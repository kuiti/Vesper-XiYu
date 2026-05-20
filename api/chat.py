# version: 3.9.0
import json
import requests
import threading
import asyncio
from fastapi import WebSocket, WebSocketDisconnect
from core.db import (
    get_config, get_memory, get_active_summary, get_active_keypoints,
    add_chat_message, set_config, add_summary, get_last_summary,
    get_messages_since_last_summary, get_reminders, update_reminder_last_reminded,
    update_reminder_done
)
from core.prompt_builder import build_system_prompt
from api.intent import detect_intent
from api.greeting import generate_greeting, generate_tease, save_last_welcome, load_last_welcome, save_last_chat_time, get_time_gap_hours
from api.split_sentences import fallback_split
from core.vector_store import add_message_vector, search_similar, is_model_ready
from datetime import datetime
import random as _random

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

SUMMARY_THRESHOLD = 10
_summary_lock = threading.Lock()

def generate_and_save_summary():
    """生成并保存新的摘要（后台线程）"""
    # 非阻塞获取锁：如果已有摘要任务在运行则静默跳过，避免堆积
    if not _summary_lock.acquire(blocking=False):
        return
    try:
        new_msgs = get_messages_since_last_summary()
        if len(new_msgs) < SUMMARY_THRESHOLD:
            return
        msgs_to_summarize = new_msgs[-30:] if len(new_msgs) > 30 else new_msgs
        conv_text = "\n".join([f"{m['role']}: {m['content']}" for m in msgs_to_summarize])
        api_key = get_config("api_key", "")
        if not api_key:
            return
        prompt = f"""请总结以下对话，输出 JSON 格式：
{{
    "summary": "一句话总结对话内容（100字以内）",
    "key_points": ["关键信息1", "关键信息2"]
}}
对话：
{conv_text}"""
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        payload = {
            "model": "deepseek-chat",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.5,
            "max_tokens": 500
        }
        resp = requests.post("https://api.deepseek.com/v1/chat/completions", headers=headers, json=payload, timeout=30)
        resp.raise_for_status()
        result = ""
        result = resp.json()["choices"][0]["message"]["content"]
        result = result.strip()
        # 剥离 LLM 输出的 markdown 代码块标记（格式不稳定，可能不带）
        for prefix in ['```json', '```']:
            if result.startswith(prefix):
                result = result[len(prefix):].strip()
        for suffix in ['```']:
            if result.endswith(suffix):
                result = result[:-len(suffix)].strip()
        data = json.loads(result)
        summary_text = data.get("summary", "")
        key_points_list = data.get("key_points", [])
        if summary_text:
            start_time = msgs_to_summarize[0]["timestamp"] if msgs_to_summarize else datetime.now().isoformat()
            end_time = msgs_to_summarize[-1]["timestamp"] if msgs_to_summarize else datetime.now().isoformat()
            add_summary(start_time, end_time, summary_text, key_points_list)
            print(f"[摘要] 已更新: {summary_text[:80]}...")
    except json.JSONDecodeError as e:
        print(f"[摘要] JSON 解析失败: {e} | 原始返回: {result[:200] if result else 'N/A'}")
    except Exception as e:
        print(f"[摘要] 生成失败: {type(e).__name__}: {e}")
    finally:
        _summary_lock.release()

async def chat_websocket(websocket: WebSocket):
    await websocket.accept()
    print("WebSocket 客户端已连接")
    
    # 欢迎语
    hours_gone = get_time_gap_hours()
    last_welcome = load_last_welcome()
    welcome_interval_ok = (last_welcome is None) or ((datetime.now() - last_welcome).total_seconds() / 3600 >= 0.5)
    if hours_gone is not None and hours_gone >= 0.5 and welcome_interval_ok:
        greeting = generate_greeting()
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
                for r in check_reminders():
                    await websocket.send_text(json.dumps({"type": "reminder", "data": r}))
        except asyncio.CancelledError:
            raise
        except Exception:
            pass
    reminder_task = asyncio.create_task(reminder_loop())

    msg_count = 0
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

            # ─── 强制命令（不更新聊天时间、不进入记录、不被 AI 记忆） ───
            if user_message.startswith("/welcome"):
                try:
                    # 临时将 last_chat 设为旧时间绕过 generate_greeting 的 hours_gone 检查。
                    # 备份→覆盖→生成→恢复流程存在风险：若中间抛异常，原始数据可能丢失。
                    import os as _os2
                    lc_file = "data/last_chat.json"
                    lc_backup = None
                    if _os2.path.exists(lc_file):
                        with open(lc_file, 'r', encoding='utf-8') as f:
                            lc_backup = f.read()
                    with open(lc_file, 'w', encoding='utf-8') as f:
                        f.write('{"last_time": "2000-01-01T00:00:00"}')
                    greeting = generate_greeting()
                    if lc_backup:
                        with open(lc_file, 'w', encoding='utf-8') as f:
                            f.write(lc_backup)
                    elif _os2.path.exists(lc_file):
                        _os2.remove(lc_file)
                    if greeting:
                        await websocket.send_text(json.dumps({"type": "greeting", "content": greeting}))
                        save_last_welcome()
                    else:
                        await websocket.send_text(json.dumps({"type": "token", "content": "欢迎回来～"}))
                except Exception as e:
                    await websocket.send_text(json.dumps({"type": "token", "content": f"欢迎回来～（生成失败）"}))
                    print(f"[welcome] 错误: {e}")
                await websocket.send_text(json.dumps({"type": "done"}))
                continue
            if user_message.startswith("/tease"):
                from core.db import set_config as _set_config
                from datetime import timedelta
                _old_prob = get_config("current_tease_probability", 30)
                _set_config("current_tease_probability", 100)
                try:
                    import os as _os
                    old_file = "data/last_chat.json"
                    old_backup = None
                    if _os.path.exists(old_file):
                        with open(old_file, 'r', encoding='utf-8') as f:
                            old_backup = f.read()
                    with open(old_file, 'w', encoding='utf-8') as f:
                        f.write('{"last_time": "' + (datetime.now() - timedelta(hours=1)).isoformat() + '"}')
                    tease_reply = generate_tease()
                    if old_backup:
                        with open(old_file, 'w', encoding='utf-8') as f:
                            f.write(old_backup)
                    elif _os.path.exists(old_file):
                        _os.remove(old_file)
                    if tease_reply:
                        await websocket.send_text(json.dumps({"type": "token", "content": tease_reply}))
                    else:
                        await websocket.send_text(json.dumps({"type": "token", "content": "（调侃生成失败，请稍后再试）"}))
                except Exception as e:
                    await websocket.send_text(json.dumps({"type": "token", "content": f"（调侃出错: {e}）"}))
                finally:
                    _set_config("current_tease_probability", _old_prob)
                await websocket.send_text(json.dumps({"type": "done"}))
                continue

            # 正常消息才更新最后聊天时间
            save_last_chat_time()

            # 调侃
            tease_keywords = ["我回来了", "回来了", "好久不见", "我回来啦", "回来啦"]
            if any(kw in user_message for kw in tease_keywords):
                try:
                    tease_reply = generate_tease()
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
            msg_count += 1

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
                emotion = "neutral"
                intent_type, intent_data = detect_intent(user_message)
                print(f"[意图检测] type={intent_type}, data={intent_data}")
                rag_context = ""
                if is_model_ready():
                    try:
                        similar_docs = search_similar(user_message, top_k=3)
                        if similar_docs:
                            rag_lines = []
                            for doc, dist in similar_docs:
                                if len(doc) > 300:
                                    doc = doc[:300] + "..."
                                rag_lines.append(f"- {doc}")
                            rag_context = "\n".join(rag_lines)
                    except Exception as e:
                        print(f"向量检索失败: {e}")

                summary = get_active_summary()
                keypoints = get_active_keypoints()
                system_prompt = build_system_prompt(
                    current_time_str=current_time_str,
                    emotion=emotion,
                    user_message=user_message,
                    rag_context=rag_context,
                    summary=summary,
                    keypoints=keypoints
                )

                messages = [{"role": "system", "content": system_prompt}]
                messages.extend(history[-20:])

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

                headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
                # 事实型意图用低温(0.3)减少幻觉，创意对话用高温(0.65)增加变化
                tool_temp = 0.3 if intent_type in ("weather", "location", "search") else 0.65
                payload = {
                    "model": "deepseek-chat",
                    "messages": messages,
                    "temperature": tool_temp,
                    "max_tokens": 2000,
                    "stream": True
                }

                # DeepSeek 专有参数 search=True，非 OpenAI 标准，切换 API 提供商时需移除此字段
                enable_ds_search = get_config("enable_deepseek_search", True)
                if enable_ds_search and intent_type in ("search",):
                    payload["search"] = True

                try:
                    full_reply = []
                    with requests.post("https://api.deepseek.com/v1/chat/completions", headers=headers, json=payload, stream=True, timeout=60) as response:
                        response.raise_for_status()
                        for line in response.iter_lines():
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
                                            full_reply.append(token)
                                            await websocket.send_text(json.dumps({"type": "token", "content": token}))
                                    except:
                                        pass
                        if full_reply:
                            assistant_content = "".join(full_reply)
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

                        if msg_count % SUMMARY_THRESHOLD == 0:
                            threading.Thread(target=generate_and_save_summary).start()
                except Exception as e:
                    print(f"[API] DeepSeek 请求失败: {type(e).__name__}: {e}")
                    await websocket.send_text(json.dumps({"type": "error", "content": "AI 服务请求失败，请稍后重试"}))
            except Exception as e:
                import traceback
                print(f"消息处理异常: {traceback.format_exc()}")
                await websocket.send_text(json.dumps({"type": "error", "content": f"出错: {e}"}))
    except WebSocketDisconnect:
        print("WebSocket 客户端断开")
    finally:
        reminder_task.cancel()