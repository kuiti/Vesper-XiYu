"""习惯追踪 API —— 每日习惯的创建、打卡、连续天数管理。"""
from fastapi import APIRouter, HTTPException
from core.db import get_habits, add_habit, update_habit, delete_habit, reset_habits_daily
from pydantic import BaseModel
from typing import List

router = APIRouter(prefix="/habits", tags=["habits"])

class HabitCreate(BaseModel):
    name: str

class HabitUpdate(BaseModel):
    checked: bool
    streak: int = 0

class HabitOut(BaseModel):
    id: int
    name: str
    checked: int
    streak: int
    date: str
    created: str

@router.get("/", response_model=List[dict])
async def list_habits():
    """获取今日习惯列表（自动重置跨日状态）"""
    reset_habits_daily()
    return get_habits()

@router.post("/")
async def create_habit(habit: HabitCreate):
    """创建新习惯"""
    if not habit.name.strip():
        raise HTTPException(400, "习惯名称不能为空")
    add_habit(habit.name.strip())
    return {"status": "ok"}

@router.patch("/{habit_id}")
async def patch_habit(habit_id: int, update: HabitUpdate):
    """更新习惯打卡状态和连续天数"""
    update_habit(habit_id, update.checked, update.streak)
    return {"status": "ok"}

@router.delete("/{habit_id}")
async def remove_habit(habit_id: int):
    """删除习惯"""
    if not delete_habit(habit_id):
        raise HTTPException(404, "习惯不存在")
    return {"status": "ok"}
