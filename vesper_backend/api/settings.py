"""设置管理 API — 提供系统配置、预设、基石类型、引导流程及完全重置等接口。"""
# version: 5.0.0
import logging

from fastapi import APIRouter
from core.db import get_config, set_config, get_presets, save_preset, delete_preset
from pydantic import BaseModel
from typing import Any, Dict

logger = logging.getLogger(__name__)

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
    """获取所有系统配置项，包含 API、主题、语音、关系模式等设置。"""
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
        "ai_name": get_config("ai_name", "夕语"),
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
    """更新单个配置项，支持白名单校验、数值范围校验和名字保留字检查。"""
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
        # 人格配置存入嵌套的 personality 字典
        p = get_config("personality", {})
        if not isinstance(p, dict):
            p = {}
        p[PERSONALITY_KEY_MAP[update.key]] = update.value
        set_config("personality", p)
    else:
        set_config(update.key, update.value)

    # card_* 字段同步到活跃角色卡
    if update.key.startswith("card_") and get_config("_active_character_card", ""):
        try:
            from core.character_card import CharacterCard
            card = CharacterCard.get_active()
            if card and hasattr(card, '_db_id') and card._db_id:
                field = update.key.replace("card_", "")
                if field in card.data:
                    card.data[field] = update.value
                    card.data["card_data"] = card.to_json(indent=None)
                    card.update_db(card._db_id)
                # 清缓存
                from core.prompt_builder import clear_persona_cache
                clear_persona_cache()
        except Exception as e:
            from core.retry import silent_exc
            silent_exc("sync_card", e)

    if update.key in ("llm_provider", "api_base_url", "api_model", "api_key"):
        from core.llm_provider import clear_provider_cache
        clear_provider_cache()
    return {"status": "ok"}

@router.get("/presets")
async def list_presets():
    """获取所有预设列表。"""
    return get_presets()

@router.post("/presets")
async def create_preset(preset: PresetData):
    """创建或更新预设。"""
    save_preset(preset.name, preset.data)
    return {"status": "ok"}

@router.delete("/presets/{name}")
async def remove_preset(name: str):
    """删除指定名称的预设。"""
    delete_preset(name)
    return {"status": "ok"}

# ========== foundation ==========

class FoundationUpdate(BaseModel):
    foundation_type: str
    reset_values: bool = False  # 是否重置好感/信任为基石默认值
    character_id: int = 0  # 角色 ID（per-character 关系）

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

    # 判断是否需要重置关系值（当前值为0时自动重置）
    should_reset = data.reset_values
    if not should_reset:
        try:
            aff, trust = get_relationship(character_id=data.character_id)
            if aff == 0 and trust == 0:
                should_reset = True
        except Exception:
            pass

    if should_reset:
        set_relationship_by_foundation(foundation_type, character_id=data.character_id)
        return {"status": "ok", "foundation_type": foundation_type, "values_reset": True}
    return {"status": "ok", "foundation_type": foundation_type, "values_reset": False}

# ========== onboarding ==========

@router.get("/onboarding-status")
async def get_onboarding_status():
    """获取新手引导状态，判断是否需要引导流程。"""
    completed = get_config("onboarding_completed", "")
    has_key = bool(get_config("api_key", ""))
    # 检查是否有聊天记录
    from core.character_card import CharacterCard
    has_history = False
    all_cids = {0}
    try:
        for c in CharacterCard.list_all():
            cid = c.get("id", 0) if isinstance(c, dict) else 0
            if cid:
                all_cids.add(cid)
    except Exception:
        pass
    for cid in all_cids:
        try:
            from core.db import get_chat_conn
            with get_chat_conn(cid) as conn:
                row = conn.execute("SELECT COUNT(*) as cnt FROM chat_history").fetchone()
                if row and row["cnt"] > 0:
                    has_history = True
                    break
        except Exception:
            pass
    return {
        "needs_onboarding": not completed and (not has_key or not has_history),
        "has_api_key": has_key,
        "has_chat_history": has_history
    }

@router.post("/onboarding-complete")
async def complete_onboarding():
    """标记新手引导已完成。"""
    set_config("onboarding_completed", "true")
    return {"status": "ok"}

class FullResetConfirm(BaseModel):
    confirm: bool = False

@router.post("/full-reset")
async def full_reset(data: FullResetConfirm = FullResetConfirm()):
    """完全重置：清除所有数据（主库 + 所有角色库），重新触发引导。"""
    if not data.confirm:
        return {"status": "error", "message": "请确认重置操作"}
    from core.db import get_conn, clear_chat_history, clear_config_cache, get_chat_conn
    from core.relationship import invalidate_relationship_cache
    from core.llm_provider import clear_provider_cache
    from core.character_card import CharacterCard
    errors = []

    # 收集所有角色 ID
    all_cids = {0}
    try:
        for c in CharacterCard.list_all():
            cid = c.get("id", 0) if isinstance(c, dict) else 0
            if cid:
                all_cids.add(cid)
    except Exception:
        pass

    # 1. 清除聊天记录 + 2. per-character 表（遍历所有角色库）
    for cid in all_cids:
        clear_chat_history(character_id=cid)
        with get_chat_conn(cid) as conn:
            cursor = conn.cursor()
            for table in ["relationship",
                           "emotion_daily", "emotion_log", "ai_personality_traits",
                           "tiered_summary", "death_archive", "user_profile",
                           "memory", "entities", "knowledge_graph",
                           "memory_history", "conversation_summary"]:
                try:
                    cursor.execute(f"DELETE FROM {table}")
                except Exception as e:
                    errors.append(f"char{cid}/{table}: {e}")

    # 3. 清除主库全局表
    with get_conn() as conn:
        cursor = conn.cursor()
        for table in [
                       "user_activity_stats", "proactive_response_log", "proactive_flags",
                       "ai_diary", "demand_patterns"]:
            try:
                cursor.execute(f"DELETE FROM {table}")
            except Exception as e:
                errors.append(f"global/{table}: {e}")

    # 4. 清除配置（保留 API 设置）
    api_key = get_config("api_key", "")
    api_provider = get_config("api_provider", "")
    api_base_url = get_config("api_base_url", "")
    api_model = get_config("api_model", "")
    llm_provider = get_config("llm_provider", "")
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM config WHERE key NOT IN ('api_key', 'api_provider', 'api_base_url', 'api_model', 'llm_provider', '_tiered_migration_done', '_default_presets_seeded')")
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
    clear_config_cache()
    invalidate_relationship_cache()
    clear_provider_cache()

    # 5. 清除向量存储
    try:
        import shutil, os
        chroma_path = "data/chroma_db"
        if os.path.exists(chroma_path):
            shutil.rmtree(chroma_path)
            os.makedirs(chroma_path, exist_ok=True)
    except Exception as e:
        errors.append(f"chroma_db: {e}")
        logger.warning(f"[重置] 清除向量库失败: {e}")

    if errors:
        return {"status": "partial", "message": f"重置完成，{len(errors)} 个表清理失败", "errors": errors}
    return {"status": "ok", "message": "完全重置完成，即将重新开始引导"}
