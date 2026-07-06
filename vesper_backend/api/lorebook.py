"""知识库 API —— 世界观/设定条目的增删改查与匹配测试。"""
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
from core.lorebook import lorebook_manager

router = APIRouter(prefix="/lorebook", tags=["lorebook"])


class LorebookCreate(BaseModel):
    keys: list[str]
    content: str
    priority: int = 5
    position: str = "after_persona"
    logic: str = "AND_ANY"
    group_name: str = ""
    probability: int = 100
    sticky: int = 0
    cooldown: int = 0
    scope: str = "global"
    character_name: str = ""
    enabled: bool = True


class LorebookUpdate(BaseModel):
    keys: Optional[list[str]] = None
    content: Optional[str] = None
    priority: Optional[int] = None
    position: Optional[str] = None
    logic: Optional[str] = None
    group_name: Optional[str] = None
    probability: Optional[int] = None
    sticky: Optional[int] = None
    cooldown: Optional[int] = None
    scope: Optional[str] = None
    character_name: Optional[str] = None
    enabled: Optional[bool] = None


@router.get("/")
async def list_entries(scope: str = None):
    """获取所有知识条目（可按 scope 过滤）"""
    return {"entries": lorebook_manager.list_entries(scope)}


@router.get("/{entry_id}")
async def get_entry(entry_id: int):
    """根据 ID 获取单个知识条目"""
    entry = lorebook_manager.get_entry(entry_id)
    if not entry:
        return {"status": "error", "message": "条目不存在"}
    return {"entry": entry}


@router.post("/")
async def create_entry(data: LorebookCreate):
    """创建新的知识条目"""
    entry_id = lorebook_manager.add_entry(
        keys=data.keys, content=data.content,
        priority=data.priority, position=data.position,
        logic=data.logic, group_name=data.group_name,
        probability=data.probability, sticky=data.sticky,
        cooldown=data.cooldown, scope=data.scope,
        character_name=data.character_name, enabled=data.enabled,
    )
    return {"status": "ok", "id": entry_id}


@router.put("/{entry_id}")
async def update_entry(entry_id: int, data: LorebookUpdate):
    """更新知识条目（仅传入需要修改的字段）"""
    kwargs = {k: v for k, v in data.model_dump(exclude_none=True).items()}
    if not kwargs:
        return {"status": "error", "message": "没有要更新的字段"}
    ok = lorebook_manager.update_entry(entry_id, **kwargs)
    if not ok:
        return {"status": "error", "message": "更新失败"}
    return {"status": "ok"}


@router.delete("/{entry_id}")
async def delete_entry(entry_id: int):
    """删除知识条目"""
    lorebook_manager.delete_entry(entry_id)
    return {"status": "ok"}


@router.post("/test")
async def test_match(message: str, scope: str = "global"):
    """测试消息匹配了哪些知识条目"""
    results = lorebook_manager.match_entries(message, scope=scope)
    return {"matched": results}
