# core/tts/volcano.py
import os, uuid, base64, logging
from . import BaseTTS, TTSResult, _save_audio_bytes, _get_audio_duration, _register_temp_file
logger = logging.getLogger(__name__)
class VolcanoTTS(BaseTTS):
    name = "volcano"
    description = "Volcano TTS"
    needs_key = True
    supports_emotion = True
    VOICES = {"BV001": "gentle female", "BV002": "lively female", "BV003": "calm male", "BV004": "sunny male"}
    DEFAULT_VOICE = "BV001"
    def __init__(self, api_key="", voice="BV001", api_url="", **kwargs):
        self.api_key = api_key
        self.voice = voice if voice in self.VOICES else self.DEFAULT_VOICE
        self.api_url = (api_url or "https://openspeech.bytedance.com/api/v1/tts").rstrip("/")
    async def synthesize(self, text, **kwargs):
        if not self.api_key: return TTSResult(success=False, error="Volcano API Key not configured")
        voice = kwargs.get("voice", self.voice)
        if voice not in self.VOICES: voice = self.DEFAULT_VOICE
        clean = self.clean_text(text)
        if not clean: return TTSResult(success=False, error="empty text")
        try:
            import httpx
            payload = {"app": {"appid": self.api_key.split("|")[0] if "|" in self.api_key else self.api_key},
                "user": {"uid": "sakura"}, "request": {"reqid": uuid.uuid4().hex, "text": clean, "text_type": "plain",
                "operation": "query", "voice_type": voice, "audio_format": "wav", "speed_ratio": kwargs.get("speed", 1.0)}}
            emotion = kwargs.get("emotion", "")
            if emotion: payload["request"]["emotion"] = emotion
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(f"{self.api_url}/tts", headers={"Authorization": f"Bearer;{self.api_key}"}, json=payload)
                if resp.status_code != 200: return TTSResult(success=False, error=f"API {resp.status_code}: {resp.text[:200]}")
                data = resp.json()
                audio_b64 = data.get("data", "")
                if not audio_b64: return TTSResult(success=False, error="no audio data")
                audio_bytes = base64.b64decode(audio_b64)
                output = _save_audio_bytes(audio_bytes, prefix="volcano_tts", ext=".wav")
                duration = _get_audio_duration(output)
                _register_temp_file(output)
                return TTSResult(success=True, audio_path=output, audio_url=f"/tts/audio/{os.path.basename(output)}", duration=duration)
        except Exception as e:
            logger.error(f"Volcano TTS: {e}")
            return TTSResult(success=False, error=str(e))
