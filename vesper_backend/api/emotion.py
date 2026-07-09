"""情绪追踪 API — 提供情绪趋势、今日情绪、情绪摘要、性格画像和情感事件日志等功能。"""
# api/emotion.py — 情绪趋势 + 演化 API（per-character）
from fastapi import APIRouter, Query
from core.emotion_tracker import get_emotion_trend, get_today_emotion, get_emotion_summary
from core.relationship import get_relationship, get_ai_emotion, AI_EMOTIONS

router = APIRouter(prefix="/emotion", tags=["emotion"])


@router.get("/trend")
async def emotion_trend(days: int = Query(7, ge=1, le=90), character_id: int = Query(0, ge=0)):
    """获取最近 N 天的情绪趋势（per-character）"""
    return {"trend": get_emotion_trend(days, character_id)}


@router.get("/today")
async def emotion_today(character_id: int = Query(0, ge=0)):
    """获取今日情绪状态（per-character）"""
    return get_today_emotion(character_id)


@router.get("/summary")
async def emotion_summary(character_id: int = Query(0, ge=0)):
    """获取情绪摘要文本（per-character）"""
    return {"summary": get_emotion_summary(character_id)}


@router.get("/relationship")
async def emotion_relationship(character_id: int = Query(0, ge=0)):
    """当前关系状态（per-character）"""
    affection, trust = get_relationship(character_id)
    ai_emotion = get_ai_emotion(character_id)
    info = AI_EMOTIONS.get(ai_emotion, AI_EMOTIONS["neutral"])
    return {
        "affection": affection,
        "trust": trust,
        "ai_emotion": ai_emotion,
        "ai_emotion_label": info["label"],
        "ai_emotion_description": info["description"]
    }


@router.get("/timeline")
async def emotion_timeline(days: int = Query(30, ge=7, le=90), character_id: int = Query(0, ge=0)):
    """情绪时间线（每日趋势 + AI情绪 + 关键事件，per-character）"""
    from core.emotion_evolution import get_emotion_timeline
    return get_emotion_timeline(days, character_id)


@router.get("/profile")
async def emotion_profile(character_id: int = Query(0, ge=0)):
    """AI 性格画像（per-character）"""
    from core.emotion_evolution import get_trait_profile
    return get_trait_profile(character_id)


@router.get("/events")
async def emotion_events(limit: int = Query(50, ge=1, le=200),
                         character_id: int = Query(0, description="角色 ID，默认 0")):
    """情感事件日志（per-character）"""
    from core.db import get_chat_conn
    with get_chat_conn(character_id) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT timestamp, event_type, affection_delta, trust_delta, affection_after, trust_after, ai_emotion_after, reason FROM emotion_log ORDER BY timestamp DESC LIMIT ?",
            (limit,)
        )
        rows = cursor.fetchall()
    return {"events": [dict(r) for r in rows]}
