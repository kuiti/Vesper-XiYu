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

# 允许前端修改的配置键白名单
_SETTINGS_WHITELIST = {
    "model_mode", "custom_system_prompt", "ai_background", "theme",
    "enable_web_search", "enable_llm_web_search", "search_provider",
    "auto_cleanup_days", "default_city", "precise_city", "manual_city",
    "enable_llm_weather_search", "primary_color", "bg_color", "sidebar_bg",
    "chat_bg", "user_bubble", "ai_bubble", "use_system_notification",
    "notification_style", "use_weather_care", "show_tray_notification",
    "relationship_mode", "sentence_mode", "chat_font_size", "proactive_frequency",
    "proactive_style", "chat_bg_image", "bg_opacity", "bg_blur", "bg_mode",
    "pin_enabled", "quick_phrases", "snake_high", "2048_best", "minesweeper_wins",
    "user_name", "ai_name", "api_key", "api_provider", "llm_provider", "api_base_url", "api_model",
    "tts_enabled", "tts_engine", "tts_voice", "tts_api_key", "tts_server_url",
    "tts_api_url", "stt_enabled", "auto_play_voice", "tts_clone_audio",
    "fallback_models", "user_taboos", "post_history_instructions",
    "card_description", "card_personality",
    "card_scenario", "card_mes_example",
} | set(PERSONALITY_KEY_MAP.keys())

@router.get("/")
async def get_all_settings() -> Dict[str, Any]:
    personality = get_config("personality", {})
    if not isinstance(personality, dict):
        personality = {}
    _voice = get_config("voice", {})
    if not isinstance(_voice, dict):
        _voice = {}
    return {
        "has_api_key": bool(get_config("api_key", "")),
        "api_provider": get_config("api_provider", ""),
        "llm_provider": get_config("llm_provider", "deepseek"),
        "model_mode": get_config("model_mode", "auto"),
        "api_base_url": get_config("api_base_url", "https://api.deepseek.com/v1"),
        "api_model": get_config("api_model", "deepseek-chat"),
        "fallback_models": get_config("fallback_models", ""),
        "length_level": personality.get("length") if personality.get("length") is not None else get_config("length_level", "短"),
        "recall_past": personality.get("recall") if personality.get("recall") is not None else get_config("recall_past", "从不"),
        "allow_emotion": personality.get("allow_emotion") if personality.get("allow_emotion") is not None else get_config("allow_emotion", True),
        "custom_system_prompt": get_config("custom_system_prompt", ""),
        "ai_background": get_config("ai_background", ""),
        "personality_tone": personality.get("tone", "冷静"),
        "theme": get_config("theme", "dark"),
        "enable_web_search": get_config("enable_web_search", True),
        "enable_llm_web_search": get_config("enable_llm_web_search", False),
        "search_provider": get_config("search_provider", "ddg"),  # off / llm / ddg
        "auto_cleanup_days": get_config("auto_cleanup_days", 30),
        "default_city": get_config("default_city", ""),
        "has_amap_key": bool(get_config("amap_key", "")),
        "user_name": get_config("user_name", "我"),
        "ai_name": get_config("ai_name", "佐仓"),
        "precise_city": get_config("precise_city", ""),
        "manual_city": get_config("manual_city", ""),
        "enable_llm_weather_search": get_config("enable_llm_weather_search", False),
        "primary_color": get_config("primary_color", "#6a9fd8"),
        "bg_color": get_config("bg_color", "#0f1119"),
        "sidebar_bg": get_config("sidebar_bg", "#161927"),
        "chat_bg": get_config("chat_bg", "#0f1119"),
        "user_bubble": get_config("user_bubble", "#1d3557"),
        "ai_bubble": get_config("ai_bubble", "#181e2b"),
        "tts_enabled": _voice.get("tts_enabled", True),
        "tts_engine": _voice.get("tts_engine", "off"),
        "tts_voice": _voice.get("tts_voice", ""),
        "has_tts_api_key": bool(_voice.get("tts_api_key", "")),
        "tts_server_url": _voice.get("tts_server_url", ""),
        "tts_api_url": _voice.get("tts_api_url", ""),
        "stt_enabled": _voice.get("stt_enabled", True),
        "auto_play_voice": _voice.get("auto_play", False),
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
        "quick_phrases": get_config("quick_phrases", "[]"),
        "snake_high": get_config("snake_high", 0),
        "2048_best": get_config("2048_best", 0),
        "minesweeper_wins": get_config("minesweeper_wins", 0),
        "tts_clone_audio": get_config("tts_clone_audio", ""),
        "card_description": get_config("card_description", ""),
        "card_personality": get_config("card_personality", ""),
        "card_scenario": get_config("card_scenario", ""),
        "card_mes_example": get_config("card_mes_example", ""),
        "user_taboos": get_config("user_taboos", "[]"),
        "post_history_instructions": get_config("post_history_instructions", ""),
    }

class RelationshipMode(BaseModel):
    mode: str

@router.post("/relationship-mode")
async def set_relationship_mode(data: RelationshipMode):
    """切换关系模式（fast / long_term）"""
    from core.relationship import switch_relationship_mode
    return switch_relationship_mode(data.mode)

# 需要数值范围校验的键
_NUMERIC_KEYS = {
    "chat_font_size": (10, 20),
    "bg_opacity": (0, 1),
    "bg_blur": (0, 20),
}

PERSONA_KEYS = {"custom_system_prompt", "ai_name", "user_name", "ai_background",
                 "card_description", "card_personality", "card_scenario", "card_mes_example"} | set(PERSONALITY_KEY_MAP.keys())


@router.post("/")
async def update_setting(update: ConfigUpdate):
    if update.key.startswith("_"):
        return {"status": "error", "message": "不能修改内部配置"}
    if update.key not in _SETTINGS_WHITELIST:
        return {"status": "error", "message": f"不允许修改配置: {update.key}"}
    if update.key in _NUMERIC_KEYS:
        lo, hi = _NUMERIC_KEYS[update.key]
        try:
            v = float(update.value)
            if v < lo or v > hi:
                return {"status": "error", "message": f"{update.key} 值需在 {lo}-{hi} 之间"}
        except (ValueError, TypeError):
            return {"status": "error", "message": f"{update.key} 需要数值"}

    if update.key in ("user_name", "ai_name"):
        v = str(update.value).strip()
        if not v or len(v) > 20:
            return {"status": "error", "message": "名字需 1-20 个字"}
        if v.lower() in ("system", "user", "assistant", "null", "undefined", "none", "true", "false"):
            return {"status": "error", "message": f"「{v}」是保留字，不能作为名字"}
        update.value = v

    if update.key in PERSONALITY_KEY_MAP:
        p = get_config("personality", {})
        if not isinstance(p, dict):
            p = {}
        p[PERSONALITY_KEY_MAP[update.key]] = update.value
        set_config("personality", p)
    else:
        set_config(update.key, update.value)

    # card_* 字段同步到 _character_card_extra
    if update.key.startswith("card_") and get_config("_active_character_card", ""):
        try:
            import json as _json
            _extra = get_config("_character_card_extra", "{}")
            _extra_obj = _json.loads(_extra) if isinstance(_extra, str) else _extra
            _field = update.key.replace("card_", "")
            _extra_obj[_field] = update.value
            set_config("_character_card_extra", _json.dumps(_extra_obj, ensure_ascii=False))
        except Exception as e:
            from core.retry import silent_exc
            silent_exc("sync_card_extra", e)

    if update.key in ("llm_provider", "api_base_url", "api_model", "api_key"):
        from core.llm_provider import clear_provider_cache
        clear_provider_cache()
    if update.key in PERSONA_KEYS and get_config("_active_character_card", ""):
        try:
            from core.character_card import CharacterCard
            card = CharacterCard()
            card.sync_from_current()
            card.save_to_db()
        except Exception as e:
            from core.retry import silent_exc
            silent_exc("auto_save_card", e)
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

# ========== foundation ==========

class FoundationUpdate(BaseModel):
    foundation_type: str
    reset_values: bool = False  # 是否重置好感/信任为基石默认值

@router.get("/providers")
async def list_providers():
    """获取可用的 LLM Provider 列表"""
    from core.llm_provider import get_available_providers
    return {"providers": get_available_providers()}

@router.get("/foundation-types")
async def list_foundation_types():
    """获取所有可用的基石类型"""
    from core.prompt_builder import FOUNDATION_TEMPLATES
    types = {}
    for name, (template, affection, trust) in FOUNDATION_TEMPLATES.items():
        types[name] = {
            "description": template[:50] + "...",
            "default_affection": affection,
            "default_trust": trust
        }
    return types

@router.post("/foundation")
async def set_foundation(data: FoundationUpdate):
    """设置基石类型，选择是否重置好感/信任值"""
    import json
    from core.prompt_builder import FOUNDATION_TEMPLATES
    from core.relationship import set_relationship_by_foundation, get_relationship

    foundation_type = data.foundation_type
    if foundation_type not in FOUNDATION_TEMPLATES:
        return {"status": "error", "message": f"未知的基石类型: {foundation_type}"}

    # 更新 ai_background 中的 foundation_type
    from core.persona_data import parse_ai_background
    current_bg = get_config("ai_background", "")
    bg_obj = parse_ai_background(current_bg)
    bg_obj["foundation_type"] = foundation_type
    if "foundation" in bg_obj:
        del bg_obj["foundation"]
    set_config("ai_background", json.dumps(bg_obj, ensure_ascii=False))

    # 判断是否需要重置关系值
    should_reset = data.reset_values
    if not should_reset:
        try:
            aff, trust = get_relationship()
            if aff == 0 and trust == 0:
                should_reset = True
        except Exception:
            pass

    if should_reset:
        set_relationship_by_foundation(foundation_type)
        return {"status": "ok", "foundation_type": foundation_type, "values_reset": True}
    return {"status": "ok", "foundation_type": foundation_type, "values_reset": False}

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

class FullResetConfirm(BaseModel):
    confirm: bool = False

@router.post("/full-reset")
async def full_reset(data: FullResetConfirm = FullResetConfirm()):
    if not data.confirm:
        return {"status": "error", "message": "请确认重置操作"}
    """完全重置：清除所有数据，重新触发引导"""
    from core.db import get_conn, clear_chat_history, clear_config_cache
    from core.relationship import invalidate_relationship_cache
    from core.llm_provider import clear_provider_cache
    # 1. 清除聊天记录
    clear_chat_history()
    # 2. 清除所有提醒、日程、待办、笔记、倒计时、目标
    errors = []
    with get_conn() as conn:
        cursor = conn.cursor()
        for table in ["reminders", "schedule", "todos", "notes", "countdowns", "goal_tracking",
                       "emotion_daily", "relationship", "empathy_feedback", "favorites", "documents"]:
            try:
                cursor.execute(f"DELETE FROM {table}")
            except Exception as e:
                errors.append(f"{table}: {e}")
    # 3. 清除配置（保留 API 设置）
    api_key = get_config("api_key", "")
    api_provider = get_config("api_provider", "")
    api_base_url = get_config("api_base_url", "")
    api_model = get_config("api_model", "")
    llm_provider = get_config("llm_provider", "")
    # 删除所有配置（除了 API 相关的）
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM config WHERE key NOT IN ('api_key', 'api_provider', 'api_base_url', 'api_model', 'llm_provider', '_tiered_migration_done', '_default_presets_seeded')")
    # 恢复 API 设置
    if api_key:
        set_config("api_key", api_key)
    if api_provider:
        set_config("api_provider", api_provider)
    if api_base_url:
        set_config("api_base_url", api_base_url)
    if api_model:
        set_config("api_model", api_model)
    if llm_provider:
        set_config("llm_provider", llm_provider)
    # 清除配置缓存（SQL DELETE 不经过 set_config，缓存不会自动失效）
    clear_config_cache()
    invalidate_relationship_cache()
    clear_provider_cache()
    # 4. 清除向量存储
    try:
        import shutil
        import os
        chroma_path = "data/chroma_db"
        if os.path.exists(chroma_path):
            shutil.rmtree(chroma_path)
            os.makedirs(chroma_path, exist_ok=True)
    except Exception as e:
        errors.append(f"chroma_db: {e}")
        print(f"[重置] 清除向量库失败: {e}")
    # 5. 清除心路历程和其他数据
    with get_conn() as conn:
        cursor = conn.cursor()
        for table in ["emotion_log", "ai_personality_traits", "user_activity_stats",
                       "proactive_response_log", "proactive_flags", "conversation_summary",
                       "ai_diary", "achievements", "demand_patterns", "pending_goals",
                       "sentence_index", "memory", "user_profile", "summary",
                       "entities", "memory_history", "death_archive", "knowledge_graph",
                       "memory_importance"]:
            try:
                cursor.execute(f"DELETE FROM {table}")
            except Exception as e:
                errors.append(f"{table}: {e}")
    if errors:
        return {"status": "partial", "message": f"重置完成，{len(errors)} 个表清理失败", "errors": errors}
    return {"status": "ok", "message": "完全重置完成，即将重新开始引导"}
