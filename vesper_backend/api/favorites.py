"""收藏管理 API — 提供消息收藏、取消收藏和收藏状态查询等功能。"""
from fastapi import APIRouter
from core.db import get_favorites, add_favorite, remove_favorite, is_favorite, get_conn
import logging
from core.retry import silent_exc
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/favorites", tags=["favorites"])

# 确保旧数据库有收藏表（启动时自动创建）
try:
    with get_conn() as _c:
        _c.execute('CREATE TABLE IF NOT EXISTS favorites (id INTEGER PRIMARY KEY AUTOINCREMENT, msg_id INTEGER UNIQUE, content TEXT, role TEXT, timestamp TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP)')
except Exception as e:
    silent_exc("favorites_init", e)

@router.get("/")
async def list_favorites():
    """获取所有收藏的消息列表。"""
    return get_favorites()

@router.post("/{msg_id}")
async def favorite_message(msg_id: int):
    """收藏指定消息，从聊天记录中获取内容并保存。"""
    # 需要从 chat_history 获取消息内容
    from core.db import get_conn
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT content, role, timestamp FROM chat_history WHERE id = ?", (msg_id,))
        row = cursor.fetchone()
    if not row:
        return {"ok": False, "message": "消息不存在"}
    add_favorite(msg_id, row["content"], row["role"], row["timestamp"])
    return {"ok": True}

@router.delete("/{msg_id}")
async def unfavorite_message(msg_id: int):
    """取消收藏指定消息。"""
    remove_favorite(msg_id)
    return {"ok": True}

@router.get("/check/{msg_id}")
async def check_favorite(msg_id: int):
    """检查指定消息是否已收藏。"""
    return {"is_favorite": is_favorite(msg_id)}
