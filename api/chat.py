# version: 5.0.0
import json
import time
import requests
import threading
import asyncio
import uuid
from fastapi import WebSocket, WebSocketDisconnect
from core.db import (
    get_config, add_chat_message, set_config,
    reroll_last_ai_message, reroll_from_message, get_reminders, update_reminder_last_reminded,
    increment_msg_counter, get_active_tiered_summaries, get_all_active_keypoints
)
from core.prompt_builder import build_system_prompt
from core.summary_engine import run_background_tasks
from api.sentiment import analyze_sentiment
from api.intent import detect_intent
from core.profile_builder import get_profile_context, extract_profile_from_messages
from core.emotion_tracker import record_emotion
from core.relationship import adjust_relationship
from api.greeting import generate_greeting, generate_tease, save_last_welcome, load_last_welcome, save_last_chat_time, load_last_chat_time, get_time_gap_hours
from api.split_sentences import fallback_split
from core.vector_store import add_message_vector, search_similar, search_knowledge_similar, is_model_ready
from core.demand_analyzer import save_demand_record, get_user_patterns, extract_patterns_via_llm
from datetime import datetime, timedelta

# 全局 WebSocket 连接追踪
_active_websockets: dict = {}  # {conn_id: websocket}
_diary_scheduler_started = False  # 日记调度器全局单例标志

def has_active_connections() -> bool:
    return len(_active_websockets) > 0

# 提醒规则：advance_minutes=提前多久开始提醒，repeat_interval=重复提醒间隔(分钟, None=只一次)
# level 7(强制): 目标时间后仍触发(now>target不跳过)，每30分钟重复
# level 1-6: 只在目标时间前 advance_minutes 窗口内触发
REMINDER_RULES = {
    7: {"name": "强制", "advance_minutes": 0, "repeat_interval": 30},       # 每30分钟
    6: {"name": "重要", "advance_minutes": 21*24*60, "repeat_interval": 1440}, # 每天
    5: {"name": "考试", "advance_minutes": 14*24*60, "repeat_interval": 1440},
    4: {"name": "待办", "advance_minutes": 5*24*60, "repeat_interval": 720},   # 12小时
    3: {"name": "计划", "advance_minutes": 2*24*60, "repeat_interval": 360},   # 6小时
    2: {"name": "日常", "advance_minutes": 5*60, "repeat_interval": None},      # 只一次
    1: {"name": "喝水", "advance_minutes": 30, "repeat_interval": None}
}

def check_reminders():
    """检查所有未完成的提醒，返回结构化数据列表"""
    now = datetime.now()
    reminders = get_reminders()
    results = []
    for r in reminders:
        if r.get("done"):
            continue
        try:
            target = datetime.fromisoformat(r["target_time"])
        except ValueError:
            continue
        # level 7(强制)即使过了目标时间也继续提醒，其他级别过期跳过
        if now > target and r.get("level") != 7:
            continue
        minutes_left = (target - now).total_seconds() / 60
        rule = REMINDER_RULES.get(r["level"], REMINDER_RULES[4])
        advance = rule.get("advance_minutes", 0)
        if minutes_left > advance:
            continue

        last_reminded = r.get("last_reminded")
        repeat_interval = rule.get("repeat_interval")
        if last_reminded is None:
            need_remind = True
        elif repeat_interval is None:
            need_remind = False
        else:
            try:
                last = datetime.fromisoformat(last_reminded)
                need_remind = (now - last).total_seconds() / 60 >= repeat_interval
            except ValueError:
                need_remind = True

        if need_remind:
            results.append({
                "id": r["id"],
                "level": r["level"],
                "level_name": rule["name"],
                "content": r["content"],
                "target_time": target.strftime("%Y-%m-%d %H:%M"),
                "minutes_left": int(minutes_left)
            })
            update_reminder_last_reminded(r["id"], now.isoformat())
    return results

def _trigger_daily_evolution():
    """触发每日情绪自主演化（后台线程）"""
    try:
        from core.emotion_evolution import process_daily_evolution
        process_daily_evolution()
    except Exception as e:
        print(f"[情绪演化] 触发异常: {e}")


def _calc_consecutive_days(msg_count, ws, loop):
    """后台计算连续互动天数（单次SQL查询）+ 触发成就检查"""
    try:
        from core.db import get_conn
        with get_conn() as cc:
            cc.execute("SELECT DISTINCT substr(timestamp,1,10) as d FROM chat_history ORDER BY d DESC")
            dates = [r["d"] for r in cc.fetchall()]
        today = datetime.now().strftime("%Y-%m-%d")
        consec = 0
        expected = datetime.strptime(today, "%Y-%m-%d")
        for d in dates:
            d_parsed = datetime.strptime(d, "%Y-%m-%d")
            if d_parsed == expected:
                consec += 1
                expected -= timedelta(days=1)
            else:
                break
        _check_achievements(msg_count, consec, ws, loop)
    except Exception as e:
        print(f"[连续天数] 计算失败: {e}")


def _check_achievements(msg_count, consecutive_days, ws, loop):
    """后台检查并发送成就通知"""
    try:
        from core.db import check_achievements, get_conn
        from core.relationship import get_relationship
        from datetime import datetime
        affection, trust = get_relationship()
        hour = datetime.now().hour
        with get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(DISTINCT substr(timestamp,1,10)) as days FROM chat_history")
            total_days = cursor.fetchone()["days"] or 0
        unlocked = check_achievements(msg_count, consecutive_days, total_days, hour, affection, trust)
        if unlocked:
            import json
            for a in unlocked:
                try:
                    asyncio.run_coroutine_threadsafe(
                        ws.send_text(json.dumps({"type": "achievement", "data": a})),
                        loop
                    )
                except Exception:
                    pass
    except Exception as e:
        print(f"[成就] 检查失败: {e}")

def _maybe_surprise(ws, loop):
    """后台随机触发小惊喜"""
    try:
        import random, asyncio, json
        from core.db import get_config, set_config
        from core.relationship import get_relationship
        from datetime import datetime, timedelta
        affection, _ = get_relationship()
        hour = datetime.now().hour
        last_surprise = get_config("_last_surprise", "")
        today = datetime.now().strftime("%Y-%m-%d")
        if affection >= 30 and hour >= 18 and last_surprise != today and random.random() < 0.1:
            from core.llm_client import call_llm
            ai_name = get_config("ai_name", "佐仓")
            prompt = f"你是{ai_name}，一个AI伙伴。请给用户分享一个小惊喜——可以是一首短诗、一个有趣的冷知识、或一句暖心的话。不超过50字，语气{get_config('personality', {}).get('tone', '冷静')}。"
            result = call_llm(prompt=prompt, temperature=0.9, max_tokens=100, timeout=10)
            if result:
                set_config("_last_surprise", today)
                asyncio.run_coroutine_threadsafe(
                    ws.send_text(json.dumps({"type": "surprise", "content": result})),
                    loop
                )
    except Exception as e:
        print(f"[惊喜] 生成失败: {e}")

def _check_goal_completion(user_message: str):
    """检查用户是否暗示完成了某目标（后台线程）"""
    try:
        from core.goal_tracker import check_goal_completion
        check_goal_completion(user_message)
    except Exception as e:
        print(f"[目标检测] 异常: {e}")


class ThinkingParser:
    """解析 LLM 流式输出中的【思考】...【回复】...结构
    思考部分缓冲（不发送给用户），回复部分流式输出。
    若模型未遵守格式，降级为全量输出。
    """
    REPLY_MARKER = "【回复】"
    THINK_MARKER = "【思考】"

    def __init__(self):
        self.buffer = ""
        self.thinking = ""
        self.reply = ""
        self.state = "thinking"  # thinking | reply

    def feed(self, token: str) -> str | None:
        """喂入一个 token。返回应发给用户的文本，None 表示暂不发送。"""
        self.buffer += token
        if self.state == "thinking":
            idx = self.buffer.find(self.REPLY_MARKER)
            if idx != -1:
                self.thinking = self.buffer[:idx]
                self.state = "reply"
                remainder = self.buffer[idx + len(self.REPLY_MARKER):]
                return remainder if remainder else None
            return None
        else:
            self.reply += token
            return token

    def fallback_check(self) -> bool:
        """检查是否需要降级：buffer 超过阈值且未找到标记"""
        return self.state == "thinking" and len(self.buffer) > 600 and self.REPLY_MARKER not in self.buffer

    def extract_demand(self) -> dict | None:
        """从思考内容中提取需求层级信息"""
        import re
        thinking = self.thinking
        if not thinking:
            return None
        level_match = re.search(r'需求层级[：:]\s*(.+)', thinking)
        emotion_match = re.search(r'用户情绪[：:]\s*(.+)', thinking)
        latent_match = re.search(r'深层需求[：:]\s*(.+)', thinking)
        strategy_match = re.search(r'回复策略[：:]\s*(.+)', thinking)
        return {
            "level": level_match.group(1).strip() if level_match else "UNKNOWN",
            "emotion": emotion_match.group(1).strip() if emotion_match else "",
            "latent": latent_match.group(1).strip() if latent_match else "",
            "strategy": strategy_match.group(1).strip() if strategy_match else "",
            "thinking_full": thinking.strip()[:500]
        }

async def chat_websocket(websocket: WebSocket):
    conn_id = str(uuid.uuid4())
    _active_websockets[conn_id] = websocket
    await websocket.accept()
    print(f"WebSocket 客户端已连接 (id={conn_id[:8]}, total={len(_active_websockets)})")
    
    # 欢迎语
    hours_gone = get_time_gap_hours()
    last_welcome = load_last_welcome()
    welcome_interval_ok = (last_welcome is None) or ((datetime.now() - last_welcome).total_seconds() / 3600 >= 0.5)
    if hours_gone is not None and hours_gone >= 0.5 and welcome_interval_ok:
        greeting = await asyncio.to_thread(generate_greeting)
        if greeting:
            add_chat_message("assistant", greeting)
            await websocket.send_text(json.dumps({"type": "greeting", "content": greeting}))
            save_last_welcome()
    
    # 发送活跃提醒总数
    all_active = [r for r in get_reminders() if not r.get("done")]
    await websocket.send_text(json.dumps({"type": "reminder_count", "count": len(all_active)}))

    # 后台定时扫描提醒（每 60 秒自动推送，不依赖用户发消息）
    async def reminder_loop():
        try:
            while True:
                await asyncio.sleep(60)
                try:
                    for r in check_reminders():
                        await websocket.send_text(json.dumps({"type": "reminder", "data": r}))
                except WebSocketDisconnect:
                    raise
                except Exception as e:
                    print(f"[提醒循环] 异常: {e}")
        except asyncio.CancelledError:
            raise
        except WebSocketDisconnect:
            pass
    reminder_task = asyncio.create_task(reminder_loop())

    # 主动问候：多条件触发 + AI 人格影响
    last_chat = load_last_chat_time()
    last_active = last_chat if last_chat else datetime.now()
    last_proactive_time = None
    consecutive_negative = 0
    session_triggered = set()  # 本会话已触发的主动类型
    proactive_context = None   # 最近一次主动消息 (content, trigger_type, timestamp)

    async def proactive_loop():
        nonlocal last_proactive_time, proactive_context
        try:
            while True:
                await asyncio.sleep(300)
                try:
                    from api.proactive import should_proactive_trigger, get_effective_cooldown
                    from core.db import log_proactive_message

                    idle_minutes = (datetime.now() - last_active).total_seconds() / 60

                    should, trigger_type, ctx = should_proactive_trigger(
                        idle_minutes=idle_minutes,
                        consecutive_negative=consecutive_negative,
                        session_triggered=session_triggered,
                    )

                    if should:
                        now = datetime.now()
                        cooldown = get_effective_cooldown()
                        if cooldown >= 99999:
                            continue  # proactive_frequency=off
                        if last_proactive_time and (now - last_proactive_time).total_seconds() < cooldown * 60:
                            continue

                        from api.greeting import generate_proactive
                        msg = await asyncio.to_thread(generate_proactive, trigger_type, ctx)
                        if msg:
                            await websocket.send_text(json.dumps({"type": "proactive", "content": msg}))
                            last_proactive_time = now
                            session_triggered.add(trigger_type)
                            proactive_context = {
                                "content": msg,
                                "trigger_type": trigger_type,
                                "timestamp": now
                            }
                            log_proactive_message(trigger_type, msg)
                            add_chat_message("assistant", msg)
                except WebSocketDisconnect:
                    raise
                except Exception as e:
                    print(f"[主动问候循环] 异常: {e}")
        except asyncio.CancelledError:
            raise
        except WebSocketDisconnect:
            pass
    proactive_task = asyncio.create_task(proactive_loop())
    global _diary_scheduler_started
    if not _diary_scheduler_started:
        _diary_scheduler_started = True
        diary_task = asyncio.create_task(diary_scheduler())
    else:
        diary_task = None

    # ─── 命令处理辅助函数 ───
    async def _handle_welcome():
        """处理 /welcome 命令"""
        try:
            greeting = await asyncio.to_thread(generate_greeting)
            if greeting:
                add_chat_message("assistant", greeting)
                await websocket.send_text(json.dumps({"type": "greeting", "content": greeting}))
                save_last_welcome()
            else:
                await websocket.send_text(json.dumps({"type": "token", "content": "欢迎回来～"}))
        except Exception as e:
            await websocket.send_text(json.dumps({"type": "token", "content": f"欢迎回来～（生成失败）"}))
            print(f"[welcome] 错误: {e}")
        await websocket.send_text(json.dumps({"type": "done"}))

    async def _handle_tease():
        """处理 /tease 命令"""
        from core.db import set_config as _set_config
        _old_prob = get_config("current_tease_probability", 30)
        _set_config("current_tease_probability", 100)
        try:
            tease_reply = await asyncio.to_thread(generate_tease)
            if tease_reply:
                await websocket.send_text(json.dumps({"type": "token", "content": tease_reply}))
            else:
                await websocket.send_text(json.dumps({"type": "token", "content": "（调侃生成失败，请稍后再试）"}))
        except Exception as e:
            await websocket.send_text(json.dumps({"type": "token", "content": f"（调侃出错: {e}）"}))
        finally:
            _set_config("current_tease_probability", _old_prob)
        await websocket.send_text(json.dumps({"type": "done"}))

    async def _handle_reroll():
        """处理 /reroll 命令，返回 (user_message, should_continue)"""
        try:
            last_usr = reroll_last_ai_message()
            if last_usr:
                await websocket.send_text(json.dumps({"type": "reroll_start", "content": "重新生成中..."}))
                return last_usr, False  # user_message, don't continue
            else:
                await websocket.send_text(json.dumps({"type": "token", "content": "没有可重新生成的消息"}))
                await websocket.send_text(json.dumps({"type": "done"}))
                return None, True  # skip this message
        except Exception as e:
            await websocket.send_text(json.dumps({"type": "token", "content": f"重新生成出错: {e}"}))
            await websocket.send_text(json.dumps({"type": "done"}))
            return None, True

    async def _handle_remind(msg: str):
        """处理 /remind 明天9点 记得开会 格式的定时提醒"""
        import re
        try:
            content = msg[7:].strip()  # 去掉 /remind
            if not content:
                await websocket.send_text(json.dumps({"type": "token", "content": "用法：/remind 时间 内容，如 /remind 明天9点 记得开会"}))
                await websocket.send_text(json.dumps({"type": "done"}))
                return
            # 简单的时间解析
            now = datetime.now()
            target_time = None
            remain_content = content

            # 明天N点
            m = re.match(r'明天(\d{1,2})点?\s*(.*)', content)
            if m:
                target_time = now.replace(hour=int(m.group(1)), minute=0, second=0, microsecond=0) + timedelta(days=1)
                remain_content = m.group(2) or ''
            # 今天N点
            m = re.match(r'今天(\d{1,2})点?\s*(.*)', content)
            if m:
                target_time = now.replace(hour=int(m.group(1)), minute=0, second=0, microsecond=0)
                if target_time <= now: target_time += timedelta(days=1)
                remain_content = m.group(2) or ''
            # N点
            m = re.match(r'(\d{1,2})点\s*(.*)', content)
            if m and not target_time:
                target_time = now.replace(hour=int(m.group(1)), minute=0, second=0, microsecond=0)
                if target_time <= now: target_time += timedelta(days=1)
                remain_content = m.group(2) or ''
            # N分钟后
            m = re.match(r'(\d+)分钟后?\s*(.*)', content)
            if m and not target_time:
                target_time = now + timedelta(minutes=int(m.group(1)))
                remain_content = m.group(2) or ''

            if not target_time:
                await websocket.send_text(json.dumps({"type": "token", "content": "无法识别时间，试试: /remind 明天9点 开会"}))
                await websocket.send_text(json.dumps({"type": "done"}))
                return

            from core.db import add_reminder
            add_reminder(remain_content or "提醒事项", target_time.isoformat(), 4)
            time_str = target_time.strftime("%m月%d日 %H:%M")
            await websocket.send_text(json.dumps({"type": "token", "content": f"✅ 已设置提醒：{time_str} —— {remain_content or '提醒事项'}"}))
            await websocket.send_text(json.dumps({"type": "done"}))
        except Exception as e:
            await websocket.send_text(json.dumps({"type": "token", "content": f"设置提醒失败：{e}"}))
            await websocket.send_text(json.dumps({"type": "done"}))

    async def _handle_reroll_from(msg_id):
        """处理 /reroll_from:<msg_id> 命令"""
        try:
            last_usr = reroll_from_message(msg_id)
            if last_usr:
                await websocket.send_text(json.dumps({"type": "reroll_start", "content": "从此处重新生成..."}))
                return last_usr, False
            else:
                await websocket.send_text(json.dumps({"type": "token", "content": f"无法从此消息(ID:{msg_id})重新生成，消息可能已被删除"}))
                await websocket.send_text(json.dumps({"type": "done"}))
                return None, True
        except Exception as e:
            await websocket.send_text(json.dumps({"type": "token", "content": f"重新生成出错: {e}"}))
            await websocket.send_text(json.dumps({"type": "done"}))
            return None, True

    try:
        while True:
            data = await websocket.receive_text()
            print(f"收到消息: {data}")
            try:
                request = json.loads(data)
            except Exception as e:
                print(f"[WS] JSON 解析失败: {e} | 原始数据: {data[:200]}")
                await websocket.send_text(json.dumps({"type": "error", "content": "消息格式错误"}))
                continue
            user_message = request.get("message", "")
            history = request.get("history") or []

            if not user_message:
                await websocket.send_text(json.dumps({"type": "error", "content": "消息不能为空"}))
                continue

            last_active = datetime.now()

            # ─── 记录活跃时段 + 主动消息回复检测 ───
            try:
                from core.db import record_user_activity_hour, mark_proactive_responded
                record_user_activity_hour()
            except Exception as e:
                print(f"[活动] 记录失败: {e}")
                pass

            proactive_note = ""
            if proactive_context:
                elapsed = (datetime.now() - proactive_context["timestamp"]).total_seconds()
                if elapsed < 600:
                    try:
                        mark_proactive_responded()
                    except Exception as e:
                        print(f"[主动] 标记回复失败: {e}")
                        pass
                    proactive_note = f"【主动对话上下文】你刚才主动问了用户：\"{proactive_context['content']}\"，用户现在回复了。请自然地延续这个话题，不要生硬切换。"
                proactive_context = None

            # ─── /remind 命令 ───
            if user_message.startswith("/remind"):
                await _handle_remind(user_message)
                continue

            # ─── 强制命令 ───
            if user_message.startswith("/welcome"):
                await _handle_welcome()
                continue
            if user_message.startswith("/tease"):
                await _handle_tease()
                continue
            if user_message.startswith("/reroll_from:"):
                try:
                    msg_id = int(user_message.split(":")[1])
                    user_message, skip = await _handle_reroll_from(msg_id)
                except (ValueError, IndexError):
                    skip = True
                if skip:
                    continue
                # 撤回后客户端历史含已删消息，去掉末尾2条（被删的用户+AI）
                history = history[:-2] if len(history) >= 2 else []
            elif user_message.startswith("/reroll"):
                user_message, skip = await _handle_reroll()
                if skip:
                    continue
                # 撤回后客户端历史含已删消息，去掉末尾2条（被删的用户+AI）
                history = history[:-2] if len(history) >= 2 else []

            # 正常消息才更新最后聊天时间（延迟到好感度更新后，确保时间间隔准确）
            hours_since = get_time_gap_hours() or 0
            save_last_chat_time()

            # 调侃
            tease_keywords = ["我回来了", "回来了", "好久不见", "我回来啦", "回来啦"]
            if any(kw in user_message for kw in tease_keywords):
                try:
                    tease_reply = await asyncio.to_thread(generate_tease)
                    if tease_reply:
                        add_chat_message("user", user_message)
                        add_chat_message("assistant", tease_reply)
                        await websocket.send_text(json.dumps({"type": "token", "content": tease_reply}))
                        await websocket.send_text(json.dumps({"type": "done"}))
                        continue
                except Exception as e:
                    print(f"调侃生成失败: {e}")

            # 用户消息先入库（LLM失败也不丢失用户输入）
            add_chat_message("user", user_message)
            msg_count = 0  # 等 LLM 成功后再递增

            try:
                # 检查并推送提醒（右侧弹窗）
                reminders = check_reminders()
                for r in reminders:
                    await websocket.send_text(json.dumps({"type": "reminder", "data": r}))

                # 正常对话
                api_key = get_config("api_key", "")
                is_local = get_config("api_provider", "") == "ollama"
                if not api_key and not is_local:
                    await websocket.send_text(json.dumps({"type": "error", "content": "请先配置 API Key"}))
                    continue

                current_time_str = datetime.now().strftime("%Y年%m月%d日 %H:%M")
                sentiment_result = await asyncio.to_thread(analyze_sentiment, user_message)
                emotion = sentiment_result.get("sentiment", "neutral")
                print(f"[情感分析] sentiment={emotion} target={sentiment_result.get('target')} intent={sentiment_result.get('intent')} impact={sentiment_result.get('relationship_impact')}")

                # ─── 追踪连续负面情绪（用于主动触发 A）───
                if emotion == "negative":
                    consecutive_negative += 1
                else:
                    consecutive_negative = 0

                # 记录情绪 + 调整好感度/信任度
                try:
                    record_emotion(emotion)
                    adjust_relationship(sentiment_result=sentiment_result, hours_since_last=hours_since)
                except Exception as e:
                    print(f"[情感] 记录/调整失败: {e}")

                try:
                    intent_type, intent_data = await asyncio.to_thread(detect_intent, user_message)
                except Exception as e:
                    print(f"[意图检测] 异常: {e}")
                    intent_type, intent_data = None, None
                print(f"[意图检测] type={intent_type}, data={intent_data}")
                rag_context = ""
                if is_model_ready():
                    try:
                        similar_docs = search_similar(user_message, top_k=3)
                        kb_docs = search_knowledge_similar(user_message, top_k=3)
                        all_docs = (similar_docs or []) + (kb_docs or [])
                        if all_docs:
                            rag_lines = []
                            for doc, dist in all_docs:
                                if len(doc) > 300:
                                    doc = doc[:300] + "..."
                                rag_lines.append(f"- {doc}")
                            rag_context = "\n".join(rag_lines)
                    except Exception as e:
                        print(f"向量检索失败: {e}")

                active_summaries = get_active_tiered_summaries()
                keypoints = get_all_active_keypoints()
                profile_context = get_profile_context()
                user_patterns = get_user_patterns()
                sentence_mode = get_config("sentence_mode", "auto")
                system_prompt = build_system_prompt(
                    current_time_str=current_time_str,
                    emotion=emotion,
                    user_message=user_message,
                    rag_context=rag_context,
                    tiered_summaries=active_summaries,
                    keypoints=keypoints,
                    custom_context=profile_context,
                    user_patterns=user_patterns,
                    sentence_mode=sentence_mode
                )

                # ─── 主动对话上下文注入 ───
                if proactive_note:
                    system_prompt += "\n" + proactive_note

                messages = [{"role": "system", "content": system_prompt}]
                messages.extend(history[-35:])

                # 保存原始消息（后续注入会覆写 user_message）
                original_user_message = user_message

                # 工具数据以自然口语嵌入，不破坏聊天氛围
                if intent_type == "weather" and intent_data:
                    weather_instruction = "【天气回复要求：气温和天气状况必须说出；湿度、体感温度、气压、风向风速、云量、能见度、露点等要素中随机选2-4个自然提及；风向和风速必须同时出现或同时省略。角色语气只决定措辞风格。】"
                    user_message = f"{weather_instruction}\n（刚帮你看了下{intent_data.get('city','未知')}：{intent_data.get('text','暂无数据')}）\n\n{user_message}"
                elif intent_type == "location" and intent_data:
                    city_name = f"{intent_data.get('province','')}{intent_data.get('city','')}"
                    user_message = f"（定位显示你现在在{city_name}）\n\n{user_message}"
                elif intent_type == "search" and intent_data:
                    user_message = f"（搜到了这些：{intent_data}）\n\n{user_message}"

                messages.append({"role": "user", "content": user_message})

                base_url = get_config("api_base_url", "https://api.deepseek.com/v1").rstrip("/")
                model = get_config("api_model", "deepseek-chat")
                is_local = get_config("api_provider", "") == "ollama"
                if is_local and not api_key:
                    headers = {"Content-Type": "application/json"}
                else:
                    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
                # 事实型意图用低温(0.3)减少幻觉，创意对话用高温(0.65)增加变化
                tool_temp = 0.3 if intent_type in ("weather", "location", "search") else 0.65
                payload = {
                    "model": model,
                    "messages": messages,
                    "temperature": tool_temp,
                    "max_tokens": 2000,
                    "stream": True
                }

                # 联网搜索：启用 DeepSeek 内置搜索（仅 DeepSeek 支持 search 参数）
                enable_ds_search = get_config("enable_web_search", True)
                if enable_ds_search and intent_type in ("search",) and "deepseek" in base_url:
                    payload["search"] = True

                try:
                    full_reply = []
                    token_queue = asyncio.Queue()
                    api_url = f"{base_url}/chat/completions"

                    def _stream_request():
                        """在线程中执行同步流式请求，逐 token 放入队列（含重试）"""
                        try:
                            resp = None
                            for attempt in range(3):
                                try:
                                    resp = requests.post(api_url, headers=headers, json=payload, stream=True, timeout=90)
                                    resp.raise_for_status()
                                    break
                                except requests.exceptions.RequestException:
                                    if attempt == 2:
                                        raise
                                    if resp:
                                        resp.close()
                                    time.sleep(2 ** attempt)  # 1s, 2s
                            with resp:
                                for line in resp.iter_lines():
                                    if line:
                                        line = line.decode('utf-8')
                                        if line.startswith("data: "):
                                            line = line[6:]
                                            if line == "[DONE]":
                                                break
                                            try:
                                                chunk = json.loads(line)
                                                token = chunk["choices"][0]["delta"].get("content", "")
                                                if token:
                                                    asyncio.run_coroutine_threadsafe(token_queue.put(token), loop)
                                            except (json.JSONDecodeError, KeyError, IndexError):
                                                pass  # SSE chunk 解析失败跳过（正常流中的噪声）
                        except Exception as e:
                            asyncio.run_coroutine_threadsafe(token_queue.put(e), loop)
                        finally:
                            asyncio.run_coroutine_threadsafe(token_queue.put(None), loop)

                    loop = asyncio.get_running_loop()
                    threading.Thread(target=_stream_request, daemon=True).start()

                    parser = ThinkingParser()
                    fallback_triggered = False

                    while True:
                        token = await token_queue.get()
                        if token is None:
                            # 流结束但 parser 仍在 thinking → flush 全量，避免前端静默
                            if not fallback_triggered and parser.state == "thinking" and parser.buffer:
                                print("[ThinkingParser] 流结束仍未找到【回复】，全量输出")
                                clean = parser.buffer
                                think_pos = clean.find(parser.THINK_MARKER)
                                if think_pos != -1:
                                    clean = clean[think_pos + len(parser.THINK_MARKER):]
                                await websocket.send_text(json.dumps({"type": "token", "content": clean}))
                            break
                        if isinstance(token, Exception):
                            raise token
                        full_reply.append(token)

                        if fallback_triggered:
                            await websocket.send_text(json.dumps({"type": "token", "content": token}))
                            continue

                        user_token = parser.feed(token)
                        if user_token is not None:
                            await websocket.send_text(json.dumps({"type": "token", "content": user_token}))

                        if parser.fallback_check():
                            print("[ThinkingParser] 降级：未检测到【回复】标记，全量输出")
                            fallback_triggered = True
                            if parser.buffer:
                                # 尝试清理思考标记，避免暴露内部格式给用户
                                clean = parser.buffer
                                # 如果包含【思考】，去掉它及之前的内容
                                think_pos = clean.find(parser.THINK_MARKER)
                                if think_pos != -1:
                                    clean = clean[think_pos + len(parser.THINK_MARKER):]
                                await websocket.send_text(json.dumps({"type": "token", "content": clean}))

                    # 提取需求层级 + 打印日志
                    demand = parser.extract_demand()
                    if demand:
                        print(f"[需求分层] level={demand['level']} emotion={demand.get('emotion','')[:80]} latent={demand.get('latent','')[:80]}")

                    if full_reply:
                        # 有 reply 内容则用 reply，否则清洗思考标记后存储
                        if parser.reply:
                            assistant_content = parser.reply
                        else:
                            # 降级路径：清洗思考标记（与流式输出 L713-717 逻辑一致）
                            assistant_content = parser.buffer
                            think_pos = assistant_content.find(parser.THINK_MARKER)
                            if think_pos != -1:
                                assistant_content = assistant_content[think_pos + len(parser.THINK_MARKER):]
                            reply_pos = assistant_content.find(parser.REPLY_MARKER)
                            if reply_pos != -1:
                                assistant_content = assistant_content[reply_pos + len(parser.REPLY_MARKER):]
                        sentences = fallback_split(assistant_content)
                        if sentences:
                            for i, sentence in enumerate(sentences):
                                add_chat_message("assistant", sentence)
                                if is_model_ready():
                                    add_message_vector(f"assistant_{datetime.now().timestamp()}_{i}", sentence, {"role": "assistant"})
                        else:
                            add_chat_message("assistant", assistant_content)
                            if is_model_ready():
                                add_message_vector(f"assistant_{datetime.now().timestamp()}", assistant_content, {"role": "assistant"})
                    await websocket.send_text(json.dumps({"type": "done"}))

                    # LLM 成功后补记用户消息向量 + 消息计数
                    if is_model_ready():
                        add_message_vector(f"user_{datetime.now().timestamp()}_{uuid.uuid4().hex[:6]}", user_message, {"role": "user"})
                    msg_count = increment_msg_counter()

                    # 需求记录保存（后台线程）
                    if demand and demand.get("level", "UNKNOWN") not in ("LITERAL", "UNKNOWN"):
                        threading.Thread(target=save_demand_record, args=(demand, original_user_message), daemon=True).start()

                    # 衰减 + 提及 + 三级摘要生成（后台线程）
                    threading.Thread(target=run_background_tasks, args=(msg_count, user_message), daemon=True).start()
                    if msg_count % 20 == 0:
                        threading.Thread(target=extract_profile_from_messages, daemon=True).start()
                    if msg_count % 50 == 0:
                        threading.Thread(target=extract_patterns_via_llm, daemon=True).start()
                    # 每日触发情绪自主演化
                    threading.Thread(target=_trigger_daily_evolution, daemon=True).start()
                    # 计算连续互动天数 + 检查成就
                    threading.Thread(target=_calc_consecutive_days, args=(msg_count, websocket, loop), daemon=True).start()
                    # 随机小惊喜
                    threading.Thread(target=_maybe_surprise, args=(websocket, loop), daemon=True).start()
                    # 检查目标完成
                    threading.Thread(target=_check_goal_completion, args=(original_user_message,), daemon=True).start()
                except Exception as e:
                    print(f"[API] 请求失败: {type(e).__name__}: {e}")
                    err_msg = "生成回复失败，请稍后重试" if full_reply else "AI 服务请求失败，请稍后重试"
                    await websocket.send_text(json.dumps({"type": "error", "content": err_msg}))
            except Exception as e:
                import traceback
                print(f"消息处理异常: {traceback.format_exc()}")
                await websocket.send_text(json.dumps({"type": "error", "content": f"出错: {e}"}))
    except WebSocketDisconnect:
        print(f"WebSocket 客户端断开 (id={conn_id[:8]})")
    finally:
        _active_websockets.pop(conn_id, None)
        reminder_task.cancel()
        proactive_task.cancel()
        if diary_task is not None:
            diary_task.cancel()


# ─── 天气定时推送调度器 ───
WEATHER_NOTIFICATION_FILE = "data/weather_notification.json"

async def weather_scheduler():
    """全局天气定时推送（7:00, 12:00, 19:00）"""
    last_push_date = ""
    while True:
        now = datetime.now()
        targets = [7, 12, 19]
        next_h = None
        for h in targets:
            t = now.replace(hour=h, minute=0, second=0, microsecond=0)
            if t > now: next_h = h; delay = (t - now).total_seconds(); break
        if next_h is None:
            delay = (now.replace(hour=7, minute=0, second=0, microsecond=0) + timedelta(days=1) - now).total_seconds()
        await asyncio.sleep(delay + 1)
        if not get_config("use_weather_care", True): continue
        now = datetime.now()
        today = now.strftime("%Y-%m-%d")
        hour = now.hour
        if hour in (7, 12, 19) and today != last_push_date:
            last_push_date = today
            try:
                await _push_weather(hour)
            except Exception as e:
                print(f"[天气调度] 推送异常: {e}")

async def _push_weather(push_hour: int):
    from core.weather import get_weather_for_city, build_weather_card_data
    city = get_config("precise_city") or "北京"
    weather = await asyncio.to_thread(get_weather_for_city, city)
    card_data = build_weather_card_data(weather, push_hour)
    if "error" in card_data:
        print(f"[天气调度] 天气获取失败: {card_data['error']}")
        return
    if _active_websockets:
        await _broadcast_weather(card_data)
    else:
        _write_weather_notification(card_data)

async def _broadcast_weather(card_data: dict):
    message = json.dumps({"type": "weather", "data": card_data}, ensure_ascii=False)
    disconnected = []
    for conn_id, ws in list(_active_websockets.items()):
        try:
            await ws.send_text(message)
        except Exception:
            disconnected.append(conn_id)
    for cid in disconnected:
        _active_websockets.pop(cid, None)
    # 同时存入聊天记录
    from core.db import add_chat_message
    add_chat_message("assistant", f"__WEATHER_CARD__{json.dumps(card_data, ensure_ascii=False)}")
    print(f"[天气调度] 已广播天气到 {len(_active_websockets)} 个连接")

def _write_weather_notification(card_data: dict):
    import os
    try:
        os.makedirs("data", exist_ok=True)
        with open(WEATHER_NOTIFICATION_FILE, "w", encoding="utf-8") as f:
            json.dump({"weather": card_data, "created_at": datetime.now().isoformat()}, f, ensure_ascii=False)
        print(f"[天气调度] 已写入天气通知文件")
    except Exception as e:
        print(f"[天气调度] 写入文件失败: {e}")

# ─── AI 日记定时生成 ───

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
            import asyncio as _a
            from core.db import get_conn, get_config, save_diary_entry
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

            recent_text = "\n".join([f"{'用户' if r['role']=='user' else ai_name}: {r['content'][:80]}" for r in reversed(recent)])
            prompt = f"今天是{today}。{ai_name}和用户今天聊了{msg_count}条消息。以下是今天的一些对话片段：\n{recent_text}\n\n请以{ai_name}的第一人称视角写一篇简短的日记（80字以内），内容包括：今天和用户聊了什么、自己的感受、用户今天的心情。语气温暖自然。"

            result = call_llm(prompt=prompt, temperature=0.8, max_tokens=200, timeout=15)
            if result:
                mood = "温暖"
                save_diary_entry(today, result, mood)
                print(f"[AI日记] 已自动生成 {today}")
        except Exception as e:
            print(f"[AI日记] 自动生成失败: {e}")
        last_generated = today