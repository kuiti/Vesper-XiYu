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

@router.get("/milestones")
async def milestones():
    """关系里程碑状态"""
    from core.relationship import get_relationship
    affection, trust = get_relationship()
    all_milestones = [
        {"key": "affection_30", "type": "affection", "threshold": 30, "name": "初识", "desc": "好感度首次突破30", "unlocked": affection >= 30},
        {"key": "affection_50", "type": "affection", "threshold": 50, "name": "好感", "desc": "好感度首次突破50，佐仓开始对你产生亲近感", "unlocked": affection >= 50},
        {"key": "affection_70", "type": "affection", "threshold": 70, "name": "喜欢", "desc": "好感度首次突破70，佐仓已经很喜欢和你聊天了", "unlocked": affection >= 70},
        {"key": "affection_85", "type": "affection", "threshold": 85, "name": "依赖", "desc": "好感度首次突破85，佐仓开始依赖你的存在", "unlocked": affection >= 85},
        {"key": "trust_30", "type": "trust", "threshold": 30, "name": "信任萌芽", "desc": "信任度首次突破30", "unlocked": trust >= 30},
        {"key": "trust_50", "type": "trust", "threshold": 50, "name": "信赖", "desc": "信任度首次突破50，佐仓开始向你敞开心扉", "unlocked": trust >= 50},
        {"key": "trust_70", "type": "trust", "threshold": 70, "name": "深信", "desc": "信任度首次突破70，佐仓几乎完全信任你", "unlocked": trust >= 70},
        {"key": "trust_85", "type": "trust", "threshold": 85, "name": "托付", "desc": "信任度首次突破85，佐仓愿意把一切告诉你", "unlocked": trust >= 85},
    ]
    return {"milestones": all_milestones, "affection": round(affection, 1), "trust": round(trust, 1)}
