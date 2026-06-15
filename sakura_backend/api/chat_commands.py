# api/chat_commands.py  |  命令处理函数
# 从 chat.py 拆出的命令处理逻辑，websocket 作为显式参数传入

import asyncio
import json
import re
from datetime import datetime, timedelta
from fastapi import WebSocket
from core.db import (
    get_config, set_config, add_chat_message,
    reroll_last_ai_message, reroll_from_message,
    add_reminder, get_reminders,
)
from api.chat_tasks import _clean_dsml
from api.greeting import generate_greeting, generate_tease, save_last_welcome


async def handle_welcome(websocket: WebSocket):
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
        await websocket.send_text(json.dumps({"type": "token", "content": "欢迎回来～（生成失败）"}))
        print(f"[welcome] 错误: {e}")
    await websocket.send_text(json.dumps({"type": "done"}))


async def handle_tease(websocket: WebSocket):
    """处理 /tease 命令"""
    import asyncio
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


async def handle_reroll(websocket: WebSocket):
    """处理 /reroll 命令，返回 (user_message, should_continue)"""
    try:
        last_usr = reroll_last_ai_message()
        if last_usr:
            await websocket.send_text(json.dumps({"type": "reroll_start", "content": "重新生成中..."}))
            return last_usr, False  # user_message, don't continue
        else:
            await websocket.send_text(json.dumps({"type": "token", "content": "没有可以重新生成的消息"}))
            await websocket.send_text(json.dumps({"type": "done"}))
            return None, True  # skip this message
    except Exception as e:
        await websocket.send_text(json.dumps({"type": "token", "content": f"重生成出错: {e}"}))
        await websocket.send_text(json.dumps({"type": "done"}))
        return None, True


async def handle_reroll_from(websocket: WebSocket, msg_id: int):
    """处理 /reroll_from:<msg_id> 命令，返回 (user_message, should_continue)"""
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


async def handle_remind(websocket: WebSocket, msg: str):
    """处理 /remind 命令，格式：/remind 明天9点 记得吃药"""
    try:
        content = msg[7:].strip()  # 去掉 /remind
        if not content:
            await websocket.send_text(json.dumps({"type": "token", "content": "用法：/remind 时间 内容，如 /remind 明天9点 记得吃药"}))
            await websocket.send_text(json.dumps({"type": "done"}))
            return
        # 简单的时间解析
        now = datetime.now()
        target_time = None
        remain_content = content

        # 解析具体时间并校验范围
        def _parse_time(hour_str, minute_str="0"):
            h, mi = int(hour_str), int(minute_str)
            if not (0 <= h <= 23 and 0 <= mi <= 59):
                return None
            return h, mi

        # N分钟后匹配（支持 "1小时后" 简写为 "1时"）
        m = re.match(r'(\d+)分钟后?\s*(.*)', content)
        if m:
            target_time = now + timedelta(minutes=int(m.group(1)))
            remain_content = m.group(2) or ''
        # 明天/今天 N点[M分] [上午/下午]
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
            await websocket.send_text(json.dumps({"type": "token", "content": "无法识别时间，示例: /remind 明天9点 记得吃药"}))
            await websocket.send_text(json.dumps({"type": "done"}))
            return

        add_reminder(remain_content or "提醒事项", target_time.isoformat(), 4)
        time_str = target_time.strftime("%m月%d日 %H:%M")
        await websocket.send_text(json.dumps({"type": "token", "content": f"✅ 已设定提醒：{time_str} — {remain_content or '提醒事项'}"}))
        # 立刻发一次提醒列表更新
        all_active = [r for r in get_reminders() if not r.get("done")]
        await websocket.send_text(json.dumps({"type": "reminder_count", "count": len(all_active)}))
    except Exception as e:
        await websocket.send_text(json.dumps({"type": "token", "content": f"提醒设置失败: {e}"}))
    await websocket.send_text(json.dumps({"type": "done"}))