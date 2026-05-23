# api/emotion.py — 情绪趋势 + 演化 API
from fastapi import APIRouter, Query
from core.emotion_tracker import get_emotion_trend, get_today_emotion, get_emotion_summary
from core.relationship import get_relationship, get_ai_emotion, AI_EMOTIONS

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


@router.get("/relationship")
async def emotion_relationship():
    """当前关系状态"""
    affection, trust = get_relationship()
    ai_emotion = get_ai_emotion()
    info = AI_EMOTIONS.get(ai_emotion, AI_EMOTIONS["neutral"])
    return {
        "affection": affection,
        "trust": trust,
        "ai_emotion": ai_emotion,
        "ai_emotion_label": info["label"],
        "ai_emotion_description": info["description"]
    }


@router.get("/timeline")
async def emotion_timeline(days: int = Query(30, ge=7, le=90)):
    """情绪时间线（每日趋势 + AI情绪 + 关键事件）"""
    from core.emotion_evolution import get_emotion_timeline
    return get_emotion_timeline(days)


@router.get("/profile")
async def emotion_profile():
    """AI 性格画像"""
    from core.emotion_evolution import get_trait_profile
    return get_trait_profile()


@router.get("/events")
async def emotion_events(limit: int = Query(50, ge=1, le=200)):
    """情感事件日志"""
    from core.db import get_conn
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT timestamp, event_type, affection_delta, trust_delta, affection_after, trust_after, ai_emotion_after, reason FROM emotion_log ORDER BY timestamp DESC LIMIT ?",
            (limit,)
        )
        rows = cursor.fetchall()
    return {"events": [dict(r) for r in rows]}
