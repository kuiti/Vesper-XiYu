"""Voice emotion mapping — maps affection/trust to TTS voice presets."""

# Voice presets from genie_tts reference audio system
PRESET_VERYLOW = "verylow"
PRESET_LOW = "low"
PRESET_HIGH = "high"


def get_voice_preset(affection: float = 0, trust: float = 50,
                     personality: str = "") -> str:
    # Trust tempers affection: low trust makes high affection less warm
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

