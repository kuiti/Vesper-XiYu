"""情景记忆 API —— 按时间线浏览和搜索过往对话片段。"""
from fastapi import APIRouter
from core.episodic_memory import get_episode_timeline, recall_episode

router = APIRouter(prefix="/episodes", tags=["episodes"])


@router.get("/timeline")
async def timeline(days: int = 7):
    """获取最近 N 天的情景记忆时间线"""
    return get_episode_timeline(days)


@router.get("/search")
async def search(q: str, limit: int = 3):
    """按关键词搜索情景记忆"""
    return recall_episode(q, limit)
