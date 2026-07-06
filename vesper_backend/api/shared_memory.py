"""共同经历 API —— 查询与用户共享的重要时刻。"""
from fastapi import APIRouter
from core.shared_memory import get_shared_moments

router = APIRouter(prefix="/shared-moments", tags=["shared-moments"])


@router.get("/")
async def list_shared_moments(limit: int = 20):
    """获取共同经历列表"""
    return get_shared_moments(limit=limit)
