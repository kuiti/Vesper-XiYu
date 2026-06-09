# core/config_keys.py — 配置键常量
"""消除散落的 get_config("xxx") 字符串拼写错误风险。
只声明高频使用的核心配置键。"""
from __future__ import annotations

# ─── API / LLM ───
KEY_API_KEY: str = "api_key"
KEY_API_MODEL: str = "api_model"
KEY_API_BASE_URL: str = "api_base_url"
KEY_API_PROVIDER: str = "api_provider"
KEY_LLM_PROVIDER: str = "llm_provider"
KEY_MODEL_MODE: str = "model_mode"

# ─── AI 人设 ───
KEY_AI_NAME: str = "ai_name"
KEY_USER_NAME: str = "user_name"
KEY_AI_BACKGROUND: str = "ai_background"
KEY_CUSTOM_SYSTEM_PROMPT: str = "custom_system_prompt"
KEY_PERSONALITY: str = "personality"

# ─── 语音 ───
KEY_VOICE: str = "voice"

# ─── 聊天 ───
KEY_SENTENCE_MODE: str = "sentence_mode"
KEY_SEARCH_PROVIDER: str = "search_provider"
KEY_ENABLE_WEB_SEARCH: str = "enable_web_search"

# ─── 主题 ───
KEY_THEME: str = "theme"
KEY_PRIMARY_COLOR: str = "primary_color"
KEY_BG_COLOR: str = "bg_color"
KEY_SIDEBAR_BG: str = "sidebar_bg"
KEY_CHAT_BG: str = "chat_bg"
KEY_USER_BUBBLE: str = "user_bubble"
KEY_AI_BUBBLE: str = "ai_bubble"

# ─── 关系 ───
KEY_RELATIONSHIP_MODE: str = "relationship_mode"

# ─── 城市/天气 ───
KEY_DEFAULT_CITY: str = "default_city"
KEY_PRECISE_CITY: str = "precise_city"
KEY_MANUAL_CITY: str = "manual_city"
KEY_AMAP_KEY: str = "amap_key"

# ─── 清理 ───
KEY_AUTO_CLEANUP_DAYS: str = "auto_cleanup_days"