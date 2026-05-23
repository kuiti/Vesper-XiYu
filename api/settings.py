# version: 5.0.0
from fastapi import APIRouter
from core.db import get_config, set_config, get_presets, save_preset, delete_preset
from pydantic import BaseModel
from typing import Any, Dict

router = APIRouter(prefix="/settings", tags=["settings"])

class ConfigUpdate(BaseModel):
    key: str
    value: Any

class PresetData(BaseModel):
    name: str
    data: dict

PERSONALITY_KEY_MAP = {
    "length_level": "length",
    "recall_past": "recall",
    "allow_emotion": "allow_emotion",
    "personality_tone": "tone",
}

@router.get("/")
async def get_all_settings() -> Dict[str, Any]:
    personality = get_config("personality", {})
    if not isinstance(personality, dict):
        personality = {}
    return {
        "has_api_key": bool(get_config("api_key", "")),
        "api_provider": get_config("api_provider", ""),
        "model_mode": get_config("model_mode", "auto"),
        "api_base_url": get_config("api_base_url", "https://api.deepseek.com/v1"),
        "api_model": get_config("api_model", "deepseek-chat"),
        "length_level": personality.get("length") if personality.get("length") is not None else get_config("length_level", "短"),
        "recall_past": personality.get("recall") if personality.get("recall") is not None else get_config("recall_past", "从不"),
        "allow_emotion": personality.get("allow_emotion") if personality.get("allow_emotion") is not None else get_config("allow_emotion", True),
        "custom_system_prompt": get_config("custom_system_prompt", ""),
        "personality_tone": personality.get("tone", "冷静"),
        "theme": get_config("theme", "dark"),
        "enable_web_search": get_config("enable_web_search", True),
        "auto_cleanup_days": get_config("auto_cleanup_days", 30),
        "default_city": get_config("default_city", ""),
        "has_amap_key": bool(get_config("amap_key", "")),
        "user_name": get_config("user_name", "我"),
        "ai_name": get_config("ai_name", "佐仓"),
        "precise_city": get_config("precise_city", ""),
        "primary_color": get_config("primary_color", "#6a9fd8"),
        "bg_color": get_config("bg_color", "#0f1119"),
        "sidebar_bg": get_config("sidebar_bg", "#161927"),
        "chat_bg": get_config("chat_bg", "#0f1119"),
        "user_bubble": get_config("user_bubble", "#1d3557"),
        "ai_bubble": get_config("ai_bubble", "#181e2b"),
        "tts_enabled": get_config("voice", {}).get("tts_enabled", True),
        "stt_enabled": get_config("voice", {}).get("stt_enabled", True),
        "auto_play_voice": get_config("voice", {}).get("auto_play", False),
        "use_system_notification": get_config("use_system_notification", False),
        "notification_style": get_config("notification_style", "warm"),
        "use_weather_care": get_config("use_weather_care", True),
        "show_tray_notification": get_config("show_tray_notification", True),
        "relationship_mode": get_config("relationship_mode", "fast"),
        "sentence_mode": get_config("sentence_mode", "auto"),
        "chat_font_size": get_config("chat_font_size", 14),
        "proactive_frequency": get_config("proactive_frequency", "medium"),
        "proactive_style": get_config("proactive_style", "warm"),
        "chat_bg_image": get_config("chat_bg_image", ""),
        "bg_opacity": get_config("bg_opacity", 1),
        "bg_blur": get_config("bg_blur", 0),
        "bg_mode": get_config("bg_mode", "cover"),
        "pin_enabled": get_config("pin_enabled", False),
        "pin_code": get_config("pin_code", ""),
        "quick_phrases": get_config("quick_phrases", "[]"),
    }

@router.post("/relationship-mode")
async def set_relationship_mode(data: dict):
    """切换关系模式（fast / long_term）"""
    from core.relationship import switch_relationship_mode
    return switch_relationship_mode(data.get("mode", "fast"))

# 需要数值范围校验的键
_NUMERIC_KEYS = {
    "chat_font_size": (10, 20),
    "bg_opacity": (0, 1),
    "bg_blur": (0, 20),
}

@router.post("/")
async def update_setting(update: ConfigUpdate):
    # 数值范围校验
    if update.key in _NUMERIC_KEYS:
        lo, hi = _NUMERIC_KEYS[update.key]
        try:
            v = float(update.value)
            if v < lo or v > hi:
                return {"status": "error", "message": f"{update.key} 值需在 {lo}-{hi} 之间"}
        except (ValueError, TypeError):
            return {"status": "error", "message": f"{update.key} 需要数值"}

    if update.key in PERSONALITY_KEY_MAP:
        p = get_config("personality", {})
        if not isinstance(p, dict):
            p = {}
        p[PERSONALITY_KEY_MAP[update.key]] = update.value
        set_config("personality", p)
    else:
        set_config(update.key, update.value)
    return {"status": "ok"}

@router.get("/presets")
async def list_presets():
    return get_presets()

@router.post("/presets")
async def create_preset(preset: PresetData):
    save_preset(preset.name, preset.data)
    return {"status": "ok"}

@router.delete("/presets/{name}")
async def remove_preset(name: str):
    delete_preset(name)
    return {"status": "ok"}

# ========== onboarding ==========

@router.get("/onboarding-status")
async def get_onboarding_status():
    completed = get_config("onboarding_completed", "")
    has_key = bool(get_config("api_key", ""))
    # 检查是否有聊天记录
    from core.db import get_conn
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as cnt FROM chat_history")
        row = cursor.fetchone()
        has_history = row["cnt"] > 0 if row else False
    return {
        "needs_onboarding": not completed and (not has_key or not has_history),
        "has_api_key": has_key,
        "has_chat_history": has_history
    }

@router.post("/onboarding-complete")
async def complete_onboarding():
    set_config("onboarding_completed", "true")
    return {"status": "ok"}