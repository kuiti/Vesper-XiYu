# version: 5.0.0
from fastapi import APIRouter, Query
from core.db import get_conn

router = APIRouter(prefix="/chat/history", tags=["chat"])

@router.get("/")
async def get_history(
    limit: int = 50,
    after_id: int = Query(None, description="获取比此ID更旧的消息（用于加载更多）"),
):
    with get_conn() as conn:
        cursor = conn.cursor()
        if after_id:
            cursor.execute(
                "SELECT id, role, content, timestamp FROM chat_history WHERE id < ? ORDER BY id DESC LIMIT ?",
                (after_id, limit)
            )
        else:
            cursor.execute(
                "SELECT id, role, content, timestamp FROM chat_history ORDER BY id DESC LIMIT ?",
                (limit,)
            )
        rows = cursor.fetchall()
    messages = [{"id": r["id"], "role": r["role"], "content": r["content"], "timestamp": r["timestamp"]} for r in rows]
    messages.reverse()
    next_after_id = messages[0]["id"] if messages else None
    return {"messages": messages, "next_after_id": next_after_id}

@router.get("/date")
async def get_history_by_date(date: str = Query(..., description="日期 YYYY-MM-DD")):
    with get_conn() as conn:
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
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM chat_history")
        count = cursor.fetchone()[0]
    return {"count": count}

@router.get("/dates")
async def get_message_dates():
    """返回有消息的所有日期及条数，按月份分组"""
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT date(timestamp) as d, COUNT(*) as cnt
            FROM chat_history
            GROUP BY d
            ORDER BY d DESC
        """)
        rows = cursor.fetchall()
    months = {}
    for r in rows:
        d = r["d"]
        month_key = d[:7]  # "2026-05"
        if month_key not in months:
            months[month_key] = {"month": month_key, "dates": []}
        months[month_key]["dates"].append({"date": d, "count": r["cnt"]})
    return {"months": list(months.values())}