import asyncio
from fastapi import APIRouter
from pydantic import BaseModel
from core.profile_builder import get_profile, save_profile, extract_profile_from_messages, clear_profile_cache
from core.db import get_conn

router = APIRouter(prefix="/profile", tags=["profile"])


class ProfileItem(BaseModel):
    key: str
    value: str


@router.get("/")
async def view_profile():
    return {"profile": get_profile()}


@router.post("/")
async def update_profile(item: ProfileItem):
    save_profile({item.key: item.value})
    return {"status": "ok"}


@router.delete("/{key}")
async def delete_profile_item(key: str):
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM user_profile WHERE key = ?", (key,))
    clear_profile_cache()
    return {"status": "ok"}


@router.post("/extract")
async def trigger_extraction():
    await asyncio.to_thread(extract_profile_from_messages)
    return {"status": "ok"}
