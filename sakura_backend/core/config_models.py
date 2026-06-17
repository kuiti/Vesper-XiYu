# core/config_models.py — 配置项 pydantic 校验模型
"""所有配置项的类型定义和默认值，get_config 返回时自动校验"""
from pydantic import BaseModel, Field


class PersonalityConfig(BaseModel):
    """人设配置"""
    tone: str = Field(default="冷静", description="语气风格")
    length: str = Field(default="短", description="回复长度")
    recall: str = Field(default="从不", description="记忆回调")
    allow_emotion: bool = Field(default=True, description="允许颜文字")


class VoiceConfig(BaseModel):
    """语音配置"""
    tts_enabled: bool = Field(default=False, description="TTS 开关")
    tts_engine: str = Field(default="off", description="TTS 引擎")
    tts_voice: str = Field(default="", description="TTS 音色")
    tts_api_key: str = Field(default="", description="TTS API Key")
    tts_api_url: str = Field(default="", description="TTS API URL")
    tts_server_url: str = Field(default="", description="TTS 服务器地址")
    tts_clone_audio: str = Field(default="", description="声音克隆音频路径")
    tts_clone_mode: str = Field(default="preset", description="声音模式：preset=预设音色, clone=声音克隆")
    tts_speed: float = Field(default=1.0, description="语速")
    stt_enabled: bool = Field(default=False, description="STT 开关")
    auto_play: bool = Field(default=False, description="自动播放")
    voice_character: str = Field(default="YUKI", description="语音角色")


class CloudConfig(BaseModel):
    """云备份配置"""
    backend_type: str = Field(default="webdav", description="后端类型")
    server_url: str = Field(default="", description="服务器地址")
    username: str = Field(default="", description="用户名")
    passphrase: str = Field(default="", description="密码")
    auto_sync: bool = Field(default=False, description="自动同步")


# 配置项类型映射
CONFIG_TYPES = {
    "personality": PersonalityConfig,
    "voice": VoiceConfig,
    "cloud_config": CloudConfig,
}

# 简单类型配置项
SIMPLE_CONFIGS = {
    "ai_name": str,
    "user_name": str,
    "api_key": str,
    "api_base_url": str,
    "api_model": str,
    "api_provider": str,
    "model_mode": str,
    "custom_system_prompt": str,
    "ai_background": str,
    "precise_city": str,
    "manual_city": str,
    "amap_key": str,
    "pin_code": str,
    "length_level": str,
    "recall_past": str,
    "allow_emotion": bool,
    "proactive_style": str,
    "sentence_mode": str,
    "search_provider": str,
    "theme": str,
    "chat_bg_image": str,
    "bg_mode": str,
    "bg_opacity": float,
    "bg_blur": float,
    "relationship_mode": str,
    "chat_font_size": int,
    "use_weather_care": bool,
    "use_system_notification": bool,
    "notification_style": str,
    "show_tray_notification": bool,
    "pin_enabled": bool,
}


def validate_config(key: str, value):
    """校验配置项，返回校验后的值。类型不匹配时返回默认值。"""
    if value is None:
        return value

    # 复杂类型配置项
    if key in CONFIG_TYPES:
        model_class = CONFIG_TYPES[key]
        if isinstance(value, dict):
            try:
                return model_class(**value).model_dump()
            except Exception:
                return model_class().model_dump()  # 返回默认值
        elif isinstance(value, model_class):
            return value.model_dump()
        else:
            return model_class().model_dump()

    # 简单类型配置项
    if key in SIMPLE_CONFIGS:
        expected_type = SIMPLE_CONFIGS[key]
        if not isinstance(value, expected_type):
            # bool 特殊处理：避免 bool("False") == True
            if expected_type is bool and isinstance(value, str):
                return value.lower() in ("1", "true", "yes", "on")
            try:
                return expected_type(value)
            except (ValueError, TypeError):
                return value  # 转换失败返回原值，让调用方用 default 兜底

    return value
