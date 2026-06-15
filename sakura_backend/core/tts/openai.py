# core/tts/openai.py
import os, logging
from . import BaseTTS, TTSResult, _save_audio_bytes, _get_audio_duration, _register_temp_file
logger = logging.getLogger(__name__)
class OpenAITTS(BaseTTS):
    name = "openai"
    description = "OpenAI TTS"
    needs_key = True
    VOICES = ["alloy", "echo", "fable", "onyx", "nova", "shimmer"]
    MODELS = ["tts-1", "tts-1-hd"]
    def __init__(self, api_key="", voice="alloy", api_url="", **kwargs):
        self.api_key = api_key
        self.voice = voice if voice in self.VOICES else "alloy"
        self.api_url = (api_url or "https://api.openai.com/v1").rstrip("/")
    async def synthesize(self, text, **kwargs):
        if not self.api_key:
            return TTSResult(success=False, error="OpenAI API Key not configured")
        voice = kwargs.get("voice", self.voice)
        if voice not in self.VOICES: voice = "alloy"
        model = kwargs.get("model", "tts-1")
        clean = self.clean_text(text)
        if not clean: return TTSResult(success=False, error="empty text")
        try:
            import httpx
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(f"{self.api_url}/audio/speech",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json={"model": model, "input": clean, "voice": voice, "response_format": "wav"})
                if resp.status_code != 200:
                    return TTSResult(success=False, error=f"API {resp.status_code}: {resp.text[:200]}")
                output = _save_audio_bytes(resp.content, prefix="openai_tts", ext=".wav")
                duration = _get_audio_duration(output)
                _register_temp_file(output)
                return TTSResult(success=True, audio_path=output, audio_url=f"/tts/audio/{os.path.basename(output)}", duration=duration)
        except Exception as e:
            logger.error(f"OpenAI TTS: {e}")
            return TTSResult(success=False, error=str(e))
