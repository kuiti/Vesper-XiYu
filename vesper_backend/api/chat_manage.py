"""聊天记录管理 API 模块（per-character）。
所有操作需要 character_id 参数路由到正确的角色库。
"""

# version: 5.0.0
import logging

from fastapi import APIRouter, BackgroundTasks, Query
from core.db import delete_chat_history_between, delete_chat_history_older_than, set_config, get_config, reset_active_memory, get_chat_conn
from pydantic import BaseModel
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat/manage", tags=["chat"])

class DateRange(BaseModel):
    start: str
    end: str

class CleanupSettings(BaseModel):
    days: int

def _clear_vectors():
    """重建所有向量索引（清除旧数据后）"""
    try:
        from core.vector_store import rebuild_all_vectors
        rebuild_all_vectors()
    except Exception as e:
        logger.warning(f"[向量清理] 异常: {e}")

@router.delete("/range")
async def delete_range(range: DateRange, bg: BackgroundTasks,
                       character_id: int = Query(0, description="角色 ID")):
    """按日期范围批量删除聊天记录（per-character）"""
    try:
        for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
            try:
                start_iso = datetime.strptime(range.start, fmt).isoformat()
                break
            except ValueError:
                continue
        else:
            raise ValueError(f"无法解析日期: {range.start}")
        for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
            try:
                end_iso = datetime.strptime(range.end, fmt).isoformat()
                break
            except ValueError:
                continue
        else:
            raise ValueError(f"无法解析日期: {range.end}")
        if len(range.end) <= 10:
            end_iso = datetime.strptime(range.end, "%Y-%m-%d").replace(hour=23, minute=59, second=59).isoformat()
    except ValueError:
        from fastapi.responses import JSONResponse
        return JSONResponse({"detail": "日期格式无效，需为 YYYY-MM-DD"}, status_code=400)
    count = delete_chat_history_between(start_iso, end_iso, character_id=character_id)
    if count > 0:
        reset_active_memory()
        bg.add_task(_clear_vectors)
    return {"deleted": count, "character_id": character_id}

@router.delete("/recent/{minutes}")
async def delete_recent(minutes: int, bg: BackgroundTasks,
                        character_id: int = Query(0, description="角色 ID")):
    """删除最近N分钟内的消息（per-character）"""
    now = datetime.now()
    cutoff = (now - timedelta(minutes=minutes)).isoformat()
    count = delete_chat_history_between(cutoff, now.isoformat(), character_id=character_id)
    if count > 0:
        reset_active_memory()
        bg.add_task(_clear_vectors)
    return {"deleted": count, "character_id": character_id}

@router.delete("/message/{msg_id}")
async def delete_message(msg_id: int,
                         character_id: int = Query(0, description="角色 ID")):
    """删除单条消息（per-character）"""
    from core.vector_store import delete_message_vectors
    with get_chat_conn(character_id) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM chat_history WHERE id = ?", (msg_id,))
        cursor.execute("DELETE FROM chat_fts WHERE rowid = ?", (msg_id,))
    # sentence_index 有 character_id 列，按角色删除
    from core.db import get_conn as _main_conn
    with _main_conn() as conn:
        conn.cursor().execute("DELETE FROM sentence_index WHERE character_id = ? AND msg_id = ?", (character_id, msg_id))
    reset_active_memory()
    delete_message_vectors(msg_id, character_id=character_id)
    return {"status": "ok", "character_id": character_id}

@router.delete("/older-than/{days}")
async def delete_older_than(days: int, bg: BackgroundTasks,
                            character_id: int = Query(0, description="角色 ID")):
    """删除指定天数之前的聊天记录（per-character）"""
    delete_chat_history_older_than(days, character_id=character_id)
    reset_active_memory()
    bg.add_task(_clear_vectors)
    return {"status": "ok", "character_id": character_id}

@router.delete("/all")
async def delete_all(bg: BackgroundTasks,
                     character_id: int = Query(0, description="角色 ID，默认 0 清空所有角色")):
    """清空聊天记录（per-character，character_id=0 时清空所有角色）"""
    from core.db import clear_chat_history
    if character_id:
        clear_chat_history(character_id=character_id)
    else:
        # 遍历所有角色清空
        clear_chat_history()
        from core.character_card import CharacterCard
        for c in CharacterCard.list_all():
            try:
                clear_chat_history(character_id=c.get("id", 0))
            except Exception:
                pass
    bg.add_task(_clear_vectors)
    return {"status": "ok", "character_id": character_id}

@router.get("/cleanup-settings")
async def get_cleanup_settings():
    """获取自动清理天数配置"""
    return {"auto_cleanup_days": get_config("auto_cleanup_days", 30)}

@router.post("/cleanup-settings")
async def set_cleanup_settings(settings: CleanupSettings):
    """设置自动清理天数"""
    set_config("auto_cleanup_days", settings.days)
    return {"status": "ok"}