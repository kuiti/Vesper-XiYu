"""用户画像 API — 提供画像查看、更新、删除和自动提取等功能。"""
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
    """获取当前用户画像。"""
    return {"profile": get_profile()}


@router.post("/")
async def update_profile(item: ProfileItem):
    """更新单条画像字段。"""
    save_profile({item.key: item.value})
    return {"status": "ok"}


@router.delete("/{key}")
async def delete_profile_item(key: str):
    """删除指定 key 的画像字段。"""
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM user_profile WHERE key = ?", (key,))
    clear_profile_cache()
    return {"status": "ok"}


@router.post("/extract")
async def trigger_extraction():
    """手动触发从聊天记录中提取用户画像。"""
    await asyncio.to_thread(extract_profile_from_messages)
    return {"status": "ok"}
