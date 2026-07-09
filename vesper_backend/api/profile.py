"""用户画像 API — 提供画像查看、更新、删除和自动提取等功能（per-character）。"""
import asyncio
from fastapi import APIRouter, Query
from pydantic import BaseModel
from core.profile_builder import get_profile, save_profile, extract_profile_from_messages, clear_profile_cache
from core.db import get_chat_conn

router = APIRouter(prefix="/profile", tags=["profile"])


class ProfileItem(BaseModel):
    key: str
    value: str


@router.get("/")
async def view_profile(character_id: int = Query(0, description="角色 ID，默认 0")):
    """获取指定角色的用户画像。"""
    return {"profile": get_profile(character_id=character_id)}


@router.post("/")
async def update_profile(item: ProfileItem,
                         character_id: int = Query(0, description="角色 ID，默认 0")):
    """更新指定角色的画像字段。"""
    save_profile({item.key: item.value}, character_id=character_id)
    return {"status": "ok"}


@router.delete("/{key}")
async def delete_profile_item(key: str,
                              character_id: int = Query(0, description="角色 ID，默认 0")):
    """删除指定角色指定 key 的画像字段。"""
    with get_chat_conn(character_id) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM user_profile WHERE key = ?", (key,))
    clear_profile_cache()
    return {"status": "ok"}


@router.post("/extract")
async def trigger_extraction(character_id: int = Query(0, description="角色 ID，默认 0")):
    """手动触发从聊天记录中提取指定角色的用户画像。"""
    await asyncio.to_thread(extract_profile_from_messages, character_id)
    return {"status": "ok"}
