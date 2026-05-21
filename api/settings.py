# version: 3.8.1
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
    "recall_past": "recall_past",
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
        "model_mode": get_config("model_mode", "auto"),
        "api_base_url": get_config("api_base_url", "https://api.deepseek.com/v1"),
        "api_model": get_config("api_model", "deepseek-chat"),
        "length_level": personality.get("length") or get_config("length_level", "短"),
        "recall_past": personality.get("recall_past") or get_config("recall_past", "从不"),
        "allow_emotion": personality.get("allow_emotion") if personality.get("allow_emotion") is not None else get_config("allow_emotion", True),
        "custom_system_prompt": get_config("custom_system_prompt", ""),
        "personality_tone": personality.get("tone", "冷静"),
        "theme": get_config("theme", "dark"),
        "enable_web_search": get_config("enable_web_search", True),
        "auto_cleanup_days": get_config("auto_cleanup_days", 30),
        "default_city": get_config("default_city", ""),
        "has_amap_key": bool(get_config("amap_key", "")),
        "user_name": get_config("user_name", "我"),
        "ai_name": get_config("ai_name", "夕语"),
        "precise_city": get_config("precise_city", ""),
        "primary_color": get_config("primary_color", "#5390d4"),
        "bg_color": get_config("bg_color", "#0d1117"),
        "sidebar_bg": get_config("sidebar_bg", "#161b22"),
        "chat_bg": get_config("chat_bg", "#0d1117"),
        "user_bubble": get_config("user_bubble", "#2b5278"),
        "ai_bubble": get_config("ai_bubble", "#1e2632"),
        "use_system_notification": get_config("use_system_notification", False),
        "notification_style": get_config("notification_style", "warm"),
        "use_weather_care": get_config("use_weather_care", True),
        "show_tray_notification": get_config("show_tray_notification", True)
    }

@router.post("/")
async def update_setting(update: ConfigUpdate):
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