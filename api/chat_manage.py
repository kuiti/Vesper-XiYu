# version: 3.8.1
from fastapi import APIRouter, BackgroundTasks
from core.db import delete_chat_history_between, delete_chat_history_older_than, set_config, get_config, reset_active_memory, get_db_connection
from pydantic import BaseModel
from datetime import datetime, timedelta

router = APIRouter(prefix="/chat/manage", tags=["chat"])

class DateRange(BaseModel):
    start: str
    end: str

class CleanupSettings(BaseModel):
    days: int

def _clear_vectors():
    try:
        from core.vector_store import rebuild_all_vectors
        rebuild_all_vectors()
    except:
        pass

@router.delete("/range")
async def delete_range(range: DateRange, bg: BackgroundTasks):
    start_iso = datetime.strptime(range.start, "%Y-%m-%d").isoformat()
    end_iso = datetime.strptime(range.end, "%Y-%m-%d").replace(hour=23, minute=59, second=59).isoformat()
    count = delete_chat_history_between(start_iso, end_iso)
    if count > 0:
        reset_active_memory()
        bg.add_task(_clear_vectors)
    return {"deleted": count}

@router.delete("/recent/{minutes}")
async def delete_recent(minutes: int, bg: BackgroundTasks):
    """删除最近N分钟内的消息"""
    now = datetime.now()
    cutoff = (now - timedelta(minutes=minutes)).isoformat()
    count = delete_chat_history_between(cutoff, now.isoformat())
    if count > 0:
        reset_active_memory()
        bg.add_task(_clear_vectors)
    return {"deleted": count}

@router.delete("/message/{msg_id}")
async def delete_message(msg_id: int, bg: BackgroundTasks):
    """删除单条消息"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM chat_history WHERE id = ?", (msg_id,))
    cursor.execute("DELETE FROM chat_fts WHERE rowid = ?", (msg_id,))
    conn.commit()
    conn.close()
    reset_active_memory()
    bg.add_task(_clear_vectors)
    return {"status": "ok"}

@router.delete("/older-than/{days}")
async def delete_older_than(days: int, bg: BackgroundTasks):
    delete_chat_history_older_than(days)
    reset_active_memory()
    bg.add_task(_clear_vectors)
    return {"status": "ok"}

@router.delete("/all")
async def delete_all(bg: BackgroundTasks):
    from core.db import clear_chat_history
    clear_chat_history()
    reset_active_memory()
    bg.add_task(_clear_vectors)
    return {"status": "ok"}

@router.get("/cleanup-settings")
async def get_cleanup_settings():
    return {"auto_cleanup_days": get_config("auto_cleanup_days", 30)}

@router.post("/cleanup-settings")
async def set_cleanup_settings(settings: CleanupSettings):
    set_config("auto_cleanup_days", settings.days)
    return {"status": "ok"}