# version: 5.0.0
import json
import os
import random
import time
import threading
import asyncio
import uuid
from fastapi import WebSocket, WebSocketDisconnect
from core.db import (
    get_config, add_chat_message, set_config,
    reroll_last_ai_message, reroll_from_message, get_reminders, update_reminder_last_reminded,
    increment_msg_counter, get_active_tiered_summaries, get_all_active_keypoints
)
from core.prompt_builder import build_system_prompt, build_dynamic_context
from core.summary_engine import run_background_tasks
from api.sentiment import analyze_sentiment
from api.intent import detect_intent
from core.profile_builder import get_profile_context, extract_profile_from_messages, extract_atomic_facts, get_facts_context
from core.emotion_tracker import record_emotion
from core.relationship import adjust_relationship
from api.greeting import generate_greeting, generate_tease, save_last_welcome, load_last_welcome, save_last_chat_time, load_last_chat_time, get_time_gap_hours
from api.split_sentences import fallback_split
from core.vector_store import add_message_vector, add_sentence_vectors, search_similar, search_knowledge_similar, is_model_ready
from core.demand_analyzer import save_demand_record, get_user_patterns, extract_patterns_via_llm
from core.mcp_tools import OPENAI_TOOLS, call_tool
from core.llm_provider import get_provider
from api.chat_tasks import (
    check_reminders, _build_depth_hint, _clean_dsml,
    _apply_background_update, _trigger_daily_evolution,
    _calc_consecutive_days, _check_achievements,
    _maybe_surprise, _check_goal_completion, _parse_dsml_tool_calls,
)

from datetime import datetime, timedelta

# 全局 WebSocket 连接追踪
_active_websockets: dict = {}  # {conn_id: websocket}
_active_websockets_lock = asyncio.Lock()  # 保护 _active_websockets 的并发访问
_diary_scheduler_started = False  # 日记调度器全局单例标志
# _latest_empathy_strategy 已改为 per-connection 变量 _conn_empathy_strategy

# 提醒规则：advance_minutes=提前多久开始提醒，repeat_interval=重复提醒间隔(分钟, None=只一次)
# level 7(强制): 目标时间后仍触发(now>target不跳过)，每30分钟重复
# level 1-6: 只在目标时间前 advance_minutes 窗口内触发
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
            # 过滤误入思考段的分隔符和 DSML 工具调用标记
            self.buffer = self.buffer.replace("<<>>", "")
            if "DSML" in self.buffer and "invoke" in self.buffer:
                # 检测到 DSML 工具调用，从 buffer 中移除
                import re as _re
                self.buffer = _re.sub(r'<\｜\｜DSML\｜\｜tool_calls>.*?</\｜\｜DSML\｜\｜tool_calls>', '', self.buffer, flags=_re.DOTALL)
            idx = self.buffer.find(self.REPLY_MARKER)
            if idx != -1:
                self.thinking = self.buffer[:idx]
                self.state = "reply"
                remainder = self.buffer[idx + len(self.REPLY_MARKER):]
                if remainder:
                    self.reply = remainder
                return remainder if remainder else None
            return None
        else:
            self.reply += token
            # 过滤 DSML 工具调用标记
            if "DSML" in self.reply and "invoke" in self.reply:
                import re as _re
                self.reply = _re.sub(r'<\｜\｜DSML\｜\｜tool_calls>.*?</\｜\｜DSML\｜\｜tool_calls>', '', self.reply, flags=_re.DOTALL)
                # 重新计算 buffer 中的 reply 部分
                marker_idx = self.buffer.find(self.REPLY_MARKER)
                if marker_idx != -1:
                    self.buffer = self.buffer[:marker_idx + len(self.REPLY_MARKER)] + self.reply
                return None  # 不发送包含 DSML 的内容
            return token

    def fallback_check(self) -> bool:
        """检查是否需要降级：buffer 超过阈值且未找到标记"""
        return self.state == "thinking" and len(self.buffer) > 1000 and self.REPLY_MARKER not in self.buffer

    def extract_reply_from_buffer(self) -> str:
        """降级提取：从 buffer 中提取回复内容（过滤思考关键词和 DSML）"""
        text = self.buffer.strip()
        if not text:
            return ""
        # 过滤 DSML 工具调用
        if "DSML" in text:
            import re as _re
            text = _re.sub(r'<\｜\｜DSML\｜\｜tool_calls>.*?</\｜\｜DSML\｜\｜tool_calls>', '', text, flags=_re.DOTALL).strip()
        # 尝试提取最后一个段落
        paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
        if paragraphs:
            last = paragraphs[-1]
            # 如果最后一段太短，取最后两段
            if len(last) < 20 and len(paragraphs) >= 2:
                last = paragraphs[-2] + "\n" + last
            return last
        return text

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


async def _schedule_proactive(delay_seconds: int, ws: WebSocket):
    """AI 通过 <proactive:30min> 标签触发的主动消息"""
    await asyncio.sleep(delay_seconds)
    try:
        # 检查用户是否有回消息（如果用户已主动说话则跳过）
        from core.db import get_conn as _gc
        with _gc() as _conn:
            _recent = _conn.execute(
                "SELECT role FROM chat_history ORDER BY id DESC LIMIT 2"
            ).fetchall()
        # 如果最后一条是用户消息（说明用户在延迟期间主动说话了），跳过
        if _recent and _recent[0]["role"] == "user":
            return

        # 借用现有的主动消息生成函数
        from api.greeting import generate_proactive
        msg = await asyncio.to_thread(generate_proactive, "proactive_tag", {})
        if msg:
            from core.db import add_chat_message as _add_msg
            _add_msg("assistant", msg)
            await ws.send_text(json.dumps({"type": "proactive", "content": msg}))
            print(f"[主动消息] AI 计划的消息已发送（延迟 {delay_seconds}s）")
    except Exception as e:
        print(f"[主动消息] 计划消息发送失败: {e}")



async def chat_websocket(websocket: WebSocket):
    conn_id = str(uuid.uuid4())
    async with _active_websockets_lock:
        _active_websockets[conn_id] = websocket
    reminder_task = None
    proactive_task = None
    tag_proactive_task = None  # <proactive:> 标签触发的定时器（与 proactive_task 分开）
    _conn_empathy_strategy = None  # per-connection 共情策略
    await websocket.accept()
    print(f"WebSocket 客户端已连接 (id={conn_id[:8]}, total={len(_active_websockets)})")
    
    # 欢迎语
    hours_gone = get_time_gap_hours()
    last_welcome = load_last_welcome()
    welcome_interval_ok = (last_welcome is None) or ((datetime.now() - last_welcome).total_seconds() / 3600 >= 2)
    if hours_gone is not None and hours_gone >= 0.5 and welcome_interval_ok:
        greeting = await asyncio.to_thread(generate_greeting)
        if greeting:
            add_chat_message("assistant", greeting)
            await websocket.send_text(json.dumps({"type": "greeting", "content": greeting}))
            save_last_welcome()
            set_config("_last_proactive_time", datetime.now().isoformat())
    
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
    consecutive_negative = int(get_config("_consecutive_negative", "0"))
    session_triggered = set()  # 本会话已触发的主动类型
    # 从 DB 恢复主动上下文，避免重连后丢失
    try:
        proactive_context = json.loads(get_config("_proactive_context", "null"))
    except Exception:
        proactive_context = None

    async def proactive_loop():
        nonlocal proactive_context
        try:
            while True:
                await asyncio.sleep(300)
                try:
                    from api.proactive import should_proactive_trigger, get_effective_cooldown
                    from core.db import log_proactive_message, get_config as _get_cfg, set_config as _set_cfg, add_chat_message as _add_msg

                    idle_minutes = (datetime.now() - last_active).total_seconds() / 60

                    should, trigger_type, ctx = should_proactive_trigger(
                        idle_minutes=idle_minutes,
                        consecutive_negative=consecutive_negative,
                        session_triggered=session_triggered,
                    )

                    # 条件驱动未触发 → 尝试心跳
                    if not should:
                        from api.proactive import should_heartbeat_trigger
                        should, trigger_type, ctx = should_heartbeat_trigger(
                            idle_minutes=idle_minutes,
                            session_triggered=session_triggered,
                        )

                    if should:
                        now = datetime.now()

                        # 用户关闭主动消息时，心跳也不触发
                        if get_effective_cooldown() >= 99999:
                            continue

                        # 用户还没回应上一条 → 检查是否为连续第2条未回复消息
                        try:
                            from core.db import get_conn as _gc
                            with _gc() as _conn:
                                _recent = _conn.execute(
                                    "SELECT role FROM chat_history ORDER BY id DESC LIMIT 2"
                                ).fetchall()
                            # 如果最近2条都是AI（说明上一条主动消息用户还没回），别再发
                            if len(_recent) >= 2 and all(r["role"] == "assistant" for r in _recent):
                                continue
                        except Exception:
                            pass

                        # 关怀类别每日上限检查
                        from api.proactive import check_care_category_limit, record_care_trigger, get_care_category
                        if not check_care_category_limit(trigger_type):
                            continue
                        care_cat = get_care_category(trigger_type)
                        ctx["care_category"] = care_cat

                        # 注入共情策略（negative_comfort / sustained_low_mood）
                        if care_cat == "emotion" and _conn_empathy_strategy:
                            ctx["empathy_style"] = _conn_empathy_strategy.get("style", "")
                            ctx["empathy_avoid"] = _conn_empathy_strategy.get("avoid", "")

                        if trigger_type != "heartbeat":
                            cooldown = get_effective_cooldown()
                            _last_ts = _get_cfg("_last_proactive_time", "")
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
                            _set_cfg(time_key, now.isoformat())
                            session_triggered.add(trigger_type)
                            record_care_trigger(trigger_type)
                            proactive_context = {
                                "content": msg,
                                "trigger_type": trigger_type,
                                "timestamp": now.isoformat()
                            }
                            _set_cfg("_proactive_context", json.dumps(proactive_context, ensure_ascii=False))
                            log_proactive_message(trigger_type, msg)
                            _add_msg("assistant", msg)
                            if is_model_ready():
                                threading.Thread(target=add_sentence_vectors, args=(f"proactive_{datetime.now().timestamp()}", msg, "assistant"), daemon=True).start()
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
                add_chat_message("assistant", _clean_dsml(greeting))
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
        _old_prob = get_config("current_tease_probability", 30)
        set_config("current_tease_probability", 100)
        try:
            tease_reply = await asyncio.to_thread(generate_tease)
            if tease_reply:
                await websocket.send_text(json.dumps({"type": "token", "content": tease_reply}))
            else:
                await websocket.send_text(json.dumps({"type": "token", "content": "（调侃生成失败，请稍后再试）"}))
        except Exception as e:
            await websocket.send_text(json.dumps({"type": "token", "content": f"（调侃出错: {e}）"}))
        finally:
            set_config("current_tease_probability", _old_prob)
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

            # 辅助：解析时间并校验范围
            def _parse_time(hour_str, minute_str="0"):
                h, mi = int(hour_str), int(minute_str)
                if not (0 <= h <= 23 and 0 <= mi <= 59):
                    return None
                return h, mi

            # N分钟后（优先匹配，避免 "1分钟后" 被误解析为 "1点"）
            m = re.match(r'(\d+)分钟后?\s*(.*)', content)
            if m:
                target_time = now + timedelta(minutes=int(m.group(1)))
                remain_content = m.group(2) or ''
            # 明天/后天 N点[M分] [上午/下午]
            if not target_time:
                m = re.match(r'(明天|后天)?\s*(上午|下午|早上|晚上)?\s*(\d{1,2})点?\s*(?:(\d{1,2})分?)?\s*(.*)', content)
                if m:
                    day_offset, period, hour_str, minute_str, rest = m.group(1), m.group(2), m.group(3), m.group(4) or "0", m.group(5) or ''
                    parsed = _parse_time(hour_str, minute_str)
                    if parsed:
                        h, mi = parsed
                        if period in ("下午", "晚上") and h < 12:
                            h += 12
                        elif period in ("上午", "早上") and h == 12:
                            h = 0
                        days = 2 if day_offset == "后天" else 1 if day_offset == "明天" else 0
                        target_time = now.replace(hour=h, minute=mi, second=0, microsecond=0) + timedelta(days=days)
                        if days == 0 and target_time <= now:
                            target_time += timedelta(days=1)
                        remain_content = rest

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
            if not isinstance(user_message, str):
                user_message = str(user_message) if user_message else ""
            history = request.get("history") or []
            _is_game_event = request.get("_gameEvent", False)
            _is_system = request.get("_system", False)

            # 共情反馈
            if request.get("type") == "feedback":
                msg_id = request.get("msg_id")
                score = request.get("score", 0)
                if msg_id and score in (1, -1):
                    try:
                        from core.db import get_conn
                        with get_conn() as conn:
                            conn.cursor().execute("INSERT INTO empathy_feedback (msg_id, score, created_at) VALUES (?, ?, ?)",
                                                  (msg_id, score, datetime.now().isoformat()))
                        # AI 回应反馈（按人设风格）
                        ai_name = get_config("ai_name", "佐仓")
                        custom_prompt = get_config("custom_system_prompt", "")
                        if score == 1:
                            if custom_prompt:
                                reply = f"（{ai_name}收到了你的认可）"
                            else:
                                reply = random.choice([
                                    "谢谢认可～",
                                    "嘿嘿，有帮助就好",
                                    "开心！",
                                    "收到你的赞，动力满满",
                                ])
                        else:
                            if custom_prompt:
                                reply = f"（{ai_name}会注意改进的）"
                            else:
                                reply = random.choice([
                                    "好的，我下次注意",
                                    "收到，会改进的",
                                    "嗯，我知道了",
                                    "谢谢反馈，我调整一下",
                                ])
                        await websocket.send_text(json.dumps({"type": "token", "content": reply}))
                        await websocket.send_text(json.dumps({"type": "done"}))
                        add_chat_message("assistant", reply)
                    except Exception as e:
                        print(f"[反馈] 记录失败: {e}")
                continue

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

            proactive_note = ""
            if proactive_context:
                ts = proactive_context["timestamp"]
                if isinstance(ts, str):
                    ts = datetime.fromisoformat(ts)
                elapsed = (datetime.now() - ts).total_seconds()
                if elapsed < 600:
                    try:
                        mark_proactive_responded()
                    except Exception as e:
                        print(f"[主动] 标记回复失败: {e}")
                        pass
                    proactive_note = f"【主动对话上下文】你刚才主动问了用户：\"{proactive_context['content']}\"，用户现在回复了。请自然地延续这个话题，不要生硬切换。"
                proactive_context = None
                set_config("_proactive_context", "null")

            # ─── /remind 命令 ───
            _cmd = user_message.split()[0] if user_message.split() else ""
            if _cmd == "/remind":
                await _handle_remind(user_message)
                continue

            # ─── 强制命令 ───
            if _cmd == "/welcome":
                await _handle_welcome()
                continue
            if _cmd == "/tease":
                await _handle_tease()
                continue
            # 目标确认命令
            if user_message.startswith("/goal "):
                parts = user_message.split()
                if len(parts) >= 3 and parts[1] in ("confirm", "reject"):
                    try:
                        from core.goal_tracker import confirm_goal, reject_goal
                        gid = int(parts[2])
                        if parts[1] == "confirm":
                            confirm_goal(gid)
                            await websocket.send_text(json.dumps({"type": "token", "content": "好的，我帮你记着这个目标。"}))
                        else:
                            reject_goal(gid)
                            await websocket.send_text(json.dumps({"type": "token", "content": "好的，不跟踪了。"}))
                        await websocket.send_text(json.dumps({"type": "done"}))
                    except Exception as e:
                        await websocket.send_text(json.dumps({"type": "error", "content": f"操作失败: {e}"}))
                else:
                    await websocket.send_text(json.dumps({"type": "error", "content": "用法：/goal confirm ID 或 /goal reject ID"}))
                continue
            _is_reroll = False
            _cmd_parts = user_message.split(":", 1)
            _cmd_name = _cmd_parts[0].split()[0] if _cmd_parts[0] else ""
            if _cmd_name == "/reroll_from" and len(_cmd_parts) > 1:
                try:
                    msg_id = int(_cmd_parts[1].strip())
                    user_message, skip = await _handle_reroll_from(msg_id)
                except (ValueError, IndexError):
                    skip = True
                if skip:
                    continue
                history = history[:-2] if len(history) >= 2 else []
                _is_reroll = True
            elif _cmd_name == "/reroll":
                user_message, skip = await _handle_reroll()
                if skip:
                    continue
                # 撤回后客户端历史含已删消息，去掉末尾2条（被删的用户+AI）
                history = history[:-2] if len(history) >= 2 else []
                _is_reroll = True

            # 正常消息才更新最后聊天时间（延迟到好感度更新后，确保时间间隔准确）
            hours_since = get_time_gap_hours() or 0

            # 调侃（必须在 save_last_chat_time 之前，否则 get_time_gap_hours 算出间隔≈0）
            tease_keywords = ["我回来了", "回来了", "好久不见", "我回来啦", "回来啦"]
            if any(kw in user_message for kw in tease_keywords) and not _is_reroll:
                try:
                    tease_reply = await asyncio.to_thread(generate_tease)
                    if tease_reply:
                        save_last_chat_time()
                        if not _is_system:
                            _tid = add_chat_message("user", user_message)
                            if _tid:
                                threading.Thread(target=add_sentence_vectors, args=(_tid, user_message, "user"), daemon=True).start()
                        add_chat_message("assistant", _clean_dsml(tease_reply))
                        await websocket.send_text(json.dumps({"type": "token", "content": tease_reply}))
                        await websocket.send_text(json.dumps({"type": "done"}))
                        continue
                except Exception as e:
                    print(f"调侃生成失败: {e}")

            save_last_chat_time()

            # 用户消息先入库（系统消息和LLM失败也不丢失用户输入）
            _user_msg_id = None
            if not _is_system:
                _user_msg_id = add_chat_message("user", user_message)
                if _user_msg_id:
                    threading.Thread(target=add_sentence_vectors, args=(_user_msg_id, user_message, "user"), daemon=True).start()
            msg_count = 0  # 等 LLM 成功后再递增

            try:
                # 检查并推送提醒（右侧弹窗）
                reminders = check_reminders()
                for r in reminders:
                    await websocket.send_text(json.dumps({"type": "reminder", "data": r}))

                # 正常对话
                api_key = get_config("api_key", "")
                is_local = get_config("api_provider", "") == "ollama"
                provider = get_provider()
                if not api_key and not is_local and provider.name not in ("ollama",):
                    await websocket.send_text(json.dumps({"type": "error", "content": "请先配置 API Key 或切换至 Ollama"}))
                    continue

                current_time_str = datetime.now().strftime("%Y年%m月%d日 %H:%M")

                # 消息去重检测（用 \x00 分隔，避免与用户消息冲突）
                dedup_note = ""
                if not _is_system:
                    _DEDUP_SEP = "|||"
                    _recent_user = get_config("_recent_user_msgs", "")
                    _recent_list = [m for m in _recent_user.split(_DEDUP_SEP) if m] if _recent_user else []
                    _dup_count = sum(1 for m in _recent_list if m == user_message)
                    if _dup_count >= 2:
                        dedup_note = f"（用户已说了{_dup_count+1}遍同样的话，可以自然地提一下）"
                    _recent_list.append(user_message)
                    if len(_recent_list) > 5:
                        _recent_list = _recent_list[-5:]
                    set_config("_recent_user_msgs", _DEDUP_SEP.join(_recent_list))

                if not _is_system:
                    # 传入最近对话上下文，帮助 LLM 理解语境（撒娇/调侃 vs 真抱怨）
                    _ctx = history[-5:] if history else []
                    # 并发执行情感分析和意图检测，减少阻塞时间
                    _sentiment_task = asyncio.to_thread(analyze_sentiment, user_message, _ctx)
                    _intent_task = asyncio.to_thread(detect_intent, user_message)
                    _results = await asyncio.gather(_sentiment_task, _intent_task, return_exceptions=True)
                    sentiment_result = _results[0] if not isinstance(_results[0], Exception) else {"sentiment": "neutral", "target": "other", "intent": "statement", "relationship_impact": 0}
                    if isinstance(_results[1], Exception):
                        print(f"[意图检测] 异常: {_results[1]}")
                        intent_type, intent_data = None, None
                    else:
                        intent_type, intent_data = _results[1]
                else:
                    sentiment_result = {"sentiment": "neutral", "target": "other", "intent": "statement", "relationship_impact": 0, "background_update": None}
                    intent_type, intent_data = None, None
                emotion = sentiment_result.get("sentiment", "neutral")
                print(f"[情感分析] sentiment={emotion} target={sentiment_result.get('target')} intent={sentiment_result.get('intent')} impact={sentiment_result.get('relationship_impact')}")
                # 自动记录 AI 背景（外号/喜好/身份）
                bg_update = sentiment_result.get("background_update")
                if bg_update:
                    _apply_background_update(bg_update)

                # ─── 追踪连续负面情绪（用于主动触发 A）───
                if not _is_system:
                    if emotion == "negative":
                        consecutive_negative += 1
                    else:
                        consecutive_negative = 0
                    set_config("_consecutive_negative", str(consecutive_negative))

                # 记录情绪 + 调整好感度/信任度（系统消息/游戏事件跳过，不扭曲关系）
                if not _is_system:
                    try:
                        record_emotion(emotion)
                        adjust_relationship(sentiment_result=sentiment_result, hours_since_last=hours_since)
                    except Exception as e:
                        print(f"[情感] 记录/调整失败: {e}")

                # ─── 共情策略计算（情绪×情境）───
                empathy_strategy = None
                if not _is_system:
                    try:
                        from api.sentiment import get_contextual_strategy
                        from core.relationship import get_relationship
                        affection, _ = get_relationship()
                        emotion_subtype = sentiment_result.get("emotion_subtype", "neutral")
                        context_kw = sentiment_result.get("context_keyword")
                        empathy_strategy = get_contextual_strategy(emotion_subtype, context_kw, affection, consecutive_negative)
                        if empathy_strategy:
                            sentiment_result["empathy_strategy"] = empathy_strategy
                            _conn_empathy_strategy = empathy_strategy
                    except Exception:
                        pass

                if not _is_system:
                    print(f"[意图检测] type={intent_type}, data={intent_data}")
                # ─── 知识库标题匹配推荐（带 60s TTL 缓存）───
                kb_title_hint = ""
                if not _is_system:
                    try:
                        now_ts = time.time()
                        if not hasattr(chat_websocket, '_kb_titles_cache') or now_ts - chat_websocket._kb_titles_cache_ts > 60:
                            from core.db import get_knowledge_filenames
                            chat_websocket._kb_titles_cache = get_knowledge_filenames()
                            chat_websocket._kb_titles_cache_ts = now_ts
                        for title in chat_websocket._kb_titles_cache:
                            name = os.path.splitext(title)[0]
                            if len(name) >= 2 and name in user_message:
                                kb_title_hint = f"【知识库关联】用户的话题可能与知识库文档「{title}」相关，你可以自然地引用其中的内容。"
                                break
                    except Exception:
                        pass

                rag_context = ""
                if not _is_system and is_model_ready():
                    try:
                        similar_docs = search_similar(user_message, top_k=3, include_metadata=True)
                        kb_docs = search_knowledge_similar(user_message, top_k=3)
                        if similar_docs:
                            # 只注入高相关性的文档，避免污染上下文
                            RAG_THRESHOLD = 0.55  # cosine similarity 阈值
                            rag_lines = []
                            for doc, dist, meta in similar_docs:
                                cos_score = 1.0 - (dist / 2.0) if dist <= 2 else 0
                                if cos_score < RAG_THRESHOLD:
                                    continue
                                if len(doc) > 300:
                                    doc = doc[:300] + "..."
                                # 格式化为对话形式
                                role = meta.get("role", "user") if meta else "user"
                                speaker = "你" if role == "assistant" else "用户"
                                rag_lines.append(f"{speaker}：{doc}")
                            if rag_lines:
                                rag_context = "\n".join(rag_lines)
                        if kb_docs:
                            # 知识库文档仍用列表格式
                            kb_lines = []
                            for doc, dist in kb_docs:
                                cos_score = 1.0 - (dist / 2.0) if dist <= 2 else 0
                                if cos_score < RAG_THRESHOLD:
                                    continue
                                if len(doc) > 300:
                                    doc = doc[:300] + "..."
                                kb_lines.append(f"- {doc}")
                            if kb_lines:
                                kb_context = "【知识库参考】\n" + "\n".join(kb_lines)
                                rag_context = (rag_context + "\n" + kb_context) if rag_context else kb_context
                    except Exception as e:
                        print(f"向量检索失败: {e}")

                active_summaries = get_active_tiered_summaries()
                keypoints = get_all_active_keypoints()
                profile_context = get_profile_context()
                facts_context = get_facts_context()
                if profile_context and facts_context:
                    profile_context = profile_context + "\n" + facts_context
                elif facts_context:
                    profile_context = facts_context
                user_patterns = get_user_patterns()
                sentence_mode = get_config("sentence_mode", "auto")
                static_prefix, dynamic_content = build_system_prompt(
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

                # ─── 可变部分注入 ───
                if proactive_note:
                    dynamic_content += "\n" + proactive_note
                if kb_title_hint:
                    dynamic_content += "\n" + kb_title_hint
                if not _is_system and not session_triggered.intersection({"goal_asked"}):
                    try:
                        from core.goal_tracker import get_pending_goals
                        pending = get_pending_goals(1)
                        if pending:
                            goal_text = pending[0]["goal_text"]
                            gid = pending[0]["id"]
                            dynamic_content += f"\n【待确认目标】用户提过「{goal_text}」，自然问一句要不要跟踪。确认回[/goal confirm {gid}]，拒绝回[/goal reject {gid}]。"
                            session_triggered.add("goal_asked")
                    except Exception:
                        pass
                if _is_system:
                    dynamic_content += "\n【重要】这条消息是系统通知，不是用户直接说的。用活泼、鼓励的语气回复，像朋友在旁边看你玩游戏一样。控制在15字以内，简短有力。不要追问，不要展开话题。"

                # 两条 system message：第一条缓存命中，第二条每次变化
                messages = [
                    {"role": "system", "content": static_prefix},
                    {"role": "system", "content": dynamic_content}
                ]

                # 智能历史修剪：去重 + 合并碎片 + 情感优先（最近8条必保留，剩余4条选有情感的）
                def _trim_history(hist):
                    if not hist:
                        return []
                    # 过滤天气卡片消息
                    hist = [m for m in hist if not m.get("content", "").startswith("__WEATHER_CARD__")]
                    # 去重：按 (role, content[:80]) 签名去重
                    seen = set()
                    deduped = []
                    for msg in reversed(hist):
                        sig = (msg.get("role", ""), msg.get("content", "")[:80])
                        if sig not in seen:
                            seen.add(sig)
                            deduped.append(msg)
                    deduped.reverse()
                    # 合并连续 assistant 碎片（仅限 5 分钟内相邻消息）
                    merged = []
                    for msg in deduped:
                        if (msg.get("role") == "assistant" and merged and merged[-1].get("role") == "assistant"):
                            # 检查时间间隔
                            _prev_ts = merged[-1].get("timestamp", "")
                            _this_ts = msg.get("timestamp", "")
                            _close_in_time = True
                            if _prev_ts and _this_ts:
                                try:
                                    _delta = abs((datetime.fromisoformat(_this_ts) - datetime.fromisoformat(_prev_ts)).total_seconds())
                                    _close_in_time = _delta < 480  # 8 分钟内
                                except Exception:
                                    pass
                            if _close_in_time:
                                merged[-1] = {**merged[-1], "content": merged[-1]["content"] + msg["content"]}
                            else:
                                merged.append(dict(msg))
                        else:
                            merged.append(dict(msg))
                    # 情感关键词优先保留
                    emotion_kw = ["累", "烦", "开心", "难过", "生气", "害怕", "紧张", "兴奋", "无聊", "孤独", "焦虑"]
                    def _has_emotion(msg):
                        return any(kw in msg.get("content", "") for kw in emotion_kw)
                    # 最近 16 条必保留，剩余 8 条优先选有情感的（总计 24 条）
                    recent = merged[-16:]
                    older = merged[:-16]
                    if len(older) > 8:
                        emotional = [m for m in older if _has_emotion(m)]
                        non_emotional = [m for m in older if not _has_emotion(m)]
                        older = (emotional + non_emotional)[-8:]

                    # 被裁掉的早期消息 → 提取关键词注入上下文
                    dropped = merged[:-(16+8)]
                    if dropped:
                        user_msgs_in_dropped = [m["content"][:50] for m in dropped if m.get("role") == "user"]
                        if user_msgs_in_dropped:
                            try:
                                import jieba
                                from collections import Counter
                                all_words = []
                                for msg in user_msgs_in_dropped:
                                    words = [w for w in jieba.cut(msg) if len(w) > 1]
                                    all_words.extend(words)
                                top_words = [w for w, _ in Counter(all_words).most_common(8)]
                                if top_words:
                                    dropped_context = f"【更早的对话中提到过】{'、'.join(top_words)}"
                                    set_config("_dropped_context", dropped_context)
                            except Exception:
                                pass

                    return recent + older

                messages.extend(_trim_history(history))

                # ─── 时间间隔标记（仅 system 消息，不污染用户可见内容）───
                _time_gapped = []
                _prev_ts = None
                _now = datetime.now()
                _today = _now.strftime("%Y-%m-%d")
                # 先注入一条时间参考，让 AI 知道每条消息大概什么时候
                _time_ref = f"（当前时间：{_now.strftime('%m月%d日 %H:%M')}，以下是历史消息，每条都有时间戳但不在内容里展示）"
                _time_gapped.append({"role": "system", "content": _time_ref})
                for _i, _m in enumerate(messages):
                    _ts = _m.get("timestamp", "")
                    # 时间间隔标记
                    if _ts and _prev_ts:
                        try:
                            _curr = datetime.fromisoformat(_ts) if isinstance(_ts, str) else _ts
                            _prev = datetime.fromisoformat(_prev_ts) if isinstance(_prev_ts, str) else _prev_ts
                            _gap = (_curr - _prev).total_seconds() / 60
                            _m_date = _curr.strftime("%Y-%m-%d")
                            _m_time = _curr.strftime("%H:%M")
                            _gap_note = ""
                            if _m_date == _today:
                                _gap_note = f"（{_m_time}）"
                            elif _m_date == (_now - timedelta(days=1)).strftime("%Y-%m-%d"):
                                _gap_note = f"（昨天 {_m_time}）"
                            else:
                                _gap_note = f"（{_m_date} {_m_time}）"
                            if _gap > 480:
                                _days = int(_gap / 1440)
                                _time_gapped.append({"role": "system", "content": f"{_gap_note} 过了{_days}天，新的一次对话"})
                            elif _gap > 120:
                                _hrs = int(_gap / 60)
                                _time_gapped.append({"role": "system", "content": f"{_gap_note} 过了{_hrs}小时，不是刚才"})
                            elif _gap > 30:
                                _time_gapped.append({"role": "system", "content": f"{_gap_note} 隔了{int(_gap)}分钟"})
                        except Exception:
                            pass
                    # 不修改消息内容，保持原样
                    _time_gapped.append(_m)
                    if _ts:
                        _prev_ts = _ts
                messages = _time_gapped

                # 深度提示注入（SillyTavern 方案）：在对话历史的深度 2-4 注入行为强化
                if not _is_system and len(messages) > 4:
                    depth_hint = _build_depth_hint(user_message, emotion)
                    if depth_hint:
                        insert_pos = max(1, len(messages) - 3)  # 距末尾 2-3 条处
                        messages.insert(insert_pos, {"role": "system", "content": depth_hint})

                # 保存原始消息（后续注入会覆写 user_message）
                original_user_message = user_message

                # 动态上下文注入用户消息头部（提升 system prompt 缓存命中率）
                if not _is_system:
                    dynamic_ctx = build_dynamic_context(current_time_str, emotion)
                    hints = []
                    if empathy_strategy:
                        hints.append(f"共情：{empathy_strategy['style']}")
                        if empathy_strategy.get('avoid'):
                            hints.append(f"避免：{empathy_strategy['avoid']}")
                    if dedup_note:
                        hints.append(dedup_note.strip("（）"))
                    if hints:
                        user_message = f"[{dynamic_ctx}|{'，'.join(hints)}]\n{user_message}"
                    else:
                        user_message = f"[{dynamic_ctx}]\n{user_message}"

                # 工具数据以自然口语嵌入，不破坏聊天氛围
                if intent_type == "weather" and intent_data:
                    user_message = f"（{intent_data.get('city','')}天气：{intent_data.get('text','暂无数据')}，自然提及即可）\n\n{user_message}"
                elif intent_type == "location" and intent_data:
                    city_name = f"{intent_data.get('province','')}{intent_data.get('city','')}"
                    user_message = f"（定位显示你现在在{city_name}）\n\n{user_message}"
                elif intent_type == "search" and intent_data:
                    user_message = f"（搜到了这些：{intent_data}）\n\n{user_message}"

                # 添加时间上下文
                now = datetime.now()
                time_context = f"（当前时间：{now.strftime('%Y-%m-%d %H:%M')}）"
                messages.append({"role": "user", "content": f"{time_context}\n{user_message}"})

                # 事实型意图用低温(0.3)减少幻觉，创意对话用高温(0.65)增加变化
                tool_temp = 0.3 if intent_type in ("weather", "location", "search") else 0.5

                # 联网搜索参数（DeepSeek 等支持 search 参数的 provider）
                sp = get_config("search_provider", "ddg")
                enable_llm_weather = get_config("enable_llm_weather_search", False)
                extra_kwargs = {}
                base_url = (get_config("api_base_url", "") or "").lower()
                if "deepseek" in base_url:
                    if sp == "llm" or \
                       (sp == "ddg" and intent_type in ("search",)) or \
                       (enable_llm_weather and intent_type == "weather"):
                        extra_kwargs["search"] = True

                try:
                    full_reply = []
                    assistant_content = ""
                    token_queue = asyncio.Queue()
                    loop = asyncio.get_running_loop()

                    def _stream_request():
                        """在线程中执行流式请求，逐 chunk 放入队列（使用 LLMProvider）"""
                        try:
                            for chunk in provider.chat_stream(
                                messages,
                                temperature=tool_temp,
                                max_tokens=2000,
                                tools=OPENAI_TOOLS,
                                tool_choice="auto",
                                **extra_kwargs,
                            ):
                                asyncio.run_coroutine_threadsafe(token_queue.put(chunk), loop)
                        except Exception as e:
                            asyncio.run_coroutine_threadsafe(token_queue.put({"type": "error", "data": str(e)}), loop)
                        finally:
                            asyncio.run_coroutine_threadsafe(token_queue.put({"type": "_eos"}), loop)

                    threading.Thread(target=_stream_request, daemon=True).start()

                    parser = ThinkingParser() if not _is_system else None
                    fallback_triggered = False
                    tool_calls_buffer = []

                    while True:
                        try:
                            chunk = await asyncio.wait_for(token_queue.get(), timeout=90)
                        except asyncio.TimeoutError:
                            print("[流式] token_queue 超时，强制结束")
                            break

                        # 流结束
                        if chunk["type"] == "_eos":
                            if parser:
                                if not fallback_triggered and parser.state == "thinking" and parser.buffer:
                                    print("[ThinkingParser] 流结束仍未找到【回复】，智能提取")
                                    reply = parser.extract_reply_from_buffer()
                                    if reply:
                                        await websocket.send_text(json.dumps({"type": "token", "content": reply}))
                            break

                        if chunk["type"] == "error":
                            raise Exception(chunk["data"])

                        # tool_calls（provider 已累积完成，直接赋值）
                        if chunk["type"] == "tool_calls":
                            tool_calls_buffer = chunk["data"]
                            continue

                        # token
                        token = chunk["data"]
                        if not token:
                            continue
                        full_reply.append(token)

                        # 系统消息跳过思考解析，直接输出
                        if _is_system:
                            await websocket.send_text(json.dumps({"type": "token", "content": token}))
                            continue

                        if fallback_triggered:
                            if "DSML" not in token:
                                await websocket.send_text(json.dumps({"type": "token", "content": token}))
                            continue

                        user_token = parser.feed(token)
                        if user_token is not None and "DSML" not in user_token:
                            await websocket.send_text(json.dumps({"type": "token", "content": user_token}))

                        if parser.fallback_check():
                            print("[ThinkingParser] 降级：未检测到【回复】标记，智能提取")
                            fallback_triggered = True
                            reply = parser.extract_reply_from_buffer()
                            if reply:
                                await websocket.send_text(json.dumps({"type": "token", "content": reply}))

                    # ─── DSML 格式工具调用检测（DeepSeek 文本输出兜底）───
                    if not tool_calls_buffer and not _is_system:
                        full_text = "".join(full_reply)
                        if "DSML" in full_text and "invoke" in full_text:
                            dsml_calls = _parse_dsml_tool_calls(full_text)
                            if dsml_calls:
                                print(f"[DSML工具调用] 检测到 {len(dsml_calls)} 个工具调用")
                                for dc in dsml_calls:
                                    tool_calls_buffer.append({
                                        "id": f"dsml_{dc['name']}_{len(tool_calls_buffer)}",
                                        "function": {"name": dc["name"], "arguments": json.dumps(dc["args"], ensure_ascii=False)}
                                    })
                                # 清除已发送给用户的 DSML 文本（通知前端清除）
                                await websocket.send_text(json.dumps({"type": "dsml_tool_call"}))

                    # ─── 处理 tool_calls ───
                    if tool_calls_buffer and not _is_system:
                        print(f"[工具调用] 检测到 {len(tool_calls_buffer)} 个工具调用")
                        # 执行工具
                        tool_results = []
                        for tc in tool_calls_buffer:
                            func_name = tc["function"]["name"]
                            try:
                                func_args = json.loads(tc["function"]["arguments"])
                            except json.JSONDecodeError:
                                func_args = {}
                            print(f"[工具调用] {func_name}({func_args})")
                            try:
                                result = call_tool(func_name, func_args)
                            except Exception as e:
                                result = f"工具执行失败: {e}"
                                print(f"[工具调用] 错误: {e}")
                            print(f"[工具调用] 结果: {result[:100]}")
                            tool_results.append({
                                "tool_call_id": tc["id"],
                                "role": "tool",
                                "content": result
                            })
                        # 将工具结果添加到消息中，继续对话
                        for tc in tool_calls_buffer:
                            tc["type"] = "function"
                        messages.append({"role": "assistant", "tool_calls": tool_calls_buffer})
                        messages.extend(tool_results)
                        # 重新请求 LLM（非流式 + 低温，工具调用后简洁确认）
                        try:
                            assistant_content = provider.chat(
                                messages,
                                temperature=0.3,
                                max_tokens=300,
                            ) or "工具已执行。"
                            # 去掉可能残留的思考标记
                            for marker in ["【思考】", "【回复】"]:
                                if marker in assistant_content:
                                    parts = assistant_content.split(marker)
                                    assistant_content = parts[-1].strip() if parts[-1].strip() else parts[0].strip()
                            # 逐字流式输出，保持打字机效果
                            for char in assistant_content:
                                await websocket.send_text(json.dumps({"type": "token", "content": char}))
                                await asyncio.sleep(0.02)
                            full_reply = [assistant_content]
                        except Exception as e:
                            print(f"[工具调用] LLM 请求失败: {e}")
                            assistant_content = "已处理。"
                            await websocket.send_text(json.dumps({"type": "token", "content": assistant_content}))
                        # 发送完成信号
                        await websocket.send_text(json.dumps({"type": "done"}))
                        # 保存消息（拆句保存）
                        if assistant_content:
                            sentences = fallback_split(assistant_content)
                            if sentences:
                                for i, sentence in enumerate(sentences):
                                    add_chat_message("assistant", _clean_dsml(sentence))
                                    if is_model_ready() and not _is_game_event:
                                        add_message_vector(f"assistant_{datetime.now().timestamp()}_{i}", sentence, {"role": "assistant"})
                            else:
                                add_chat_message("assistant", _clean_dsml(assistant_content))
                                if is_model_ready() and not _is_game_event:
                                    add_message_vector(f"assistant_{datetime.now().timestamp()}", assistant_content, {"role": "assistant"})
                        # 记录消息计数
                        if not _is_system:
                            msg_count = increment_msg_counter()
                        continue

                    # 提取需求层级（系统消息跳过）
                    demand = None
                    if parser:
                        demand = parser.extract_demand()
                        if demand:
                            print(f"[需求分层] level={demand['level']} emotion={demand.get('emotion','')[:80]} latent={demand.get('latent','')[:80]}")

                    assistant_content = ""
                    if full_reply:
                        if _is_system:
                            assistant_content = "".join(full_reply).strip()
                        elif parser.reply:
                            assistant_content = parser.reply
                        else:
                            assistant_content = parser.buffer
                            if fallback_triggered:
                                assistant_content = "".join(full_reply)
                            think_pos = assistant_content.find(parser.THINK_MARKER)
                            if think_pos != -1:
                                assistant_content = assistant_content[think_pos + len(parser.THINK_MARKER):]
                            reply_pos = assistant_content.find(parser.REPLY_MARKER)
                            if reply_pos != -1:
                                assistant_content = assistant_content[reply_pos + len(parser.REPLY_MARKER):]

                        # ─── Tag 指令解析（function calling fallback + 主动消息）───
                        tag_feedback = None
                        if not _is_system and assistant_content:
                            from core.tag_parser import process_reply_tags, TagParser, parse_interval

                            # 先提取 <proactive:> 标签（AI 自己设置下次主动消息间隔）
                            proactive_tags = [t for t in TagParser.parse(assistant_content) if t["type"] == "proactive"]
                            if proactive_tags:  # 只取第一个，避免多定时器并行
                                pt = proactive_tags[0]
                                interval_sec = parse_interval(pt["content"])
                                if interval_sec and interval_sec >= 30:
                                    print(f"[主动消息] AI 设置了 {pt['content']} 后主动消息")
                                    # 取消之前的 proactive 任务（避免多个定时器并行）
                                    if tag_proactive_task and not tag_proactive_task.done():
                                        tag_proactive_task.cancel()
                                    tag_proactive_task = asyncio.create_task(_schedule_proactive(interval_sec, websocket))

                            cleaned, tag_feedback = process_reply_tags(assistant_content, tool_calls_used=bool(tool_calls_buffer))
                            if cleaned is not None:
                                if cleaned != assistant_content:
                                    print(f"[TagParser] 移除了标签文本: {assistant_content[:50]} -> {cleaned[:50]}")
                                assistant_content = cleaned
                                for fb in tag_feedback:
                                    if fb:
                                        add_chat_message("system", fb)

                        if not _is_system:
                            # 拆句保存，向量化也按句索引
                            sentences = fallback_split(assistant_content)
                            if sentences:
                                for i, sentence in enumerate(sentences):
                                    add_chat_message("assistant", _clean_dsml(sentence))
                                    if is_model_ready() and not _is_game_event:
                                        add_message_vector(f"assistant_{datetime.now().timestamp()}_{i}", sentence, {"role": "assistant"})
                            else:
                                add_chat_message("assistant", _clean_dsml(assistant_content))
                                if is_model_ready() and not _is_game_event:
                                    add_message_vector(f"assistant_{datetime.now().timestamp()}", assistant_content, {"role": "assistant"})
                    # 【口嗨检测】AI说"帮你记了"但没调工具 → 后台补调
                    if not _is_system and not tool_calls_buffer and assistant_content:
                        import re as _re
                        false_promise = _re.search(r'(帮你记|已记录|已帮你|记在日历|提醒已设|日程已加)', assistant_content)
                        if false_promise:
                            print(f"[口嗨检测] AI口嗨了但没有调工具，提示词: {original_user_message[:50]}")

                    await websocket.send_text(json.dumps({"type": "done", "_system": _is_system}))
                    if _is_system and assistant_content:
                        await websocket.send_text(json.dumps({"type": "toast", "content": assistant_content.strip()[:120]}))

                    # 消息计数（系统消息全跳过，用户消息向量化已在接收时完成）
                    if not _is_system:
                        msg_count = increment_msg_counter()
                    else:
                        msg_count = 0

                    # 需求记录保存（后台线程，系统消息跳过）
                    if not _is_system and demand and demand.get("level", "UNKNOWN") not in ("LITERAL", "UNKNOWN"):
                        threading.Thread(target=save_demand_record, args=(demand, original_user_message), daemon=True).start()

                    # 衰减 + 提及 + 三级摘要生成（后台线程，系统消息跳过）
                    if not _is_system:
                        threading.Thread(target=run_background_tasks, args=(msg_count, original_user_message), daemon=True).start()
                    if not _is_system:
                        if msg_count % 50 == 0:
                            threading.Thread(target=extract_profile_from_messages, daemon=True).start()
                        if msg_count % 30 == 0:
                            threading.Thread(target=extract_atomic_facts, daemon=True).start()
                        if msg_count % 30 == 0:
                            # 知识图谱提取
                            def _extract_kg():
                                try:
                                    from core.knowledge_graph import extract_triplets_from_messages, save_triplets
                                    from core.db import get_recent_chat_messages
                                    msgs = get_recent_chat_messages(20)
                                    triplets = extract_triplets_from_messages(msgs)
                                    if triplets:
                                        save_triplets(triplets)
                                        print(f"[知识图谱] 提取了 {len(triplets)} 个三元组")
                                except Exception as e:
                                    print(f"[知识图谱] 提取失败: {e}")
                            threading.Thread(target=_extract_kg, daemon=True).start()
                        if msg_count % 50 == 0:
                            threading.Thread(target=extract_patterns_via_llm, daemon=True).start()
                        # 计算连续互动天数 + 检查成就
                        threading.Thread(target=_calc_consecutive_days, args=(msg_count, websocket, loop), daemon=True).start()
                    # 每日触发情绪自主演化（全局，不限系统消息）
                    threading.Thread(target=_trigger_daily_evolution, daemon=True).start()
                    # 随机小惊喜 + 检查目标完成 + 自动记录AI背景（系统消息跳过）
                    if not _is_system:
                        threading.Thread(target=_maybe_surprise, args=(websocket, loop), daemon=True).start()
                        threading.Thread(target=_check_goal_completion, args=(original_user_message,), daemon=True).start()

                except Exception as e:
                    print(f"[API] 请求失败: {type(e).__name__}: {e}")
                    # 流式中途失败：保存已发内容，避免用户看到的回复丢失
                    if full_reply and assistant_content and not _is_system:
                        add_chat_message("assistant", assistant_content)
                    err_msg = "生成回复失败，请稍后重试" if full_reply else "AI 服务请求失败，请稍后重试"
                    await websocket.send_text(json.dumps({"type": "error", "content": err_msg}))
            except Exception as e:
                import traceback
                print(f"消息处理异常: {traceback.format_exc()}")
                await websocket.send_text(json.dumps({"type": "error", "content": f"出错: {e}"}))
    except WebSocketDisconnect:
        print(f"WebSocket 客户端断开 (id={conn_id[:8]})")
    finally:
        async with _active_websockets_lock:
            _active_websockets.pop(conn_id, None)
        if reminder_task:
            reminder_task.cancel()
        if proactive_task:
            proactive_task.cancel()
        if tag_proactive_task and not tag_proactive_task.done():
            tag_proactive_task.cancel()
        # 清理主动上下文，避免重连后误触发
        try:
            set_config("_proactive_context", "null")
        except Exception:
            pass
        # diary_task 是全局任务，不在此取消（由 APScheduler 管理生命周期）


# ─── 天气定时推送调度器 ───
WEATHER_NOTIFICATION_FILE = "data/weather_notification.json"

async def weather_scheduler():
    """全局天气定时推送（7:00, 12:00, 19:00）"""
    pushed_slots = set()
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
        if hour in (7, 12, 19) and (today, hour) not in pushed_slots:
            pushed_slots.add((today, hour))
            try:
                await _push_weather(hour)
            except Exception as e:
                print(f"[天气调度] 推送异常: {e}")

async def _push_weather(push_hour: int):
    from core.weather import get_weather_for_city, build_weather_card_data
    city = get_config("precise_city") or get_config("manual_city") or "北京"
    for attempt in range(2):
        weather = await asyncio.to_thread(get_weather_for_city, city)
        card_data = build_weather_card_data(weather, push_hour)
        if "error" not in card_data:
            break
        print(f"[天气调度] 第{attempt+1}次获取失败: {card_data['error']}")
        if attempt == 0:
            await asyncio.sleep(60)  # 等 60 秒重试一次
    else:
        print(f"[天气调度] 2次尝试均失败，本时段跳过")
        return
    if _active_websockets:
        await _broadcast_weather(card_data)
    else:
        _write_weather_notification(card_data)

async def _broadcast_weather(card_data: dict):
    message = json.dumps({"type": "weather", "data": card_data}, ensure_ascii=False)
    disconnected = []
    async with _active_websockets_lock:
        for conn_id, ws in list(_active_websockets.items()):
            try:
                await ws.send_text(message)
            except Exception:
                disconnected.append(conn_id)
        for cid in disconnected:
            _active_websockets.pop(cid, None)
    # 同时存入聊天记录
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
            from core.db import save_diary_entry, get_conn
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
                print(f"[AI日记] 已自动生成 {today}")
        except Exception as e:
            print(f"[AI日记] 自动生成失败: {e}")
        last_generated = today