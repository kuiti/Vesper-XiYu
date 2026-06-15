# version: 5.0.0
import json
import random
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
    _build_rag_context,
)
from api.chat_parser import ThinkingParser  # 提取自本文件的解析类
from api.chat_commands import (
    handle_welcome, handle_tease, handle_reroll, handle_remind, handle_reroll_from,
)
from api.chat_loops import (
    reminder_loop,
    proactive_loop,
    diary_scheduler,
)
from api.weather_push import weather_scheduler, _push_weather, _broadcast_weather
from api.chat_fallback import try_fallback_reply

from datetime import datetime, timedelta
import logging
from core.retry import silent_exc
logger = logging.getLogger(__name__)

# 全局 WebSocket 连接追踪
_active_websockets: dict = {}  # {conn_id: websocket}
_active_websockets_lock = asyncio.Lock()  # 保护 _active_websockets 的并发访问
_diary_scheduler_started = False  # 日记调度器全局单例标志
# _latest_empathy_strategy 已改为 per-connection 变量 _conn_empathy_strategy

# 提醒规则：advance_minutes=提前多久开始提醒，repeat_interval=重复提醒间隔(分钟, None=只一次)
# level 7(强制): 目标时间后仍触发(now>target不跳过)，每30分钟重复
# level 1-6: 只在目标时间前 advance_minutes 窗口内触发
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

    reminder_task = asyncio.create_task(reminder_loop(websocket))

    # 主动问候：多条件触发 + AI 人格影响
    last_chat = load_last_chat_time()
    last_active = last_chat if last_chat else datetime.now()
    consecutive_negative = int(get_config("_consecutive_negative", "0"))
    session_triggered = set()  # 本会话已触发的主动类型

    proactive_task = asyncio.create_task(proactive_loop(
        websocket, last_active, consecutive_negative, session_triggered, _conn_empathy_strategy,
    ))
    global _diary_scheduler_started
    if not _diary_scheduler_started:
        _diary_scheduler_started = True
        diary_task = asyncio.create_task(diary_scheduler())
    else:
        diary_task = None

    # 命令处理函数从 api.chat_commands 导入

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
            # 检查是否有用户未回应的主动消息（从 DB 读取，支持 chat_loops 提取版）
            _proactive_raw = get_config("_proactive_context", "null")
            if _proactive_raw and _proactive_raw != "null":
                try:
                    _pc = json.loads(_proactive_raw)
                    ts = _pc["timestamp"]
                    if isinstance(ts, str):
                        ts = datetime.fromisoformat(ts)
                    elapsed = (datetime.now() - ts).total_seconds()
                    if elapsed < 600:
                        try:
                            mark_proactive_responded()
                        except Exception as e:
                            print(f"[主动] 标记回复失败: {e}")
                            pass
                        proactive_note = f"【主动对话上下文】你刚才主动问了用户：\"{_pc['content']}\"，用户现在回复了。请自然地延续这个话题，不要生硬切换。"
                    set_config("_proactive_context", "null")
                except Exception as e:
                    silent_exc("chat", e)

            # ─── /remind 命令 ───
            _cmd = user_message.split()[0] if user_message.split() else ""
            if _cmd == "/remind":
                await handle_remind(websocket, user_message)
                continue

            # ─── 强制命令 ───
            if _cmd == "/welcome":
                await handle_welcome(websocket)
                continue
            if _cmd == "/tease":
                await handle_tease(websocket)
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
                    user_message, skip = await handle_reroll_from(websocket, msg_id)
                except (ValueError, IndexError):
                    skip = True
                if skip:
                    continue
                history = history[:-2] if len(history) >= 2 else []
                _is_reroll = True
            elif _cmd_name == "/reroll":
                user_message, skip = await handle_reroll(websocket)
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
                    except Exception as e:
                        silent_exc("?", e)

                if not _is_system:
                    print(f"[意图检测] type={intent_type}, data={intent_data}")
                kb_title_hint, rag_context = _build_rag_context(user_message, _is_system)

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
                    except Exception as e:
                        silent_exc("?", e)
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
                                except Exception as e:
                                    silent_exc("_trim_history", e)
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
                            except Exception as e:
                                silent_exc("_has_emotion", e)

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
                        except Exception as e:
                            silent_exc("?", e)
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

                        if chunk["type"] == "done":
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
                        # 事件状态检测（每次用户消息都跑）
                        from core.profile_builder import track_event_completion, track_plan_intent, track_in_progress, clear_completed_plans
                        threading.Thread(target=track_event_completion, args=(original_user_message,), daemon=True).start()
                        threading.Thread(target=track_plan_intent, args=(original_user_message,), daemon=True).start()
                        threading.Thread(target=track_in_progress, args=(original_user_message,), daemon=True).start()
                        threading.Thread(target=clear_completed_plans, daemon=True).start()
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

                    # ─── 三阶段降级 ───
                    if not full_reply:
                        handled, full_reply, assistant_content = await try_fallback_reply(
                            websocket, messages, full_reply, assistant_content, _is_system, e
                        )
                        if handled:
                            continue

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
        except Exception as e:
            silent_exc("?", e)
        # diary_task 是全局任务，不在此取消（由 APScheduler 管理生命周期）


# ─── 天气定时推送调度器（已提取到 api/weather_push.py）───

