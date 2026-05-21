# api/relationship.py — 好感度/信任度/AI情绪 API
from fastapi import APIRouter
from core.relationship import get_relationship, get_ai_emotion, reset_relationship, AI_EMOTIONS

router = APIRouter(prefix="/relationship", tags=["relationship"])


@router.get("/")
async def view_relationship():
    """获取当前好感度、信任度、AI情绪"""
    affection, trust = get_relationship()
    ai_emotion = get_ai_emotion()
    emotion_info = AI_EMOTIONS.get(ai_emotion, AI_EMOTIONS["neutral"])
    return {
        "affection": round(affection, 1),
        "trust": round(trust, 1),
        "ai_emotion": ai_emotion,
        "ai_emotion_label": emotion_info["label"],
        "ai_emotion_description": emotion_info["description"]
    }


@router.post("/reset")
async def reset():
    """重置好感度/信任度/AI情绪为初始值"""
    reset_relationship()
    return {"status": "ok", "message": "已重置为初始值"}
