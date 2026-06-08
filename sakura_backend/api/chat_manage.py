# version: 5.0.0
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
    except Exception as e:
        print(f"[向量清理] 异常: {e}")

@router.delete("/range")
async def delete_range(range: DateRange, bg: BackgroundTasks):
    try:
        # 兼容 "YYYY-MM-DD" 和 "YYYY-MM-DDTHH:MM:SS" 两种格式
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
        # 如果是纯日期，end 默认补 23:59:59
        if len(range.end) <= 10:
            end_iso = datetime.strptime(range.end, "%Y-%m-%d").replace(hour=23, minute=59, second=59).isoformat()
    except ValueError:
        from fastapi.responses import JSONResponse
        return JSONResponse({"detail": "日期格式无效，需为 YYYY-MM-DD"}, status_code=400)
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
    from core.db import get_conn
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM chat_history WHERE id = ?", (msg_id,))
        cursor.execute("DELETE FROM chat_fts WHERE rowid = ?", (msg_id,))
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