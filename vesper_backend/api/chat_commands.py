"""聊天命令处理模块。

处理 /welcome、/tease、/reroll 等斜杠命令，websocket 作为显式参数传入。
"""

import asyncio
import json
import re
import logging
from datetime import datetime, timedelta
from fastapi import WebSocket
from core.db import (
    get_config, set_config, add_chat_message,
    reroll_last_ai_message, reroll_from_message,
)
from api.chat_tasks import _clean_dsml
from api.greeting import generate_greeting, generate_tease, save_last_welcome

logger = logging.getLogger(__name__)


async def handle_welcome(websocket: WebSocket, character_id: int = 0):
    """处理 /welcome 命令"""
    try:
        greeting = await asyncio.to_thread(generate_greeting)
        if greeting:
            add_chat_message("assistant", _clean_dsml(greeting), character_id=character_id)
            await websocket.send_text(json.dumps({"type": "greeting", "content": greeting}))
            save_last_welcome()
        else:
            await websocket.send_text(json.dumps({"type": "token", "content": "欢迎回来～"}))
    except Exception as e:
        await websocket.send_text(json.dumps({"type": "token", "content": "欢迎回来～（生成失败）"}))
        logger.warning(f"[welcome] 错误: {e}")
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


async def handle_reroll(websocket: WebSocket, character_id: int = 0):
    """处理 /reroll 命令，返回 (user_message, should_skip)"""
    try:
        last_usr = reroll_last_ai_message(character_id=character_id)
        if last_usr:
            await websocket.send_text(json.dumps({"type": "reroll_start", "content": "重新生成中..."}))
            return last_usr, False
        else:
            await websocket.send_text(json.dumps({"type": "token", "content": "没有可以重新生成的消息"}))
            await websocket.send_text(json.dumps({"type": "done"}))
            return None, True
    except Exception as e:
        await websocket.send_text(json.dumps({"type": "token", "content": f"重生成出错: {e}"}))
        await websocket.send_text(json.dumps({"type": "done"}))
        return None, True


async def handle_reroll_from(websocket: WebSocket, msg_id: int, character_id: int = 0):
    """处理 /reroll_from:<msg_id> 命令，返回 (user_message, should_skip)"""
    try:
        last_usr = reroll_from_message(msg_id, character_id=character_id)
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

