# api/emotion.py — 情绪趋势 API
from fastapi import APIRouter, Query
from core.emotion_tracker import get_emotion_trend, get_today_emotion, get_emotion_summary

router = APIRouter(prefix="/emotion", tags=["emotion"])


@router.get("/trend")
async def emotion_trend(days: int = Query(7, ge=1, le=90)):
    """获取最近 N 天的情绪趋势"""
    return {"trend": get_emotion_trend(days)}


@router.get("/today")
async def emotion_today():
    """获取今日情绪状态"""
    return get_today_emotion()


@router.get("/summary")
async def emotion_summary():
    """获取情绪摘要文本"""
    return {"summary": get_emotion_summary()}
