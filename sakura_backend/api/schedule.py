from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, field_validator
from core.db import get_conn
from datetime import datetime

router = APIRouter(prefix="/schedule", tags=["schedule"])


class ScheduleCreate(BaseModel):
    title: str
    description: str = ""
    start_time: str

    @field_validator("start_time")
    @classmethod
    def validate_iso(cls, v: str) -> str:
        if v:
            try:
                # 处理 Z 后缀（Python < 3.11 需要）
                normalized = v.replace("Z", "+00:00")
                datetime.fromisoformat(normalized)
            except (ValueError, TypeError):
                raise ValueError(f"无效的 ISO 时间格式: {v}")
        return v
    end_time: str = ""
    location: str = ""
    all_day: int = 0
    color: str = "#5390d4"

    @field_validator("end_time")
    @classmethod
    def validate_end_time_iso(cls, v: str) -> str:
        if v:
            try:
                normalized = v.replace("Z", "+00:00")
                datetime.fromisoformat(normalized)
            except (ValueError, TypeError):
                raise ValueError(f"无效的 ISO 时间格式: {v}")
        return v


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
    # 先创建日程（保证主数据落库），成功后再补提醒（失败不影响日程）
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO schedule (title, description, start_time, end_time, location, all_day, color) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (item.title, item.description, item.start_time, item.end_time, item.location, item.all_day, item.color)
        )
        sched_id = cursor.lastrowid
    if item.start_time:
        try:
            from core.db import add_reminder
            t = datetime.fromisoformat(item.start_time)
            add_reminder(f"日程: {item.title}", t.isoformat(), level=4)
        except Exception as e:
            print(f"[日程] 自动创建提醒失败（日程已保存）: {e}")
    return {"status": "ok", "id": sched_id}


@router.delete("/{sched_id}")
async def delete_schedule(sched_id: int):
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM schedule WHERE id = ?", (sched_id,))
        if cursor.rowcount == 0:
            raise HTTPException(404, "日程不存在")
    return {"status": "ok"}
