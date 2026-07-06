"""聊天历史 API — 提供按时间/日期查询消息、消息计数和日期分组等功能。"""
# version: 5.0.0
from fastapi import APIRouter, Query
from core.db import get_conn, get_chat_conn

router = APIRouter(prefix="/chat/history", tags=["chat"])

def _active_cid():
    from core.character_card import CharacterCard
    c = CharacterCard.get_active()
    return c._db_id if c and hasattr(c, '_db_id') else 0

@router.get("/")
async def get_history(
    limit: int = 50,
    after_id: int = Query(None, description="获取比此ID更旧的消息（用于加载更多）"),
    session_id: int = Query(0, description="指定会话 ID，0=当前活跃会话"),
):
    """分页获取聊天历史，支持指定会话和游标翻页。"""
    cid = _active_cid()
    if not session_id:
        from core.db import get_active_session_id
        session_id = get_active_session_id(character_id=cid)
    conn = get_chat_conn(cid)
    cursor = conn.cursor()
    if after_id:
        cursor.execute(
            "SELECT id, role, content, timestamp FROM chat_history WHERE session_id = ? AND id < ? ORDER BY id DESC LIMIT ?",
            (session_id, after_id, limit)
        )
    else:
        cursor.execute(
            "SELECT id, role, content, timestamp FROM chat_history WHERE session_id = ? ORDER BY id DESC LIMIT ?",
            (session_id, limit)
        )
    rows = cursor.fetchall()
    messages = [{"id": r["id"], "role": r["role"], "content": r["content"], "timestamp": r["timestamp"]} for r in rows]
    messages.reverse()
    next_after_id = messages[0]["id"] if messages else None
    return {"messages": messages, "next_after_id": next_after_id}

@router.get("/date")
async def get_history_by_date(date: str = Query(..., description="日期 YYYY-MM-DD")):
    """获取指定日期的所有聊天记录。"""
    with get_chat_conn(_active_cid()) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, role, content, timestamp FROM chat_history WHERE date(timestamp) = ? ORDER BY id",
            (date,)
        )
        rows = cursor.fetchall()
    messages = [{"id": r["id"], "role": r["role"], "content": r["content"], "timestamp": r["timestamp"]} for r in rows]
    return {"messages": messages}

@router.get("/count")
async def get_message_count():
    """获取当前会话的总消息条数。"""
    with get_chat_conn(_active_cid()) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM chat_history")
        count = cursor.fetchone()[0]
    return {"count": count}

@router.get("/dates")
async def get_message_dates():
    """返回有消息的所有日期及条数，按月份分组"""
    with get_chat_conn(_active_cid()) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT date(timestamp) as d, COUNT(*) as cnt
            FROM chat_history
            GROUP BY d
            ORDER BY d DESC
        """)
        rows = cursor.fetchall()
    # 按月份分组日期
    months = {}
    for r in rows:
        d = r["d"]
        month_key = d[:7]  # "2026-05"
        if month_key not in months:
            months[month_key] = {"month": month_key, "dates": []}
        months[month_key]["dates"].append({"date": d, "count": r["cnt"]})
    return {"months": list(months.values())}