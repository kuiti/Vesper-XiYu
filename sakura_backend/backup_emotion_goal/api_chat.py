# version: 3.9.0
import json
import time
import requests
import threading
import asyncio
import uuid
from fastapi import WebSocket, WebSocketDisconnect
from core.db import (
    get_config, add_chat_message, set_config,
    reroll_last_ai_message, get_reminders, update_reminder_last_reminded,
    increment_msg_counter, get_active_tiered_summaries, get_all_active_keypoints
)
from core.prompt_builder import build_system_prompt
from core.summary_engine import run_background_tasks
from api.sentiment import analyze_sentiment
from api.intent import detect_intent
from core.profile_builder import get_profile_context, extract_profile_from_messages
from core.emotion_tracker import record_emotion
from core.relationship import adjust_relationship
from api.greeting import generate_greeting, generate_tease, save_last_welcome, load_last_welcome, save_last_chat_time, get_time_gap_hours
from api.split_sentences import fallback_split
from core.vector_store import add_message_vector, search_similar, search_knowledge_similar, is_model_ready
from core.demand_analyzer import save_demand_record, get_user_patterns, extract_patterns_via_llm
from datetime import datetime

# 全局 WebSocket 连接追踪
_active_websockets: dict = {}  # {conn_id: websocket}

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
                except Exception as e:
                    print(f"[提醒循环] 异常: {e}")
        except asyncio.CancelledError:
            raise
        except WebSocketDisconnect:
            pass
    reminder_task = asyncio.create_task(reminder_loop())

    # 主动问候：每5分钟检查，>=30分钟无消息时生成场景化问候，每小时最多1次
    last_active = datetime.now()
    last_proactive_time = None
    PROACTIVE_COOLDOWN = 60  # 冷却60分钟

    async def proactive_loop():
        nonlocal last_proactive_time
        try:
            while True:
                await asyncio.sleep(300)
                try:
                    idle_minutes = (datetime.now() - last_active).total_seconds() / 60
                    if idle_minutes >= 30:
                        now = datetime.now()
                        # 冷却检查
                        if last_proactive_time and (now - last_proactive_time).total_seconds() < PROACTIVE_COOLDOWN * 60:
                            continue
                        from api.greeting import generate_proactive
                        msg = await asyncio.to_thread(generate_proactive, round(idle_minutes))
                        if msg:
                            await websocket.send_text(json.dumps({"type": "proactive", "content": msg}))
                            last_proactive_time = now
                except Exception as e:
                    print(f"[主动问候循环] 异常: {e}")
        except asyncio.CancelledError:
            raise
        except WebSocketDisconnect:
            pass
    proactive_task = asyncio.create_task(proactive_loop())

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
            history = request.get("history", [])

            if not user_message:
                await websocket.send_text(json.dumps({"type": "error", "content": "消息不能为空"}))
                continue

            last_active = datetime.now()

            # ─── 强制命令（不更新聊天时间、不进入记录、不被 AI 记忆） ───
            if user_message.startswith("/welcome"):
                try:
                    # 临时把 last_chat 设为旧时间，绕过 generate_greeting 的 hours_gone 检查
                    import os as _os2
                    lc_file = "data/last_chat.json"
                    lc_backup = None
                    if _os2.path.exists(lc_file):
                        with open(lc_file, 'r', encoding='utf-8') as f:
                            lc_backup = f.read()
                    with open(lc_file, 'w', encoding='utf-8') as f:
                        f.write('{"last_time": "2000-01-01T00:00:00"}')
                    greeting = await asyncio.to_thread(generate_greeting)
                    if greeting:
                        await websocket.send_text(json.dumps({"type": "greeting", "content": greeting}))
                        save_last_welcome()
                    else:
                        await websocket.send_text(json.dumps({"type": "token", "content": "欢迎回来～"}))
                except Exception as e:
                    await websocket.send_text(json.dumps({"type": "token", "content": f"欢迎回来～（生成失败）"}))
                    print(f"[welcome] 错误: {e}")
                finally:
                    if lc_backup:
                        with open(lc_file, 'w', encoding='utf-8') as f:
                            f.write(lc_backup)
                    elif _os2.path.exists(lc_file):
                        _os2.remove(lc_file)
                await websocket.send_text(json.dumps({"type": "done"}))
                continue
            if user_message.startswith("/tease"):
                from core.db import set_config as _set_config
                from datetime import timedelta
                _old_prob = get_config("current_tease_probability", 30)
                _set_config("current_tease_probability", 100)
                _tease_file_backup = None
                _tease_file = "data/last_chat.json"
                try:
                    import os as _os
                    if _os.path.exists(_tease_file):
                        with open(_tease_file, 'r', encoding='utf-8') as f:
                            _tease_file_backup = f.read()
                    with open(_tease_file, 'w', encoding='utf-8') as f:
                        f.write('{"last_time": "' + (datetime.now() - timedelta(hours=1)).isoformat() + '"}')
                    tease_reply = await asyncio.to_thread(generate_tease)
                    if tease_reply:
                        await websocket.send_text(json.dumps({"type": "token", "content": tease_reply}))
                    else:
                        await websocket.send_text(json.dumps({"type": "token", "content": "（调侃生成失败，请稍后再试）"}))
                except Exception as e:
                    await websocket.send_text(json.dumps({"type": "token", "content": f"（调侃出错: {e}）"}))
                finally:
                    _set_config("current_tease_probability", _old_prob)
                    if _tease_file_backup:
                        with open(_tease_file, 'w', encoding='utf-8') as f:
                            f.write(_tease_file_backup)
                    elif _os.path.exists(_tease_file):
                        _os.remove(_tease_file)
                await websocket.send_text(json.dumps({"type": "done"}))
                continue
            if user_message.startswith("/reroll"):
                try:
                    last_usr = reroll_last_ai_message()
                    if last_usr:
                        await websocket.send_text(json.dumps({"type": "reroll_start", "content": "重新生成中..."}))
                        user_message = last_usr
                    else:
                        await websocket.send_text(json.dumps({"type": "token", "content": "没有可重新生成的消息"}))
                        await websocket.send_text(json.dumps({"type": "done"}))
                        continue
                except Exception as e:
                    await websocket.send_text(json.dumps({"type": "token", "content": f"重新生成出错: {e}"}))
                    await websocket.send_text(json.dumps({"type": "done"}))
                    continue

            # 正常消息才更新最后聊天时间
            save_last_chat_time()

            # 调侃
            tease_keywords = ["我回来了", "回来了", "好久不见", "我回来啦", "回来啦"]
            if any(kw in user_message for kw in tease_keywords):
                try:
                    tease_reply = await asyncio.to_thread(generate_tease)
                    if tease_reply:
                        add_chat_message("assistant", tease_reply)
                        await websocket.send_text(json.dumps({"type": "token", "content": tease_reply}))
                        await websocket.send_text(json.dumps({"type": "done"}))
                        continue
                except Exception as e:
                    print(f"调侃生成失败: {e}")

            add_chat_message("user", user_message)
            if is_model_ready():
                add_message_vector(f"user_{datetime.now().timestamp()}", user_message, {"role": "user"})
            msg_count = increment_msg_counter()

            try:
                # 检查并推送提醒（右侧弹窗）
                reminders = check_reminders()
                for r in reminders:
                    await websocket.send_text(json.dumps({"type": "reminder", "data": r}))

                # 正常对话
                api_key = get_config("api_key", "")
                if not api_key:
                    await websocket.send_text(json.dumps({"type": "error", "content": "请先配置 DeepSeek API Key"}))
                    continue

                current_time_str = datetime.now().strftime("%Y年%m月%d日 %H:%M")
                emotion = await asyncio.to_thread(analyze_sentiment, user_message)

                # 记录情绪 + 调整好感度/信任度
                record_emotion(emotion)
                hours_since = get_time_gap_hours() or 0
                adjust_relationship(emotion=emotion, user_message=user_message, hours_since_last=hours_since)

                intent_type, intent_data = await asyncio.to_thread(detect_intent, user_message)
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
                system_prompt = build_system_prompt(
                    current_time_str=current_time_str,
                    emotion=emotion,
                    user_message=user_message,
                    rag_context=rag_context,
                    tiered_summaries=active_summaries,
                    keypoints=keypoints,
                    custom_context=profile_context,
                    user_patterns=user_patterns
                )

                messages = [{"role": "system", "content": system_prompt}]
                messages.extend(history[-35:])

                # 保存原始消息（后续注入会覆写 user_message）
                original_user_message = user_message

                # 工具数据以自然口语嵌入，不破坏聊天氛围
                if intent_type == "weather" and intent_data:
                    weather_instruction = "【天气回复要求：气温和天气状况必须说出；湿度、体感温度、气压、风向风速、云量、能见度、露点等要素中随机选2-4个自然提及；风向和风速必须同时出现或同时省略。角色语气只决定措辞风格。】"
                    user_message = f"{weather_instruction}\n（刚帮你看了下{intent_data['city']}：{intent_data['text']}）\n\n{user_message}"
                elif intent_type == "location" and intent_data:
                    city_name = f"{intent_data.get('province','')}{intent_data.get('city','')}"
                    user_message = f"（定位显示你现在在{city_name}）\n\n{user_message}"
                elif intent_type == "search" and intent_data:
                    user_message = f"（搜到了这些：{intent_data}）\n\n{user_message}"

                messages.append({"role": "user", "content": user_message})

                base_url = get_config("api_base_url", "https://api.deepseek.com/v1").rstrip("/")
                model = get_config("api_model", "deepseek-chat")
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
                        # 有 reply 内容则用 reply（排除思考部分），否则降级用全量
                        assistant_content = parser.reply if parser.reply else "".join(full_reply)
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

                    # 需求记录保存（后台线程，用原始消息避免意图注入数据污染）
                    if demand and demand.get("level", "UNKNOWN") not in ("LITERAL", "UNKNOWN"):
                        threading.Thread(target=save_demand_record, args=(demand, original_user_message)).start()

                    # 衰减 + 提及 + 三级摘要生成（后台线程）
                    threading.Thread(target=run_background_tasks, args=(msg_count, user_message)).start()
                    if msg_count % 20 == 0:
                        threading.Thread(target=extract_profile_from_messages).start()
                    # 每 50 条消息，后台提炼需求模式
                    if msg_count % 50 == 0:
                        threading.Thread(target=extract_patterns_via_llm).start()
                except Exception as e:
                    print(f"[API] AI 请求失败: {type(e).__name__}: {e}")
                    await websocket.send_text(json.dumps({"type": "error", "content": "AI 服务请求失败，请稍后重试"}))
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


# ─── 天气定时推送调度器 ───
WEATHER_NOTIFICATION_FILE = "data/weather_notification.json"

async def weather_scheduler():
    """全局天气定时推送（7:00, 12:00, 19:00）"""
    last_push_hour = -1
    while True:
        await asyncio.sleep(60)
        if not get_config("use_weather_care", True):
            continue
        now = datetime.now()
        hour, minute = now.hour, now.minute
        if minute == 0 and hour in (7, 12, 19) and hour != last_push_hour:
            last_push_hour = hour
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