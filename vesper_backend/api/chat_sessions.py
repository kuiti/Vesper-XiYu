"""多会话管理 API 模块。

提供会话的创建、切换、删除、重命名等 REST 接口。
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from core.db import (
    list_sessions, create_session, switch_session,
    delete_session, rename_session, get_active_session_id,
    get_all_chat_messages,
)
from core.character_card import get_active_character_id

router = APIRouter(prefix="/chat/sessions", tags=["chat-sessions"])


class SessionCreate(BaseModel):
    name: str = "新对话"


class SessionRename(BaseModel):
    name: str


@router.get("/")
async def get_sessions():
    """列出当前角色的所有会话"""
    cid = get_active_character_id()
    sessions = list_sessions(character_id=cid)
    active_id = get_active_session_id(character_id=cid)
    return {"sessions": sessions, "active_id": active_id}


@router.post("/")
async def create_new_session(data: SessionCreate):
    """创建新会话"""
    cid = get_active_character_id()
    sid = create_session(name=data.name, character_id=cid)
    return {"status": "ok", "session_id": sid}


@router.post("/{session_id}/switch")
async def switch_to_session(session_id: int):
    """切换到指定会话"""
    cid = get_active_character_id()
    switch_session(session_id, character_id=cid)
    messages = get_all_chat_messages(character_id=cid, session_id=session_id)
    return {"status": "ok", "session_id": session_id, "messages": messages}


@router.delete("/{session_id}")
async def delete_existing_session(session_id: int):
    """删除会话及其消息"""
    cid = get_active_character_id()
    # 不允许删除最后一个 session
    sessions = list_sessions(character_id=cid)
    if len(sessions) <= 1:
        raise HTTPException(400, "不能删除最后一个会话")
    delete_session(session_id, character_id=cid)
    return {"status": "ok"}


@router.put("/{session_id}/rename")
async def rename_existing_session(session_id: int, data: SessionRename):
    """重命名会话"""
    cid = get_active_character_id()
    rename_session(session_id, data.name, character_id=cid)
    return {"status": "ok"}
