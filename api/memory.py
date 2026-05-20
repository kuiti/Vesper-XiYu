from fastapi import APIRouter
from core.db import get_memory, set_memory, delete_memory
from pydantic import BaseModel
from typing import Dict

router = APIRouter(prefix="/memory", tags=["memory"])

class MemoryItem(BaseModel):
    key: str
    value: str

@router.get("/")
async def list_memory() -> Dict[str, str]:
    """获取所有手动记忆（过滤内部下划线开头的）"""
    all_mem = get_memory()
    # 只返回不以 _ 开头的（用户手动记忆）
    return {k: v for k, v in all_mem.items() if not k.startswith("_")}

@router.post("/")
async def add_memory(item: MemoryItem):
    set_memory(item.key, item.value)
    return {"status": "ok"}

@router.delete("/{key}")
async def remove_memory(key: str):
    delete_memory(key)
    return {"status": "ok"}