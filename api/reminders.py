# version: 3.8.1
from fastapi import APIRouter
from core.db import get_reminders, add_reminder, delete_reminder, update_reminder_done, update_reminder_last_reminded
from pydantic import BaseModel
from typing import List, Optional

router = APIRouter(prefix="/reminders", tags=["reminders"])

class ReminderCreate(BaseModel):
    content: str
    target_time: str
    level: int = 4

class ReminderOut(BaseModel):
    id: int
    content: str
    target_time: str
    level: int
    done: bool
    last_reminded: Optional[str] = None

@router.get("/", response_model=List[ReminderOut])
async def list_reminders():
    return get_reminders()

@router.post("/")
async def create_reminder(r: ReminderCreate):
    add_reminder(r.content, r.target_time, r.level)
    return {"status": "ok"}

@router.patch("/{rid}/done")
async def mark_done(rid: int):
    update_reminder_done(rid, True)
    return {"status": "ok"}

@router.patch("/{rid}/snooze")
async def snooze_reminder(rid: int):
    from datetime import datetime
    update_reminder_last_reminded(rid, datetime.now().isoformat())
    return {"status": "ok"}

@router.delete("/{rid}")
async def remove_reminder(rid: int):
    delete_reminder(rid)
    return {"status": "ok"}
