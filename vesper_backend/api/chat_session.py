# api/chat_session.py — WebSocket 会话管理
"""从 chat.py 提取的 ChatSession 类，封装单次 WebSocket 连接的全生命周期。"""

import json
import random
import asyncio
import uuid
import threading
import time
from datetime import datetime
from fastapi import WebSocket, WebSocketDisconnect
from core.db import (
    get_config, add_chat_message, set_config, get_conn,
    increment_msg_counter, get_active_tiered_summaries, get_all_active_keypoints,
    record_user_activity_hour,
)
from core.prompt_builder import build_system_prompt, build_dynamic_context
from api.sentiment import analyze_sentiment
from api.intent import detect_intent
from core.profile_builder import get_profile_context, get_facts_context
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
    _clean_dsml, _apply_background_update,
    _trigger_daily_evolution, _calc_consecutive_days,
    _maybe_surprise, _check_goal_completion, _build_rag_context,
    _run_demand_pattern_extraction,
)
from api.chat_parser import ThinkingParser
from api.chat_commands import (
    handle_welcome, handle_reroll,
)
from api.chat_loops import proactive_loop, diary_scheduler
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
_WS_RATE_LIMIT = 10  # 每窗口最大消息数
_WS_RATE_WINDOW = 10  # 速率窗口（秒）



def _safe_task(coro):
    """Create task with exception logging to avoid silent failures"""
    task = asyncio.create_task(coro)
    def _log_if_failed(t):
        if not t.cancelled():
            exc = t.exception()
            if exc:
                logger.warning(f"[task] 后台任务异常: {exc}")
    task.add_done_callback(_log_if_failed)
    return task


def _detect_reply_emotion(text: str) -> str:
    """检测 AI 回复的情感倾向，返回标签用于前端表情显示（正则化）"""
    from core.emotion_patterns import detect_emotion
    return detect_emotion(text or "")


def _compress_conversation_context(msgs: list[dict], max_chars: int = 40000) -> list[dict]:
    """SmartCrusher v2：消息列表超出字符上限时，智能压缩早期对话。

    保留最近 8 条完整，之前的提取关键信息：
    - 用户提问/请求（标记是否已回答）
    - 情感转折点
    - 决定/结论
    - 用户表达的偏好
    """
    total = sum(len(m.get("content", "") or "") for m in msgs)
    if total <= max_chars:
        return msgs

    system_msgs = [m for m in msgs if m["role"] == "system"]
    history_msgs = [m for m in msgs if m["role"] in ("user", "assistant")]

    if len(history_msgs) <= 8:
        return msgs

    keep = history_msgs[-8:]
    compress = history_msgs[:-8]

    # 智能提取关键信息
    from core.emotion_patterns import detect_emotion, is_question as _is_q
    topics = []        # 讨论过的话题
    user_questions = []  # 用户问题（是否已回答）
    emotions = []      # 情感变化

    for i, m in enumerate(compress):
        content = (m.get("content") or "").strip()
        if not content or len(content) < 3:
            continue
        role = m["role"]

        # 检测用户问题
        if role == "user":
            if _is_q(content):
                # 检查后续是否有 assistant 回复
                answered = any(
                    compress[j]["role"] == "assistant" and (compress[j].get("content") or "").strip()
                    for j in range(i + 1, min(i + 3, len(compress)))
                )
                if not answered:
                    user_questions.append(content[:80])
            elif len(content) > 15:
                topics.append(content[:60])

        # 检测情感转折（用强度 + 反讽降权）
        from core.emotion_patterns import detect_emotion_intensity, is_sarcastic
        emo, intensity = detect_emotion_intensity(content)
        if is_sarcastic(content):
            intensity *= 0.3  # 反讽降权 70%
        if intensity > 0.4:  # 只记录中高置信情感
            label = "用户" if role == "user" else "AI"
            emo_label = {"happy": "开心", "sad": "低落", "love": "亲密", "surprise": "惊讶"}.get(emo, emo)
            emotions.append(f"{label}{emo_label}")

    # 构建摘要
    parts = []
    if topics:
        parts.append(f"讨论过: {'; '.join(topics[:5])}")
    if user_questions:
        parts.append(f"未完全回答的问题: {'; '.join(user_questions[:3])}")
    if emotions:
        # 取最后的情感状态
        parts.append(f"情绪走向: {emotions[-1]}")

    if parts:
        summary_text = "。".join(parts)
        if len(summary_text) > 800:
            summary_text = summary_text[:800] + "…"
        summary = {"role": "system", "content": f"【早期对话摘要】{summary_text}"}
        return system_msgs + [summary] + keep

    # 降级：简单截取
    compressed_parts = []
    for m in compress:
        content = (m.get("content") or "").strip()
        if content:
            label = "用户" if m["role"] == "user" else "你"
            compressed_parts.append(f"{label}: {content[:80]}")
    if compressed_parts:
        summary_text = " | ".join(compressed_parts)
        if len(summary_text) > 800:
            summary_text = summary_text[:800] + "…"
        summary = {"role": "system", "content": f"【早期对话摘要】{summary_text}"}
        return system_msgs + [summary] + keep

    return system_msgs + keep


def _run_memory_curation(history: list, character_id: int = 0):
    """后台记忆整理：每 8 轮对话自动提取事实（per-character）"""
    try:
        # 提取最近对话用于分析
        recent = []
        for msg in (history or []):
            role = msg.get("role", "")
            content = msg.get("content", "")
            if role in ("user", "assistant") and content:
                recent.append({"role": role, "content": content})
        if len(recent) < 4:
            return

        from core.memory_curation import run_curation
        result = run_curation(recent, character_id=character_id)
        if result.get("saved", 0) > 0:
            logger.info(f"[记忆整理] 从 {len(recent)} 条对话中提取并保存了 {result['saved']} 条事实")
    except Exception as e:
        logger.warning(f"[记忆整理] 后台任务异常: {e}")


class ChatSession:
    """封装一次 WebSocket 连接的全生命周期。"""

    def __init__(self, websocket: WebSocket):
        self.ws = websocket
        self.conn_id = str(uuid.uuid4())
        self.proactive_task = None
        self.tag_proactive_task = None
        self._conn_empathy_strategy = None
        self._session_start = datetime.now().isoformat()
        self._session_msg_count = 0
        self._character_id = 0
        try:
            from core.character_card import CharacterCard
            card = CharacterCard.get_active()
            if card and hasattr(card, '_db_id') and card._db_id:
                self._character_id = card._db_id
        except Exception:
            pass
        self.user_message = ""
        self._rate_timestamps: list = []
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
        self._easter_egg_msg = None
        self._last_ai_msg_id = None
        # 计算用户离开时长
        self._idle_minutes = self._calc_idle_minutes()

    def _calc_idle_minutes(self) -> float:
        """计算用户离开时长（分钟）"""
        try:
            last_chat = load_last_chat_time()
            if last_chat:
                return max(0, (datetime.now() - last_chat).total_seconds() / 60)
        except Exception:
            pass
        return 0

    async def run(self):
        """会话入口：接受连接 → 发送欢迎 → 启动后台 → 消息循环"""
        async with _active_websockets_lock:
            if len(_active_websockets) >= _MAX_WS_CONNECTIONS:
                await self.ws.accept()
                await self.ws.send_text(json.dumps({"type": "error", "content": "服务器连接数已满"}))
                await self.ws.close()
                return
            _active_websockets[self.conn_id] = self.ws

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

                # 速率限制
                now_ts = time.time()
                self._rate_timestamps = [t for t in self._rate_timestamps if now_ts - t < _WS_RATE_WINDOW]
                if len(self._rate_timestamps) >= _WS_RATE_LIMIT:
                    await self.ws.send_text(json.dumps({"type": "error", "content": "消息发送过快，请稍后"}))
                    continue
                self._rate_timestamps.append(now_ts)

                try:
                    await self._handle_request(request)
                except Exception as e:
                    import traceback
                    logger.warning(f"[WS] 处理消息异常（会话继续）: {e}\n{traceback.format_exc()}")
                    try:
                        await self.ws.send_text(json.dumps({"type": "error", "content": "处理消息时出错，请重试"}))
                    except Exception:
                        pass

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
                add_chat_message("assistant", greeting, character_id=self._character_id)
                await self.ws.send_text(json.dumps({"type": "greeting", "content": greeting}))
                save_last_welcome()
                set_config("_last_proactive_time", datetime.now().isoformat())

    def _start_background_tasks(self):
        """启动提醒/主动消息/日记后台任务"""
        last_chat = load_last_chat_time()
        last_active = last_chat if last_chat else datetime.now()
        self.consecutive_negative = int(get_config("_consecutive_negative", "0"))

        self.proactive_task = _safe_task(proactive_loop(
            self.ws, last_active, self.consecutive_negative,
            self.session_triggered, self._conn_empathy_strategy,
            character_id=self._character_id,
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
        for t in [self.proactive_task, self.tag_proactive_task]:
            if t and not t.done():
                t.cancel()

        # 保存情景记忆（会话快照）
        if self._session_msg_count >= 3:
            try:
                from core.episodic_memory import save_episode
                from core.db import get_recent_chat_messages
                end_time = datetime.now().isoformat()
                messages = get_recent_chat_messages(self._session_msg_count + 10, character_id=self._character_id)
                if messages:
                    save_episode(self._session_start, end_time, messages, character_id=self._character_id)
            except Exception as e:
                logger.warning(f"[情景] 保存失败: {e}")

        logger.info(f"WS 断开 (id={self.conn_id[:8]}, remaining={len(_active_websockets)})")

    # ════════════════════════════════════════════
    # 单条消息处理
    # ════════════════════════════════════════════

    async def _handle_request(self, request: dict):
        """路由一条请求：反馈 / 命令 / 正常对话（防御性：所有输入不可信）"""
        # 消息内容：类型安全 + 长度限制
        self.user_message = request.get("message", "")
        if not isinstance(self.user_message, str):
            self.user_message = str(self.user_message) if self.user_message else ""
        self.user_message = self.user_message[:4000]  # 硬上限，防止 DoS

        # 历史记录：类型安全 + 数量限制
        self.history = request.get("history") or []
        if not isinstance(self.history, list):
            self.history = []
        if self.history:
            self.history = [m for m in self.history if isinstance(m, dict) and "role" in m and "content" in m]
            self.history = self.history[-50:]  # 最多保留 50 条
            # 每条内容截断
            for m in self.history:
                if isinstance(m.get("content"), str) and len(m["content"]) > 2000:
                    m["content"] = m["content"][:2000]

        # 布尔标志：类型安全
        self._is_game_event = bool(request.get("_gameEvent", False))
        self._is_system = bool(request.get("_system", False))

        # 共情反馈
        if request.get("type") == "feedback":
            await self._handle_feedback(request)
            return

        # 角色切换（不断开 WebSocket，就地切换）
        if request.get("type") == "switch_character":
            await self._handle_switch_character(request)
            return

        # 编辑消息（重新生成）
        if request.get("type") == "edit":
            await self._handle_edit(request)
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
        try:
            msg_id = int(request.get("msg_id", 0))
        except (ValueError, TypeError):
            return
        score = request.get("score", 0)
        if not msg_id or score not in (1, -1):
            return
        try:
            from core.db import get_chat_conn as _get_chat
            with _get_chat(self._character_id) as conn:
                conn.cursor().execute(
                    "INSERT INTO empathy_feedback (msg_id, score, created_at) VALUES (?, ?, ?)",
                    (msg_id, score, datetime.now().isoformat()),
                )
            # 负面反馈时保存到反馈记忆（从角色专属库读取）
            if score == -1:
                from core.db import get_chat_conn
                chat_conn = get_chat_conn(self._character_id)
                c = chat_conn.cursor()
                c.execute("SELECT content FROM chat_history WHERE id = ?", (int(msg_id),))
                row = c.fetchone()
                if row and row["content"]:
                    from core.feedback_memory import save_behavior_feedback
                    save_behavior_feedback(
                        f"用户不喜欢这样的回复: {row['content'][:500]}",
                        category="behavior", source="empathy_feedback",
                        character_id=self._character_id,
                    )
            reply = random.choice(["谢谢认可～", "收到，我会继续努力的"]) if score == 1 \
                else random.choice(["好的，我下次注意", "收到，会改进的"])
            await self.ws.send_text(json.dumps({"type": "token", "content": reply}))
            await self.ws.send_text(json.dumps({"type": "done"}))
            add_chat_message("assistant", reply, character_id=self._character_id)
        except Exception as e:
            silent_exc("feedback", e)

    async def _handle_switch_character(self, request: dict):
        """就地切换角色（不断开 WebSocket）"""
        char_id = request.get("character_id", 0)
        try:
            char_id = int(char_id)
        except (ValueError, TypeError):
            await self.ws.send_text(json.dumps({"type": "error", "content": "无效的角色 ID"}))
            return

        from core.character_card import CharacterCard
        card = CharacterCard.load_from_db(char_id)
        if not card:
            await self.ws.send_text(json.dumps({"type": "error", "content": f"角色 {char_id} 不存在"}))
            return

        # 激活角色
        CharacterCard.activate(char_id)
        self._character_id = card._db_id if hasattr(card, '_db_id') and card._db_id else char_id
        self._session_msg_count = 0
        self._session_start = datetime.now().isoformat()

        # 同步全局配置
        from core.db import set_config
        if card.name:
            set_config("ai_name", card.name)
        if card.system_prompt:
            set_config("custom_system_prompt", card.system_prompt)
        set_config("_active_character_card", card.name)

        # 清除 prompt 缓存
        try:
            from core.prompt_builder import clear_persona_cache
            clear_persona_cache()
        except Exception:
            pass

        # 通知前端切换成功
        await self.ws.send_text(json.dumps({
            "type": "switched",
            "character_id": char_id,
            "name": card.name,
            "first_mes": card.first_mes or "",
        }))

        logger.info(f"[WS] 角色切换: → {card.name} (id={char_id})")

    async def _handle_edit(self, request: dict):
        """编辑已发送的消息，从 msg_id 处重新生成"""
        msg_id = request.get("msg_id", 0)
        new_text = request.get("message", "").strip()
        if not msg_id or not new_text:
            await self.ws.send_text(json.dumps({"type": "error", "content": "编辑参数不完整"}))
            return
        if len(new_text) > 4000:
            await self.ws.send_text(json.dumps({"type": "error", "content": "消息过长"}))
            return

        try:
            from core.db import get_chat_conn, reroll_from_message
            conn = get_chat_conn(self._character_id)
            cursor = conn.cursor()
            cursor.execute("SELECT role FROM chat_history WHERE id = ?", (msg_id,))
            row = cursor.fetchone()
            if not row:
                await self.ws.send_text(json.dumps({"type": "error", "content": "消息不存在"}))
                return

            # 删除 msg_id 之后的所有消息
            reroll_from_message(msg_id, character_id=self._character_id)
        except Exception as e:
            logger.warning(f"[edit] 删除历史失败: {e}")
            await self.ws.send_text(json.dumps({"type": "error", "content": "编辑失败"}))
            return

        # 设置新消息并重新生成
        self.user_message = new_text
        self.history = self.history[:-2] if len(self.history) >= 2 else []
        self._session_msg_count += 1
        await self._handle_chat_message()

    async def _route_command(self):
        """路由 / 开头的命令"""
        ws = self.ws
        msg = self.user_message
        history = self.history

        if msg.startswith("/welcome") or msg.startswith("/first"):
            await handle_welcome(ws, character_id=self._character_id)
            return

        if msg.startswith("/reroll"):
            user_message, skip = await handle_reroll(ws, character_id=self._character_id)
            if skip:
                return
            history = history[:-2] if len(history) >= 2 else []
            self.user_message = user_message
            self.history = history
            await self._handle_chat_message()
            return

        if msg.startswith("/goal confirm"):
            await self._handle_goal_confirm()
            return

        if msg.startswith("/goal reject"):
            await self._handle_goal_reject()
            return

        if msg.startswith("/feedback"):
            content = msg[len("/feedback"):].strip()
            if content:
                from core.feedback_memory import save_behavior_feedback
                save_behavior_feedback(content, category="behavior", source="feedback_command", character_id=self._character_id)
                await ws.send_text(json.dumps({"type": "token", "content": "收到，我记住了。"}))
                await ws.send_text(json.dumps({"type": "done"}))
            else:
                await ws.send_text(json.dumps({"type": "error", "content": "用法: /feedback <你想让我改进的地方>"}))
            return

        # 其他命令统一路由到正常对话
        await self._handle_chat_message()

    async def _handle_goal_confirm(self):
        """确认追踪用户指定的目标"""
        raw = self.user_message.replace("/goal confirm", "").strip()
        if not raw or not raw.isdigit():
            await self.ws.send_text(json.dumps({"type": "error", "content": "用法: /goal confirm <ID>"}))
            return
        gid = int(raw)
        with get_chat_conn(self._character_id) as conn:
            conn.cursor().execute("UPDATE pending_goals SET status='confirmed' WHERE id=?", (gid,))
        await self.ws.send_text(json.dumps({"type": "token", "content": "好的，我帮你记着这个目标。"}))
        await self.ws.send_text(json.dumps({"type": "done"}))

    async def _handle_goal_reject(self):
        """拒绝追踪用户指定的目标"""
        raw = self.user_message.replace("/goal reject", "").strip()
        if not raw or not raw.isdigit():
            await self.ws.send_text(json.dumps({"type": "error", "content": "用法: /goal reject <ID>"}))
            return
        gid = int(raw)
        with get_chat_conn(self._character_id) as conn:
            conn.cursor().execute("UPDATE pending_goals SET status='rejected' WHERE id=?", (gid,))
        await self.ws.send_text(json.dumps({"type": "token", "content": "好的，不跟踪了。"}))
        await self.ws.send_text(json.dumps({"type": "done"}))

    # ============================================
    # Core chat processing
    # ============================================

    async def _handle_chat_message(self):
        """Process a normal chat message"""
        ws = self.ws
        msg = self.user_message
        history = self.history
        hours_since = get_time_gap_hours()
        self._session_msg_count += 1

        tease_kws = ["我回来了", "回来了", "好久不见", "我回来啦", "回来啦"]
        if any(kw in msg for kw in tease_kws):
            try:
                tease_reply = await asyncio.to_thread(generate_tease)
                if tease_reply:
                    save_last_chat_time()
                    if not self._is_system:
                        tid = add_chat_message("user", msg, character_id=self._character_id)
                        if tid:
                            _background_thread_pool.submit(add_sentence_vectors, tid, msg, "user", self._character_id)
                    add_chat_message("assistant", tease_reply, character_id=self._character_id)
                    await ws.send_text(json.dumps({"type": "token", "content": _clean_dsml(tease_reply)}))
                    await ws.send_text(json.dumps({"type": "done"}))
                    return
            except Exception as e:
                logger.warning(f"tease failed: {e}")

        # 彩蛋检查
        try:
            from core.easter_eggs import check_easter_egg, check_holiday
            egg = check_easter_egg(msg) or check_holiday()
            if egg:
                self._easter_egg_msg = egg
        except Exception:
            pass

        # 纠错检测：若用户在纠正 AI 的事实错误 → 记录到 correction_memory
        try:
            from core.correction_memory import detect_correction, record_correction
            prev_ai = ""
            if history:
                for h in reversed(history):
                    if h.get("role") == "assistant" and h.get("content"):
                        prev_ai = h["content"]
                        break
            correction = detect_correction(msg, prev_ai)
            if correction:
                _background_thread_pool.submit(
                    record_correction,
                    msg, prev_ai,
                    correction["wrong_pattern"],
                    correction["corrected_fact"],
                    correction["trigger_keywords"],
                    self._character_id,
                )
                logger.info(f"[纠错] 检测到纠正: wrong={correction['wrong_pattern'][:30]} correct={correction['corrected_fact'][:30]}")
        except Exception:
            pass

        # 反讽检测：影响 relationship（已接 user_message 分支）和人格演化（_rule_sarcasm_penalty）
        # 不再写入 feedback_memory —— 反讽是用户当下情绪，不是给 AI 的行为规则
        # AI 看到"用户反讽: 呵呵"会困惑要改什么，反而增加 prompt 噪声
        try:
            from core.emotion_patterns import is_sarcastic
            if is_sarcastic(msg):
                logger.info(f"[反讽] 检测到阴阳怪气，已通过 relationship 调整 + sarcasm_penalty 处理")
        except Exception:
            pass

        # 提及计数：用户消息中的关键短语 → mention_weights（跨组件复用）
        try:
            from core.mention_tracker import record_mention
            _background_thread_pool.submit(record_mention, msg, self._character_id)

        # 反讽惩罚：每 50 条检查反讽率 → agreeableness 微降
        if self._session_msg_count % 50 == 0 and self._session_msg_count > 0:
            from core.emotion_evolution import _rule_sarcasm_penalty
            _background_thread_pool.submit(_rule_sarcasm_penalty, self._character_id)

        except Exception:
            pass

        save_last_chat_time()

        if not self._is_system:
            uid = add_chat_message("user", msg, character_id=self._character_id)
            if uid:
                _background_thread_pool.submit(add_sentence_vectors, uid, msg, "user", self._character_id)

        await self._analyze_context(history, hours_since or 0)
        await self._build_and_send(history, hours_since or 0)

    async def _analyze_context(self, history, hours_since):
        """Run sentiment analysis + intent detection + empathy strategy"""
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

        # 以下为非阻塞的后台任务（情感记录、好感调整、共情策略）
        if not self._is_system:
            _background_thread_pool.submit(self._post_analysis_bg, sr, hours_since)

    def _post_analysis_bg(self, sr: dict, hours_since: float):
        """后台：情感记录 + 好感调整 + 共情策略（不阻塞响应）"""
        try:
            record_emotion(self.emotion, character_id=self._character_id)
            adjust_relationship(sentiment_result=sr, hours_since_last=hours_since, character_id=self._character_id, user_message=self.user_message)
        except Exception as e:
            logger.warning(f"emotion: {e}")

        try:
            from api.sentiment import get_contextual_strategy
            from core.relationship import get_relationship
            aff, _ = get_relationship(character_id=self._character_id)
            strategy = get_contextual_strategy(sr.get("emotion_subtype", "neutral"), sr.get("context_keyword"), aff, self.consecutive_negative)
            if strategy:
                self._conn_empathy_strategy = strategy
        except Exception as e:
            logger.warning(f"[sent] 共情策略获取失败: {e}")

    async def _check_dedup(self, msg):
        """Deduplicate repeated messages (per-connection cache)"""
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
        """Build system prompt, assemble messages, start LLM streaming"""
        ws = self.ws
        msg = self.user_message
        it = self.intent_type

        kh, rag = _build_rag_context(msg, self._is_system)
        summaries = get_active_tiered_summaries(character_id=self._character_id)
        kps = get_all_active_keypoints(character_id=self._character_id)
        pc = (get_profile_context(character_id=self._character_id) or "")
        fc = get_facts_context(character_id=self._character_id) or ""
        if pc and fc:
            pc += "\n" + fc
        elif fc:
            pc = fc
        ups = get_user_patterns()
        sm = get_config("sentence_mode", "auto")

        provider = get_provider()
        from core.character_card import resolve_config
        api_key = resolve_config("api_key", "", self._character_id)
        if not api_key and resolve_config("api_provider", "", self._character_id) != "ollama" and provider.name not in ("ollama",):
            await ws.send_text(json.dumps({"type": "error", "content": "configure API Key"}))
            return

        ts = datetime.now().strftime("%Y-%m-%d %H:%M")
        dedup = await self._check_dedup(msg)

        sp, dc, de = build_system_prompt(current_time_str=ts, emotion=self.emotion, user_message=msg, rag_context=rag, tiered_summaries=summaries, keypoints=kps, custom_context=pc, user_patterns=ups, sentence_mode=sm, chat_history=history, character_id=self._character_id)

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
            except Exception as e:
                logger.warning(f"[build] 目标追踪加载失败: {e}")
                pass
        if self._is_system:
            dc += "\n[short system reply]"

        msgs = [{"role": "system", "content": sp}, {"role": "system", "content": dc}]

        # 注入角色卡 mes_example 到对话历史
        try:
            from core.character_card import CharacterCard
            active_card = CharacterCard.get_active()
            if active_card and active_card.mes_example:
                msgs.append({"role": "system", "content": f"【对话示例】\n{active_card.mes_example}"})
        except Exception:
            pass

        try:
            from core.db import get_chat_conn
            conn = get_chat_conn(self._character_id)
            rows = conn.execute(
                "SELECT role, content FROM chat_history ORDER BY id DESC LIMIT 16"
            ).fetchall()
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
                    if pos <= len(msgs):
                        msgs.insert(pos, {"role": "system", "content": c})

        # SmartCrusher：消息列表超出字符上限时压缩早期对话
        msgs = _compress_conversation_context(msgs, max_chars=40000)

        dc2 = build_dynamic_context(ts, self.emotion, self._idle_minutes, character_id=self._character_id)
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

        # 彩蛋消息注入
        if hasattr(self, '_easter_egg_msg') and self._easter_egg_msg:
            user_content = f"[彩蛋提示：在回复开头自然地说「{self._easter_egg_msg}」]\n" + user_content
            self._easter_egg_msg = None


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
        """Stream LLM response, handle tool calls, fallback"""
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
                gen = p.chat_stream(messages, temperature=tool_temp, max_tokens=4096, tools=OPENAI_TOOLS, tool_choice="auto", **extra_kwargs)
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
                    await ws.send_text(json.dumps({"type": "token", "content": t}))
                    continue
                ut = parser.feed(t)
                if ut is not None:
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

        await self._process_reply(full_reply, parser, fallback)

    async def _handle_tool_calls(self, messages, tc_buf):
        """Execute tool calls and send brief confirmation"""
        ws = self.ws
        p = get_provider()
        tool_results = []
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
            if isinstance(result, str):
                tool_results.append(f"[{fn}]: {result[:200]}")

        try:
            c = p.chat(messages, temperature=0.3, max_tokens=300) or "done."
            for m in ["【思考】", "【回复】"]:
                if m in c:
                    c = c.split(m)[-1].strip()
            await ws.send_text(json.dumps({"type": "token", "content": c}))
        except Exception as e:
            logger.error(f"tool LLM: {e}")
            # LLM 总结失败时，直接给用户看工具原始结果
            c = "\n".join(tool_results) if tool_results else "（工具执行完成）"
            await ws.send_text(json.dumps({"type": "token", "content": c}))

        await ws.send_text(json.dumps({"type": "done"}))
        set_config("_dropped_context", "")
        await self._save_response(c, True)

    async def _process_reply(self, full_reply, parser, fallback):
        """Parse tags, save response, trigger background tasks"""
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
                        add_chat_message("system", f, character_id=self._character_id)

            rm = get_config("relationship_mode", "fast")
            if rm in ("auto", "semi-auto"):
                import re as _rr
                am = _rr.search(r"<aff:([+-]?\d+(?:\.\d+)?)>", content)
                tm = _rr.search(r"<trust:([+-]?\d+(?:\.\d+)?)>", content)
                if am or tm:
                    ad = float(am.group(1)) if am else 0
                    td = float(tm.group(1)) if tm else 0
                    if abs(ad) > 0.001 or abs(td) > 0.001:
                        adjust_relationship(sentiment_result={"relationship_impact": ad, "target": "ai", "intent": "statement", "sentiment": "neutral"}, character_id=self._character_id, user_message=self.user_message)
                    content = _rr.sub(r"<aff:[+-]?\d+(?:\.\d+)?>", "", content)
                    content = _rr.sub(r"<trust:[+-]?\d+(?:\.\d+)?>", "", content).strip()

        # 人格一致性检查（启发式同步，LLM 异步）
        if not self._is_system and content:
            try:
                from core.consistency_checker import _heuristic_check, _memory_consistency_check
                # 启发式检查（0ms）
                heuristic_fix = _heuristic_check(self.user_message, content)
                if heuristic_fix:
                    content = heuristic_fix
                # 记忆一致性（0ms，仅记录）
                _memory_consistency_check(content)
                # LLM 深度检查降级为后台（不阻塞响应）
                _background_thread_pool.submit(
                    self._async_consistency_check, content
                )
            except Exception:
                pass

        await self._save_response(content)

        # 情感检测（用于前端表情显示）
        emotion = _detect_reply_emotion(content)

        await ws.send_text(json.dumps({"type": "done", "_system": self._is_system, "emotion": emotion}))
        set_config("_dropped_context", "")
        if self._is_system and content:
            await ws.send_text(json.dumps({"type": "toast", "content": content.strip()[:120]}))

        if not self._is_system:
            mc = increment_msg_counter(character_id=self._character_id)
            loop = asyncio.get_running_loop()
            # 用户活跃统计
            _background_thread_pool.submit(record_user_activity_hour)
            _background_thread_pool.submit(_trigger_daily_evolution)
            _background_thread_pool.submit(_calc_consecutive_days, mc, self.ws, loop)
            _background_thread_pool.submit(_maybe_surprise, self.ws, loop)
            _background_thread_pool.submit(_check_goal_completion, content, self._character_id)
            # 里程碑检查（需开启 milestones feature）
            try:
                from core.character_card import CharacterCard
                if CharacterCard.is_feature_enabled("milestones"):
                    from core.relationship import check_milestone
                    char_name = ""
                    active = CharacterCard.get_active()
                    if active:
                        char_name = active.name
                    milestone = check_milestone(char_name, character_id=self._character_id)
                    if milestone:
                        _background_thread_pool.submit(add_chat_message, "system", milestone, character_id=self._character_id)
            except Exception:
                pass

            # 三级摘要后台任务（per-character：衰减/摘要生成/关键词/反思/巩固）
            try:
                from core.summary_engine import run_background_tasks
                _background_thread_pool.submit(run_background_tasks, mc, self.user_message, self._character_id)
            except Exception as e:
                silent_exc("后台摘要任务", e)
            # 记忆整理（每 8 轮自动提取事实，per-character）
            if mc > 0 and mc % 8 == 0:
                _background_thread_pool.submit(_run_memory_curation, self.history, self._character_id)
            # 共同经历检测
            try:
                from core.shared_memory import detect_moment, record_shared_moment
                moment_type = detect_moment(self.user_message, content)
                if moment_type:
                    _background_thread_pool.submit(record_shared_moment, content[:100], moment_type)
            except Exception as e:
                silent_exc("共同经历检测", e)
            if parser and hasattr(parser, "extract_demand"):
                d = parser.extract_demand()
                if d and d.get("level", "") not in ("LITERAL", "UNKNOWN"):
                    _background_thread_pool.submit(save_demand_record, d, self.user_message)
            _background_thread_pool.submit(self._extract_knowledge_graph, content)
        # 每轮提取实体 + 用语
        try:
            from core.memory_provider import MemoryProvider
            provider = MemoryProvider()
            provider.extract_entities_from_text(self.user_message, self._character_id)
            provider.extract_vocabulary_from_text(self.user_message, self._character_id)
        except Exception as e:
            silent_exc("实体/用语提取", e)
        # 结论分析：每 30 条消息执行一次（AI 对用户行为模式的总结）
        if self._session_msg_count > 0 and self._session_msg_count % 30 == 0:
            try:
                from core.conclusion_engine import run_conclusion_analysis
                _background_thread_pool.submit(run_conclusion_analysis)
            except Exception as e:
                silent_exc("结论分析", e)
            # TempMemory 批量巩固：每 30 条消息后台提取一次（不用等到每日 4:30）
            try:
                from core.memory_provider import batch_extract_memories
                _background_thread_pool.submit(batch_extract_memories, self._character_id, 5)
            except Exception as e:
                silent_exc("TempMemory 巩固", e)
        # 需求模式提炼：每 50 条消息执行一次（LLM 分析用户深层需求）
        if self._session_msg_count > 0 and self._session_msg_count % 50 == 0:
            _background_thread_pool.submit(_run_demand_pattern_extraction)
        # TempMemory：暂存本轮对话供后续批量巩固
        try:
            from core.memory_provider import save_temp_conversation
            _background_thread_pool.submit(save_temp_conversation, self._character_id, self.user_message, content)
        except Exception as e:
            silent_exc("TempMemory 暂存", e)

    async def _save_response(self, content, is_tool_response=False):
        """Save AI response to chat_history and vector store"""
        if not content:
            return
        self._last_ai_msg_id = None
        ss = fallback_split(content)
        if ss:
            for i, s in enumerate(ss):
                msg_id = add_chat_message("assistant", _clean_dsml(s), character_id=self._character_id)
                self._last_ai_msg_id = msg_id
                if is_model_ready() and not self._is_game_event:
                    add_message_vector(f"as_{datetime.now().timestamp()}_{i}", s, {"role": "assistant"})
        else:
            self._last_ai_msg_id = add_chat_message("assistant", _clean_dsml(content), character_id=self._character_id)
            if is_model_ready() and not self._is_game_event:
                add_message_vector(f"as_{datetime.now().timestamp()}", content, {"role": "assistant"})

    def _extract_knowledge_graph(self, content):
        """Background: extract triples from user+AI exchange (per-character)"""
        if not content or len(content) < 20:
            return
        try:
            user_msg = getattr(self, "user_message", "") or ""
            combined = f"用户: {user_msg}\nAI: {content}"
            from core.knowledge_graph import extract_triples_from_text
            extract_triples_from_text(combined, source="chat", character_id=self._character_id)
        except Exception as e:
            logger.warning(f"[kg] 知识图谱提取失败: {e}")
            pass

    def _async_consistency_check(self, content: str):
        """后台：LLM 一致性检查（不阻塞响应，修正结果写回 chat_history）"""
        try:
            from core.consistency_checker import _should_llm_check, reflect_response
            if not _should_llm_check(content):
                return
            persona = ""
            try:
                from core.character_card import CharacterCard
                card = CharacterCard.get_active()
                if card and card.system_prompt:
                    persona = card.system_prompt
            except Exception:
                pass
            if not persona:
                persona = get_config("custom_system_prompt", "")
            if persona:
                refined = reflect_response(self.user_message, content, persona, character_id=self._character_id)
                if refined and refined != content:
                    logger.info(f"[一致性] 后台修正: {refined[:60]}...")
                    if self._last_ai_msg_id:
                        from core.db.chat import update_chat_message
                        update_chat_message(self._last_ai_msg_id, _clean_dsml(refined), character_id=self._character_id)
                        logger.info(f"[一致性] 已更新消息 #{self._last_ai_msg_id}")
        except Exception:
            pass

    async def _fallback_reply(self):
        """Fallback when streaming produces no response"""
        ws = self.ws
        p = get_provider()
        from core.db import get_chat_conn
        conn = get_chat_conn(self._character_id)
        rows = conn.execute(
            "SELECT role, content FROM chat_history ORDER BY id DESC LIMIT 8"
        ).fetchall()
        msgs = [dict(r) for r in reversed(rows)]
        try:
            handled, new_reply, content = await try_fallback_reply(
                ws, msgs, [], "", self._is_system, None, character_id=self._character_id,
            )
            if handled:
                if content:
                    await self._save_response(content)
            else:
                await ws.send_text(json.dumps({"type": "error", "content": "reply failed"}))
        except Exception as e:
            logger.error(f"fallback: {e}")
            await ws.send_text(json.dumps({"type": "error", "content": "reply failed"}))


async def _schedule_proactive(delay_seconds, ws, character_id=0):
    await asyncio.sleep(delay_seconds)
    try:
        from core.db import get_chat_conn
        from core.character_card import get_active_character_id
        _cid = character_id or get_active_character_id()
        conn = get_chat_conn(character_id)
        rows = conn.execute(
            "SELECT role FROM chat_history ORDER BY id DESC LIMIT 2"
        ).fetchall()
        if rows and rows[0]["role"] == "user":
            return
        from api.greeting import generate_proactive
        msg = await asyncio.to_thread(generate_proactive, "proactive_tag", {})
        if msg:
            add_chat_message("assistant", msg, character_id=_cid)
            await ws.send_text(json.dumps({"type": "proactive", "content": msg}))
    except Exception as e:
        logger.warning(f"proactive: {e}")
