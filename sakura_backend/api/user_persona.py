# api/user_persona.py — 用户身份 API
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
from core.user_persona import user_persona_manager

router = APIRouter(prefix="/user-personas", tags=["user-personas"])


class PersonaCreate(BaseModel):
    name: str
    description: str = ""
    avatar: str = ""
    is_default: bool = False


class PersonaUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    avatar: Optional[str] = None
    is_default: Optional[bool] = None


@router.get("/")
async def list_personas():
    return {"personas": user_persona_manager.list_personas()}


@router.get("/active")
async def get_active_persona():
    p = user_persona_manager.get_active_persona()
    if not p:
        return {"persona": None}
    return {"persona": p}


@router.get("/{persona_id}")
async def get_persona(persona_id: int):
    p = user_persona_manager.get_persona(persona_id)
    if not p:
        return {"status": "error", "message": "身份不存在"}
    return {"persona": p}


@router.post("/")
async def create_persona(data: PersonaCreate):
    persona_id = user_persona_manager.add_persona(
        name=data.name, description=data.description,
        avatar=data.avatar, is_default=data.is_default,
    )
    return {"status": "ok", "id": persona_id}


@router.put("/{persona_id}")
async def update_persona(persona_id: int, data: PersonaUpdate):
    kwargs = {k: v for k, v in data.model_dump(exclude_none=True).items()}
    if not kwargs:
        return {"status": "error", "message": "没有要更新的字段"}
    ok = user_persona_manager.update_persona(persona_id, **kwargs)
    if not ok:
        return {"status": "error", "message": "更新失败"}
    return {"status": "ok"}


@router.delete("/{persona_id}")
async def delete_persona(persona_id: int):
    user_persona_manager.delete_persona(persona_id)
    return {"status": "ok"}


@router.post("/{persona_id}/activate")
async def activate_persona(persona_id: int):
    ok = user_persona_manager.set_active(persona_id)
    if not ok:
        return {"status": "error", "message": "身份不存在"}
    return {"status": "ok"}
