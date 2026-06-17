# version: 5.0.0
from fastapi import WebSocket
import logging

logger = logging.getLogger(__name__)


async def chat_websocket(websocket: WebSocket):
    """WebSocket 聊天端点（委托给 ChatSession 管理）"""
    from api.chat_session import ChatSession
    session = ChatSession(websocket)
    await session.run()
