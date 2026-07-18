"""收藏管理 API — 提供消息收藏、取消收藏和收藏状态查询等功能（per-character）。"""
from fastapi import APIRouter, Query
from core.db import get_favorites, add_favorite, remove_favorite, is_favorite, get_chat_conn
import logging
from core.retry import silent_exc
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/favorites", tags=["favorites"])

@router.get("/")
async def list_favorites(character_id: int = Query(0, description="角色 ID，默认 0")):
    """获取收藏的消息列表（per-character）。"""
    return get_favorites(character_id=character_id)

@router.post("/{msg_id}")
async def favorite_message(msg_id: int,
                          character_id: int = Query(0, description="角色 ID，默认 0")):
    """收藏指定消息（per-character）"""
    with get_chat_conn(character_id) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT content, role, timestamp FROM chat_history WHERE id = ?", (msg_id,))
        row = cursor.fetchone()
    if not row:
        return {"ok": False, "message": "消息不存在"}
    add_favorite(msg_id, row["content"], row["role"], row["timestamp"], character_id=character_id)
    return {"ok": True}

@router.delete("/{msg_id}")
async def unfavorite_message(msg_id: int,
                            character_id: int = Query(0, description="角色 ID，默认 0")):
    """取消收藏指定消息（per-character）。"""
    remove_favorite(msg_id, character_id=character_id)
    return {"ok": True}

@router.get("/check/{msg_id}")
async def check_favorite(msg_id: int,
                        character_id: int = Query(0, description="角色 ID，默认 0")):
    """检查指定消息是否已收藏（per-character）。"""
    return {"is_favorite": is_favorite(msg_id, character_id=character_id)}
