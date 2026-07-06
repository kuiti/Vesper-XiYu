"""语音情感映射 —— 根据好感度/信任度选择 TTS 语音预设"""

# 语音预设等级（来自 genie_tts 参考音频系统）
PRESET_VERYLOW = "verylow"
PRESET_LOW = "low"
PRESET_HIGH = "high"


def get_voice_preset(affection: float = 0, trust: float = 50,
                     personality: str = "") -> str:
    """根据好感度和信任度返回语音预设等级"""
    # 信任度调节好感度：低信任使高好感的语气不那么温暖
    adjusted = affection
    if trust < 30 and affection >= 30:
        adjusted = max(affection - 15, 0)
    elif trust > 70 and affection < 70:
        adjusted = min(affection + 10, 100)

    if adjusted < 30:
        return PRESET_VERYLOW
    elif adjusted < 60:
        return PRESET_LOW
    else:
        return PRESET_HIGH

