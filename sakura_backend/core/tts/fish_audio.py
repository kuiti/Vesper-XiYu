# core/tts/fish_audio.py
import os, logging
from . import BaseTTS, TTSResult, _save_audio_bytes, _get_audio_duration, _register_temp_file
logger = logging.getLogger(__name__)
class FishAudioTTS(BaseTTS):
    name = "fish_audio"
    description = "Fish Audio"
    needs_key = True
    supports_clone = True
    def __init__(self, api_key="", voice="", api_url="", **kwargs):
        self.api_key = api_key
        self.voice = voice
        self.api_url = (api_url or "https://api.fish.audio/v1").rstrip("/")
    async def synthesize(self, text, **kwargs):
        if not self.api_key: return TTSResult(success=False, error="Fish Audio API Key not configured")
        voice = kwargs.get("voice", self.voice) or "7f92f8af1b7d4a8a8f8b8c8d8e8f8a8b"
        reference_audio = kwargs.get("reference_audio", "")
        clean = self.clean_text(text)
        if not clean: return TTSResult(success=False, error="empty text")
        try:
            import httpx
            payload = {"text": clean, "voice": voice}
            if reference_audio: payload["reference_audio"] = reference_audio
            async with httpx.AsyncClient(timeout=120.0) as client:
                resp = await client.post(f"{self.api_url}/tts",
                    headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}, json=payload)
                if resp.status_code != 200: return TTSResult(success=False, error=f"API {resp.status_code}: {resp.text[:200]}")
                output = _save_audio_bytes(resp.content, prefix="fish_tts", ext=".wav")
                duration = _get_audio_duration(output)
                _register_temp_file(output)
                return TTSResult(success=True, audio_path=output, audio_url=f"/tts/audio/{os.path.basename(output)}", duration=duration)
        except Exception as e:
            logger.error(f"Fish Audio TTS: {e}")
            return TTSResult(success=False, error=str(e))
