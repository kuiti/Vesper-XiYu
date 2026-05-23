from fastapi import APIRouter
from pydantic import BaseModel
from core.db import get_conn
from datetime import datetime

router = APIRouter(prefix="/schedule", tags=["schedule"])


class ScheduleCreate(BaseModel):
    title: str
    description: str = ""
    start_time: str
    end_time: str = ""
    location: str = ""
    all_day: int = 0
    color: str = "#5390d4"


@router.get("/")
async def list_schedule():
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM schedule ORDER BY start_time")
        rows = cursor.fetchall()
    return [{"id": r["id"], "title": r["title"], "description": r["description"],
             "start_time": r["start_time"], "end_time": r["end_time"],
             "location": r["location"], "all_day": r["all_day"], "color": r["color"]} for r in rows]


@router.post("/")
async def create_schedule(item: ScheduleCreate):
    # 先创建提醒（避免日程入库后提醒失败导致不一致）
    if item.start_time:
        try:
            from core.db import add_reminder
            t = datetime.fromisoformat(item.start_time)
            add_reminder(f"日程: {item.title}", t.isoformat(), level=4)
        except Exception as e:
            print(f"[日程] 自动创建提醒失败: {e}")
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO schedule (title, description, start_time, end_time, location, all_day, color) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (item.title, item.description, item.start_time, item.end_time, item.location, item.all_day, item.color)
        )
        sched_id = cursor.lastrowid
    return {"status": "ok", "id": sched_id}


@router.delete("/{sched_id}")
async def delete_schedule(sched_id: int):
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM schedule WHERE id = ?", (sched_id,))
    return {"status": "ok"}
