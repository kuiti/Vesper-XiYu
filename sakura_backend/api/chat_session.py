# api/chat_session.py — WebSocket 会话管理
"""从 chat.py 提取的 ChatSession 类，封装单次 WebSocket 连接的全生命周期。"""

import json
import random
import asyncio
import uuid
import threading
from datetime import datetime
from fastapi import WebSocket, WebSocketDisconnect
from core.db import (
    get_config, add_chat_message, set_config, get_conn,
    reroll_last_ai_message, reroll_from_message, get_reminders,
    increment_msg_counter, get_active_tiered_summaries, get_all_active_keypoints,
)
from core.prompt_builder import build_system_prompt, build_dynamic_context
from api.sentiment import analyze_sentiment
from api.intent import detect_intent
from core.profile_builder import get_profile_context, extract_atomic_facts, get_facts_context
from core.emotion_tracker import record_emotion
from core.relationship import adjust_relationship
from api.greeting import (
    generate_greeting, generate_tease, save_last_welcome, load_last_welcome,
    save_last_chat_time, load_last_chat_time, get_time_gap_hours,
)
from api.split_sentences import fallback_split
from core.vector_store import add_message_vector, add_sentence_vectors, is_model_ready
from core.demand_analyzer import save_demand_record, get_user_patterns
from api.chat_tasks import (
    check_reminders, _clean_dsml, _apply_background_update,
    _trigger_daily_evolution, _calc_consecutive_days, _check_achievements,
    _maybe_surprise, _check_goal_completion, _parse_dsml_tool_calls, _build_rag_context,
)
from api.chat_parser import ThinkingParser
from api.chat_commands import (
    handle_welcome, handle_tease, handle_reroll, handle_reroll_from, handle_remind,
)
from api.chat_loops import reminder_loop, proactive_loop, diary_scheduler
from api.chat_fallback import try_fallback_reply
from core.retry import silent_exc
from core.mcp_tools import OPENAI_TOOLS, call_tool
from core.llm_provider import get_provider

import logging
logger = logging.getLogger(__name__)

# ─── 全局连接追踪 ───
_active_websockets: dict = {}
_active_websockets_lock = asyncio.Lock()
_diary_scheduler_started = False
_diary_scheduler_lock = threading.Lock()

# 后台线程池
from concurrent.futures import ThreadPoolExecutor
_background_thread_pool = ThreadPoolExecutor(max_workers=8)

_MAX_WS_MSG_SIZE = 50 * 1024
_MAX_WS_CONNECTIONS = 20



def _safe_task(coro):
    """Create task with exception logging to avoid silent failures"""
    task = asyncio.create_task(coro)
    task.add_done_callback(lambda t: t.exception() if not t.cancelled() else None)
    return task


class ChatSession:
    """封装一次 WebSocket 连接的全生命周期。"""

    def __init__(self, websocket: WebSocket):
        self.ws = websocket
        self.conn_id = str(uuid.uuid4())
        self.reminder_task = None
        self.proactive_task = None
        self.tag_proactive_task = None
        self._conn_empathy_strategy = None
        self.user_message = ""
        self.history = []
        self.emotion = "neutral"
        self._is_game_event = False
        self._is_system = False
        self.session_triggered = set()
        self.consecutive_negative = 0
        self.sentiment_result = None
        self.intent_type = None
        self.intent_data = None
        self._stream_stop = threading.Event()

    async def run(self):
        """会话入口：接受连接 → 发送欢迎 → 启动后台 → 消息循环"""
        async with _active_websockets_lock:
            if len(_active_websockets) >= _MAX_WS_CONNECTIONS:
                await self.ws.accept()
                await self.ws.send_text(json.dumps({"type": "error", "content": "服务器连接数已满"}))
                await self.ws.close()
                return
            _active_websockets[self.conn_id] = self.ws

        self.reminder_task = _safe_task(reminder_loop(self.ws))
        await self.ws.accept()
        logger.info(f"WS 客户端已连接 (id={self.conn_id[:8]}, total={len(_active_websockets)})")

        await self._send_greeting()
        self._start_background_tasks()

        try:
            while True:
                data = await self.ws.receive_text()
                logger.debug(f"收到消息: (len={len(data)})")
                try:
                    request = json.loads(data)
                except Exception as e:
                    logger.warning(f"[WS] JSON 解析失败: {e}")
                    await self.ws.send_text(json.dumps({"type": "error", "content": "消息格式错误"}))
                    continue

                if len(json.dumps(request, ensure_ascii=False)) > _MAX_WS_MSG_SIZE:
                    await self.ws.send_text(json.dumps({"type": "error", "content": "消息过大"}))
                    continue

                await self._handle_request(request)

        except WebSocketDisconnect:
            await self._on_disconnect()
        except Exception as e:
            logger.exception(f"[WS] 未预期错误: {e}")
            await self._on_disconnect()

    async def _send_greeting(self):
        """发送欢迎语"""
        hours_gone = get_time_gap_hours()
        last_welcome = load_last_welcome()
        welcome_ok = (last_welcome is None) or \
                     ((datetime.now() - last_welcome).total_seconds() / 3600 >= 2)
        if hours_gone is not None and hours_gone >= 0.5 and welcome_ok:
            greeting = await asyncio.to_thread(generate_greeting)
            if greeting:
                add_chat_message("assistant", greeting)
                await self.ws.send_text(json.dumps({"type": "greeting", "content": greeting}))
                save_last_welcome()
                set_config("_last_proactive_time", datetime.now().isoformat())

        all_active = [r for r in get_reminders() if not r.get("done")]
        await self.ws.send_text(json.dumps({"type": "reminder_count", "count": len(all_active)}))

    def _start_background_tasks(self):
        """启动提醒/主动消息/日记后台任务"""
        last_chat = load_last_chat_time()
        last_active = last_chat if last_chat else datetime.now()
        self.consecutive_negative = int(get_config("_consecutive_negative", "0"))

        self.proactive_task = _safe_task(proactive_loop(
            self.ws, last_active, self.consecutive_negative,
            self.session_triggered, self._conn_empathy_strategy,
        ))
        global _diary_scheduler_started
        with _diary_scheduler_lock:
            if not _diary_scheduler_started:
                _diary_scheduler_started = True
                _safe_task(diary_scheduler())

    async def _on_disconnect(self):
        """连接断开时清理"""
        async with _active_websockets_lock:
            _active_websockets.pop(self.conn_id, None)
        for t in [self.reminder_task, self.proactive_task, self.tag_proactive_task]:
            if t and not t.done():
                t.cancel()
        logger.info(f"WS 断开 (id={self.conn_id[:8]}, remaining={len(_active_websockets)})")

    # ════════════════════════════════════════════
    # 单条消息处理
    # ════════════════════════════════════════════

    async def _handle_request(self, request: dict):
        """路由一条请求：反馈 / 命令 / 正常对话"""
        self.user_message = request.get("message", "")
        if not isinstance(self.user_message, str):
            self.user_message = str(self.user_message) if self.user_message else ""
        self.history = request.get("history") or []
        if self.history:
            self.history = [m for m in self.history if isinstance(m, dict) and "role" in m and "content" in m]
        self._is_game_event = request.get("_gameEvent", False)
        self._is_system = request.get("_system", False)

        # 共情反馈
        if request.get("type") == "feedback":
            await self._handle_feedback(request)
            return

        if not self.user_message:
            await self.ws.send_text(json.dumps({"type": "error", "content": "消息不能为空"}))
            return

        # 命令路由
        if self.user_message.startswith("/"):
            await self._route_command()
            return

        await self._handle_chat_message()

    async def _handle_feedback(self, request: dict):
        """处理共情反馈"""
        msg_id = request.get("msg_id")
        score = request.get("score", 0)
        if not msg_id or score not in (1, -1):
            return
        try:
            with get_conn() as conn:
                conn.cursor().execute(
                    "INSERT INTO empathy_feedback (msg_id, score, created_at) VALUES (?, ?, ?)",
                    (msg_id, score, datetime.now().isoformat()),
                )
            ai_name = get_config("ai_name", "佐仓")
            reply = random.choice(["谢谢认可～", "好的，我下次注意"]) if score == 1 \
                else random.choice(["好的，我下次注意", "收到，会改进的"])
            await self.ws.send_text(json.dumps({"type": "token", "content": reply}))
            await self.ws.send_text(json.dumps({"type": "done"}))
            add_chat_message("assistant", reply)
        except Exception as e:
            silent_exc("feedback", e)

    async def _route_command(self):
        """路由 / 开头的命令"""
        ws = self.ws
        msg = self.user_message
        history = self.history

        if msg.startswith("/welcome") or msg.startswith("/first"):
            await handle_welcome(ws, msg)
            return

        if msg.startswith("/reroll"):
            user_message, skip = await handle_reroll(ws)
            if skip:
                return
            history = history[:-2] if len(history) >= 2 else []
            self.user_message = user_message
            self.history = history
            await self._handle_chat_message()
            return

        if msg.startswith("/remind"):
            await handle_remind(ws, msg)
            return

        if msg.startswith("/goal confirm"):
            await self._handle_goal_confirm()
            return

        if msg.startswith("/goal reject"):
            await self._handle_goal_reject()
            return

        # 其他命令统一路由到正常对话
        await self._handle_chat_message()

    async def _handle_goal_confirm(self):
        try:
            gid = int(self.user_message.replace("/goal confirm", "").strip())
            with get_conn() as conn:
                conn.cursor().execute(
                    "UPDATE pending_goals SET status='confirmed' WHERE id=?", (gid,)
                )
            await self.ws.send_text(json.dumps({"type": "token", "content": "好的，我帮你记着这个目标。"}))
            await self.ws.send_text(json.dumps({"type": "done"}))
        except Exception as e:
            await self.ws.send_text(json.dumps({"type": "error", "content": f"操作失败: {e}"}))

    async def _handle_goal_reject(self):
        try:
            gid = int(self.user_message.replace("/goal reject", "").strip())
            with get_conn() as conn:
                conn.cursor().execute(
                    "UPDATE pending_goals SET status='rejected' WHERE id=?", (gid,)
                )
            await self.ws.send_text(json.dumps({"type": "token", "content": "好的，不跟踪了。"}))
            await self.ws.send_text(json.dumps({"type": "done"}))
        except Exception as e:
            await self.ws.send_text(json.dumps({"type": "error", "content": f"操作失败: {e}"}))

    # ============================================
    # Core chat processing
    # ============================================

    async def _handle_chat_message(self):
        """Process a normal chat message"""
        ws = self.ws
        msg = self.user_message
        history = self.history
        hours_since = get_time_gap_hours()

        tease_kws = ["我回来了", "回来了", "好久不见", "我回来啦", "回来啦"]
        if any(kw in msg for kw in tease_kws):
            try:
                tease_reply = await asyncio.to_thread(generate_tease)
                if tease_reply:
                    save_last_chat_time()
                    if not self._is_system:
                        tid = add_chat_message("user", msg)
                        if tid:
                            _background_thread_pool.submit(add_sentence_vectors, tid, msg, "user")
                    add_chat_message("assistant", _clean_dsml(tease_reply))
                    await ws.send_text(json.dumps({"type": "token", "content": tease_reply}))
                    await ws.send_text(json.dumps({"type": "done"}))
                    return
            except Exception as e:
                logger.warning(f"tease failed: {e}")

        save_last_chat_time()

        if not self._is_system:
            uid = add_chat_message("user", msg)
            if uid:
                _background_thread_pool.submit(add_sentence_vectors, uid, msg, "user")

        await self._analyze_context(history, hours_since)
        await self._build_and_send(history, hours_since)

    async def _analyze_context(self, history, hours_since):
        if not self._is_system and history:
            ctx = history[-5:] if history else []
            st = asyncio.to_thread(analyze_sentiment, self.user_message, ctx)
            it = asyncio.to_thread(detect_intent, self.user_message)
            r = await asyncio.gather(st, it, return_exceptions=True)
            sr = r[0] if not isinstance(r[0], Exception) else {"sentiment": "neutral", "target": "other", "intent": "statement", "relationship_impact": 0}
            self.intent_type, self.intent_data = r[1] if not isinstance(r[1], Exception) else (None, None)
        else:
            sr = {"sentiment": "neutral", "target": "other", "intent": "statement", "relationship_impact": 0}
            self.intent_type, self.intent_data = None, None

        self.sentiment_result = sr
        self.emotion = sr.get("sentiment", "neutral")
        logger.info(f"[sent] emotion={self.emotion} intent={sr.get('intent')}")

        bg = sr.get("background_update")
        if bg:
            _apply_background_update(bg)

        if not self._is_system:
            self.consecutive_negative = self.consecutive_negative + 1 if self.emotion == "negative" else 0
            set_config("_consecutive_negative", str(self.consecutive_negative))

        if not self._is_system:
            try:
                record_emotion(self.emotion)
                adjust_relationship(sentiment_result=sr, hours_since_last=hours_since)
            except Exception as e:
                logger.warning(f"emotion: {e}")

        if not self._is_system:
            try:
                from api.sentiment import get_contextual_strategy
                from core.relationship import get_relationship
                aff, _ = get_relationship()
                strategy = get_contextual_strategy(sr.get("emotion_subtype", "neutral"), sr.get("context_keyword"), aff, self.consecutive_negative)
                if strategy:
                    sr["empathy_strategy"] = strategy
                    self._conn_empathy_strategy = strategy
            except Exception:
                pass

    async def _check_dedup(self, msg):
        if self._is_system:
            return ""
        if not hasattr(self, "_recent_msgs"):
            self._recent_msgs = []
        cnt = sum(1 for m in self._recent_msgs if m == msg)
        note = f"(repeated {cnt+1}x)" if cnt >= 2 else ""
        self._recent_msgs.append(msg)
        if len(self._recent_msgs) > 5:
            self._recent_msgs = self._recent_msgs[-5:]
        return note

    async def _build_and_send(self, history, hours_since):
        ws = self.ws
        msg = self.user_message
        it = self.intent_type

        kh, rag = _build_rag_context(msg, self._is_system)
        summaries = get_active_tiered_summaries()
        kps = get_all_active_keypoints()
        pc = (get_profile_context() or "")
        fc = get_facts_context() or ""
        if pc and fc:
            pc += "\n" + fc
        elif fc:
            pc = fc
        ups = get_user_patterns()
        sm = get_config("sentence_mode", "auto")

        for r in check_reminders():
            await ws.send_text(json.dumps({"type": "reminder", "data": r}))

        provider = get_provider()
        if not get_config("api_key", "") and get_config("api_provider", "") != "ollama" and provider.name not in ("ollama",):
            await ws.send_text(json.dumps({"type": "error", "content": "configure API Key"}))
            return

        ts = datetime.now().strftime("%Y-%m-%d %H:%M")
        dedup = await self._check_dedup(msg)

        sp, dc, de = build_system_prompt(current_time_str=ts, emotion=self.emotion, user_message=msg, rag_context=rag, tiered_summaries=summaries, keypoints=kps, custom_context=pc, user_patterns=ups, sentence_mode=sm, chat_history=history)

        pn = get_config("_proactive_note", "")
        if pn:
            dc += "\n" + pn
        if kh:
            dc += "\n" + kh
        if not self._is_system and "goal_asked" not in self.session_triggered:
            try:
                from core.goal_tracker import get_pending_goals
                pg = get_pending_goals(1)
                if pg:
                    dc += "\n[goal] " + pg[0]["goal_text"]
                    self.session_triggered.add("goal_asked")
            except Exception:
                pass
        if self._is_system:
            dc += "\n[short system reply]"

        msgs = [{"role": "system", "content": sp}, {"role": "system", "content": dc}]

        try:
            with get_conn() as conn:
                rows = conn.execute("SELECT role, content FROM chat_history ORDER BY id DESC LIMIT 16").fetchall()
            for r in reversed(rows):
                d = dict(r)
                if d["content"] and not d["content"].startswith("__WEATHER_CARD__"):
                    msgs.append(d)
        except Exception as e:
            logger.warning(f"[build] 加载聊天历史失败: {e}")

        if not self._is_system and de:
            for depth, c in sorted(de, key=lambda x: x[0]):
                if depth > 0:
                    pos = max(2, len(msgs) - depth)
                    if pos < len(msgs):
                        msgs.insert(pos, {"role": "system", "content": c})

        dc2 = build_dynamic_context(ts, self.emotion)
        hints = []
        if self._conn_empathy_strategy:
            hints.append("e:" + self._conn_empathy_strategy["style"])
        if dedup:
            hints.append(dedup)
        user_content = ("[" + dc2 + "]\n" + msg) if not hints else ("[" + dc2 + "|" + ",".join(hints) + "]\n" + msg)
        # intent data injection (weather/location/search)
        if self.intent_data:
            id_ = self.intent_data
            it = self.intent_type
            if it == "weather":
                _w = id_.get('city','') + "天气:" + id_.get('text','暂无数据')
                user_content = "(" + _w + "，自然提及即可)\n\n" + user_content
            elif it == "location":
                _c = id_.get('province','') + id_.get('city','')
                user_content = "(定位显示你现在在" + _c + ")\n\n" + user_content
            elif it == "search":
                user_content = "(搜到了这些:" + str(id_) + ")\n\n" + user_content


        tt = 0.3 if it in ("weather", "location", "search") else 0.5
        ekw = {}
        bu = (get_config("api_base_url", "") or "").lower()
        if "deepseek" in bu:
            sp2 = get_config("search_provider", "ddg")
            elw = get_config("enable_llm_weather_search", False)
            if sp2 == "llm" or (sp2 == "ddg" and it in ("search",)) or (elw and it == "weather"):
                ekw["search"] = True

        await self._do_stream(msgs, tt, ekw)

    async def _do_stream(self, messages, tool_temp, extra_kwargs):
        ws = self.ws
        full_reply = []
        queue = asyncio.Queue()
        loop = asyncio.get_running_loop()
        self._stream_stop.clear()
        tc_buf = []
        parser = ThinkingParser() if not self._is_system else None
        fallback = False

        def run():
            gen = None
            try:
                p = get_provider()
                gen = p.chat_stream(messages, temperature=tool_temp, max_tokens=2000, tools=OPENAI_TOOLS, tool_choice="auto", **extra_kwargs)
                for ch in gen:
                    if self._stream_stop.is_set():
                        break
                    asyncio.run_coroutine_threadsafe(queue.put(ch), loop)
            except Exception as e:
                asyncio.run_coroutine_threadsafe(queue.put({"type": "error", "data": str(e)}), loop)
            finally:
                if gen is not None:
                    try:
                        gen.close()
                    except Exception:
                        pass
                asyncio.run_coroutine_threadsafe(queue.put({"type": "_eos"}), loop)

        _background_thread_pool.submit(run)

        try:
            while True:
                try:
                    ch = await asyncio.wait_for(queue.get(), timeout=90)
                except asyncio.TimeoutError:
                    logger.warning("[WS] 流式响应超时 (90s)")
                    await ws.send_text(json.dumps({"type": "error", "content": "响应超时，请重试"}))
                    break
                if ch["type"] == "_eos":
                    if parser and not fallback and parser.state == "thinking" and parser.buffer:
                        r = parser.extract_reply_from_buffer()
                        if r:
                            await ws.send_text(json.dumps({"type": "token", "content": r}))
                    break
                if ch["type"] == "error":
                    raise Exception(ch["data"])
                if ch["type"] == "tool_calls":
                    tc_buf = ch["data"]
                    continue
                if ch["type"] == "done":
                    continue
                t = ch["data"]
                if not t:
                    continue
                full_reply.append(t)
                if self._is_system:
                    await ws.send_text(json.dumps({"type": "token", "content": t}))
                    continue
                if fallback:
                    if "DSML" not in t:
                        await ws.send_text(json.dumps({"type": "token", "content": t}))
                    continue
                ut = parser.feed(t)
                if ut is not None and "DSML" not in ut:
                    await ws.send_text(json.dumps({"type": "token", "content": ut}))
                if parser.fallback_check():
                    fallback = True
                    r = parser.extract_reply_from_buffer()
                    if r:
                        await ws.send_text(json.dumps({"type": "token", "content": r}))
        finally:
            self._stream_stop.set()

        if tc_buf and not self._is_system:
            await self._handle_tool_calls(messages, tc_buf)
            return

        if not tc_buf and not self._is_system:
            ft = "".join(full_reply)
            if "DSML" in ft and "invoke" in ft:
                calls = _parse_dsml_tool_calls(ft)
                if calls:
                    for c in calls:
                        tc_buf.append({"id": f"dsml_{c['name']}_{len(tc_buf)}", "function": {"name": c["name"], "arguments": json.dumps(c["args"], ensure_ascii=False)}})
                    await ws.send_text(json.dumps({"type": "dsml_tool_call"}))
                    await self._handle_tool_calls(messages, tc_buf)
                    return

        await self._process_reply(full_reply, parser, fallback)

    async def _handle_tool_calls(self, messages, tc_buf):
        ws = self.ws
        p = get_provider()
        for tc in tc_buf:
            fn = tc["function"]["name"]
            try:
                fa = json.loads(tc["function"]["arguments"])
            except json.JSONDecodeError:
                fa = {}
            logger.info(f"tool {fn}")
            try:
                result = call_tool(fn, fa)
            except Exception as e:
                result = "tool failed"
                logger.error(f"tool: {e}")
            tc["type"] = "function"
            messages.append({"role": "assistant", "tool_calls": [tc]})
            messages.append({"role": "tool", "tool_call_id": tc["id"], "content": result})

        try:
            c = p.chat(messages, temperature=0.3, max_tokens=300) or "done."
            for m in ["【思考】", "【回复】"]:
                if m in c:
                    c = c.split(m)[-1].strip()
            await ws.send_text(json.dumps({"type": "token", "content": c}))
        except Exception as e:
            logger.error(f"tool LLM: {e}")
            c = "processed."
            await ws.send_text(json.dumps({"type": "token", "content": c}))

        await ws.send_text(json.dumps({"type": "done"}))
        set_config("_dropped_context", "")
        await self._save_response(c, True)

    async def _process_reply(self, full_reply, parser, fallback):
        ws = self.ws
        if not full_reply:
            await self._fallback_reply()
            return

        content = ""
        if self._is_system:
            content = "".join(full_reply).strip()
        elif parser and parser.reply:
            content = parser.reply
        elif parser:
            content = parser.buffer
            if fallback:
                content = "".join(full_reply)
            rp = content.find("【回复】")
            if rp != -1:
                content = content[rp + 4:]

        if not self._is_system and content:
            from core.tag_parser import process_reply_tags, TagParser
            pts = [t for t in TagParser.parse(content) if t["type"] == "proactive"]
            if pts:
                from api.chat_tasks import parse_interval
                iv = parse_interval(pts[0]["content"])
                if iv and iv >= 30:
                    if self.tag_proactive_task and not self.tag_proactive_task.done():
                        self.tag_proactive_task.cancel()
                    self.tag_proactive_task = _safe_task(_schedule_proactive(iv, ws))

            cleaned, fb = process_reply_tags(content, tool_calls_used=False)
            if cleaned is not None:
                content = cleaned
                for f in fb:
                    if f:
                        add_chat_message("system", f)

            rm = get_config("relationship_mode", "fast")
            if rm in ("auto", "semi-auto"):
                import re as _rr
                am = _rr.search(r"<aff:([+-]?\d+(?:\.\d+)?)>", content)
                tm = _rr.search(r"<trust:([+-]?\d+(?:\.\d+)?)>", content)
                if am or tm:
                    ad = float(am.group(1)) if am else 0
                    td = float(tm.group(1)) if tm else 0
                    if abs(ad) > 0.001 or abs(td) > 0.001:
                        adjust_relationship(sentiment_result={"relationship_impact": ad, "target": "ai", "intent": "statement", "sentiment": "neutral"})
                    content = _rr.sub(r"<aff:[+-]?\d+(?:\.\d+)?>", "", content)
                    content = _rr.sub(r"<trust:[+-]?\d+(?:\.\d+)?>", "", content).strip()

        await self._save_response(content)
        await ws.send_text(json.dumps({"type": "done", "_system": self._is_system}))
        set_config("_dropped_context", "")
        if self._is_system and content:
            await ws.send_text(json.dumps({"type": "toast", "content": content.strip()[:120]}))

        if not self._is_system:
            mc = increment_msg_counter()
            loop = asyncio.get_running_loop()
            _background_thread_pool.submit(_trigger_daily_evolution)
            _background_thread_pool.submit(_calc_consecutive_days, mc, self.ws, loop)
            _background_thread_pool.submit(_maybe_surprise, self.ws, loop)
            _background_thread_pool.submit(_check_goal_completion, content)
            if parser and hasattr(parser, "extract_demand"):
                d = parser.extract_demand()
                if d and d.get("level", "") not in ("LITERAL", "UNKNOWN"):
                    _background_thread_pool.submit(save_demand_record, d, self.user_message)
            _background_thread_pool.submit(self._extract_knowledge_graph, content)

    async def _save_response(self, content, is_tool_response=False):
        if not content:
            return
        ss = fallback_split(content)
        if ss:
            for i, s in enumerate(ss):
                add_chat_message("assistant", _clean_dsml(s))
                if is_model_ready() and not self._is_game_event:
                    add_message_vector(f"as_{datetime.now().timestamp()}_{i}", s, {"role": "assistant"})
        else:
            add_chat_message("assistant", _clean_dsml(content))
            if is_model_ready() and not self._is_game_event:
                add_message_vector(f"as_{datetime.now().timestamp()}", content, {"role": "assistant"})

    def _extract_knowledge_graph(self, content):
        if not content or len(content) < 20:
            return
        try:
            from core.knowledge_graph import extract_triples_from_text
            extract_triples_from_text(content, source="chat")
        except Exception:
            pass

    async def _fallback_reply(self):
        ws = self.ws
        p = get_provider()
        with get_conn() as conn:
            rows = conn.execute("SELECT role, content FROM chat_history ORDER BY id DESC LIMIT 8").fetchall()
        msgs = [dict(r) for r in reversed(rows)]
        try:
            handled, new_reply, content = await try_fallback_reply(
                ws, msgs, [], "", self._is_system, None,
            )
            if handled:
                if content:
                    await self._save_response(content)
            else:
                await ws.send_text(json.dumps({"type": "error", "content": "reply failed"}))
        except Exception as e:
            logger.error(f"fallback: {e}")
            await ws.send_text(json.dumps({"type": "error", "content": "reply failed"}))


async def _schedule_proactive(delay_seconds, ws):
    await asyncio.sleep(delay_seconds)
    try:
        with get_conn() as conn:
            rows = conn.execute("SELECT role FROM chat_history ORDER BY id DESC LIMIT 2").fetchall()
        if rows and rows[0]["role"] == "user":
            return
        from api.greeting import generate_proactive
        msg = await asyncio.to_thread(generate_proactive, "proactive_tag", {})
        if msg:
            add_chat_message("assistant", msg)
            await ws.send_text(json.dumps({"type": "proactive", "content": msg}))
    except Exception as e:
        logger.warning(f"proactive: {e}")
