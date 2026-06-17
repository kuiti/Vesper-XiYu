# api/chat_loops.py  |  reminder_loop + proactive_loop + diary_scheduler
# 从 chat.py 拆出的循环任务函数，接收所需状态参数而非依赖闭包

import asyncio
import json
import threading
from datetime import datetime, timedelta
from fastapi import WebSocket, WebSocketDisconnect
from core.db import (
    get_config, set_config, add_chat_message, get_reminders,
    log_proactive_message, get_conn, save_diary_entry,
)
from api.chat_tasks import check_reminders
import logging
from core.retry import silent_exc
logger = logging.getLogger(__name__)


async def reminder_loop(websocket: WebSocket):
    """后台定时扫描提醒，每 60 秒自动推送，直到用户断开连接"""
    try:
        while True:
            await asyncio.sleep(60)
            try:
                for r in check_reminders():
                    await websocket.send_text(json.dumps({"type": "reminder", "data": r}))
            except WebSocketDisconnect:
                raise
            except Exception as e:
                logger.warning(f"[提醒循环] 异常: {e}")
    except asyncio.CancelledError:
        raise
    except WebSocketDisconnect:
        pass


async def proactive_loop(
    websocket: WebSocket,
    last_active: datetime,
    consecutive_negative: int,
    session_triggered: set,
    conn_empathy_strategy: dict | None,
):
    """主动消息推送循环：多种触发条件 + AI 人格影响"""
    try:
        while True:
            await asyncio.sleep(300)
            try:
                from api.proactive import should_proactive_trigger, get_effective_cooldown
                from core.vector_store import add_sentence_vectors, is_model_ready

                idle_minutes = (datetime.now() - last_active).total_seconds() / 60

                should, trigger_type, ctx = should_proactive_trigger(
                    idle_minutes=idle_minutes,
                    consecutive_negative=consecutive_negative,
                    session_triggered=session_triggered,
                )

                # 如果主动触发未命中 → 尝试心跳触发
                if not should:
                    from api.proactive import should_heartbeat_trigger
                    should, trigger_type, ctx = should_heartbeat_trigger(
                        idle_minutes=idle_minutes,
                        session_triggered=session_triggered,
                    )

                if should:
                    now = datetime.now()

                    # 用户关闭主动消息时，咱也不打扰
                    if get_effective_cooldown() >= 99999:
                        continue

                    # 用户没回应上一条 → 检查是否为连续（2条未回复消息）
                    try:
                        with get_conn() as _conn:
                            _recent = _conn.execute(
                                "SELECT role FROM chat_history ORDER BY id DESC LIMIT 2"
                            ).fetchall()
                        # 如果最近2条都是AI说的（一条主动消息用户没回，就别再发了）
                        if len(_recent) >= 2 and all(r["role"] == "assistant" for r in _recent):
                            continue
                    except Exception as e:
                        silent_exc("proactive_loop.recent_check", e)

                    # 关怀类每日上限检查
                    from api.proactive import check_care_category_limit, record_care_trigger, get_care_category
                    if not check_care_category_limit(trigger_type):
                        continue
                    care_cat = get_care_category(trigger_type)
                    ctx["care_category"] = care_cat

                    # 注入共情策略（negative_comfort / sustained_low_mood）
                    if care_cat == "emotion" and conn_empathy_strategy:
                        ctx["empathy_style"] = conn_empathy_strategy.get("style", "")
                        ctx["empathy_avoid"] = conn_empathy_strategy.get("avoid", "")

                    if trigger_type != "heartbeat":
                        cooldown = get_effective_cooldown()
                        _last_ts = get_config("_last_proactive_time", "")
                        if _last_ts:
                            try:
                                _last_dt = datetime.fromisoformat(_last_ts)
                                if (now - _last_dt).total_seconds() < cooldown * 60:
                                    continue
                            except ValueError:
                                pass

                    from api.greeting import generate_proactive
                    msg = await asyncio.to_thread(generate_proactive, trigger_type, ctx)
                    if msg:
                        await websocket.send_text(json.dumps({"type": "proactive", "content": msg}))
                        time_key = "_last_heartbeat_time" if trigger_type == "heartbeat" else "_last_proactive_time"
                        set_config(time_key, now.isoformat())
                        session_triggered.add(trigger_type)
                        record_care_trigger(trigger_type)
                        proactive_context = {
                            "content": msg,
                            "trigger_type": trigger_type,
                            "timestamp": now.isoformat()
                        }
                        set_config("_proactive_context", json.dumps(proactive_context, ensure_ascii=False))
                        log_proactive_message(trigger_type, msg)
                        add_chat_message("assistant", msg)
                        if is_model_ready():
                            threading.Thread(target=add_sentence_vectors, args=(f"proactive_{datetime.now().timestamp()}", msg, "assistant"), daemon=True).start()
            except WebSocketDisconnect:
                raise
            except Exception as e:
                logger.warning(f"[主动消息循环] 异常: {e}")
    except asyncio.CancelledError:
        raise
    except WebSocketDisconnect:
        pass


async def diary_scheduler():
    """每天 23:00 自动生成 AI 日记"""
    last_generated = ""
    while True:
        now = datetime.now()
        target = now.replace(hour=23, minute=0, second=0, microsecond=0)
        if target <= now:
            target += timedelta(days=1)
        delay = (target - now).total_seconds()
        await asyncio.sleep(delay)
        today = datetime.now().strftime("%Y-%m-%d")
        if today == last_generated:
            continue
        try:
            from core.llm_client import call_llm

            ai_name = get_config("ai_name", "佐仓")
            with get_conn() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) as cnt FROM chat_history WHERE timestamp >= ?", (today,))
                msg_count = cursor.fetchone()["cnt"]
                cursor.execute("SELECT content, role FROM chat_history WHERE timestamp >= ? ORDER BY id DESC LIMIT 15", (today,))
                recent = cursor.fetchall()

            if msg_count < 5:
                last_generated = today
                continue

            recent_text = "\n".join([f"{'用户' if r['role']=='user' else '「' + ai_name + '」'}: {r['content'][:80]}" for r in reversed(recent)])
            prompt = f"今天是{today}。「{ai_name}」和用户今天聊了{msg_count}条消息。以下是今天的一些对话片段：\n{recent_text}\n\n请以「{ai_name}」的第一人称视角写一篇简短的日记（80字以内），内容包括：今天和用户聊了什么、自己的感受、用户今天的心情。语气温暖自然。"

            result = call_llm(prompt=prompt, temperature=0.8, max_tokens=200, timeout=15)
            if result:
                mood = "温暖"
                save_diary_entry(today, result, mood)
                logger.info(f"[AI日记] 已自动生成 {today}")
        except Exception as e:
            logger.error(f"[AI日记] 自动生成失败: {e}")
        last_generated = today