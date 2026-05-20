from fastapi import APIRouter
from core.db import get_active_summary, get_active_keypoints, reset_active_memory, get_last_summary, get_messages_since_last_summary
from pydantic import BaseModel
from typing import List

router = APIRouter(prefix="/summary", tags=["summary"])

class SummaryResponse(BaseModel):
    summary: str
    keypoints: List[str]

@router.get("/active")
async def get_active():
    return SummaryResponse(
        summary=get_active_summary(),
        keypoints=get_active_keypoints()
    )

@router.get("/status")
async def summary_status():
    last = get_last_summary()
    pending = get_messages_since_last_summary()
    return {
        "last_summary": last["summary"] if last else None,
        "last_summary_time": last["created_at"] if last else None,
        "pending_messages": len(pending),
        "threshold": 10
    }

@router.post("/reset")
async def reset_memory():
    reset_active_memory()
    return {"status": "ok"}