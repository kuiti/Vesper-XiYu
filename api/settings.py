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

@router.get("/")
async def get_all_settings() -> Dict[str, Any]:
    return {
        "has_api_key": bool(get_config("api_key", "")),
        "model_mode": get_config("model_mode", "auto"),
        "length_level": get_config("length_level", "短"),
        "recall_past": get_config("recall_past", "从不"),
        "allow_emotion": get_config("allow_emotion", True),
        "custom_system_prompt": get_config("custom_system_prompt", ""),
        "personality_tone": get_config("personality", {}).get("tone", "冷静"),
        "theme": get_config("theme", "dark"),
        "enable_web_search": get_config("enable_web_search", True),
        "enable_deepseek_search": get_config("enable_deepseek_search", True),
        "auto_cleanup_days": get_config("auto_cleanup_days", 30),
        "default_city": get_config("default_city", ""),
        "has_amap_key": bool(get_config("amap_key", "")),
        "user_name": get_config("user_name", "我"),
        "ai_name": get_config("ai_name", "Vesper"),
        "precise_city": get_config("precise_city", ""),
        "primary_color": get_config("primary_color", "#5390d4"),
        "bg_color": get_config("bg_color", "#0d1117"),
        "sidebar_bg": get_config("sidebar_bg", "#161b22"),
        "chat_bg": get_config("chat_bg", "#0d1117"),
        "user_bubble": get_config("user_bubble", "#2b5278"),
        "ai_bubble": get_config("ai_bubble", "#1e2632"),
    }

@router.post("/")
async def update_setting(update: ConfigUpdate):
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