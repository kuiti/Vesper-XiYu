# core/tts/cosyvoice.py
import os, logging
from . import BaseTTS, TTSResult, _save_audio_bytes, _get_audio_duration, _register_temp_file
logger = logging.getLogger(__name__)
class CosyVoiceTTS(BaseTTS):
    name = "cosyvoice"
    description = "CosyVoice Local"
    needs_key = False
    needs_local = True
    supports_clone = True
    supports_emotion = True
    def __init__(self, server_url="http://127.0.0.1:50000", voice="", **kwargs):
        self.server_url = server_url.rstrip("/")
        self.voice = voice or "default"
    async def synthesize(self, text, **kwargs):
        clean = self.clean_text(text)
        if not clean: return TTSResult(success=False, error="empty text")
        try:
            import httpx
            voice = kwargs.get("voice", self.voice)
            payload = {"text": clean, "voice": voice, "speed": kwargs.get("speed", 1.0)}
            emotion = kwargs.get("emotion", "")
            if emotion: payload["emotion"] = emotion
            async with httpx.AsyncClient(timeout=120.0) as client:
                resp = await client.post(f"{self.server_url}/tts", json=payload)
                if resp.status_code != 200: return TTSResult(success=False, error=f"CosyVoice {resp.status_code}: {resp.text[:200]}")
                output = _save_audio_bytes(resp.content, prefix="cosyvoice_tts", ext=".wav")
                duration = _get_audio_duration(output)
                _register_temp_file(output)
                return TTSResult(success=True, audio_path=output, audio_url=f"/tts/audio/{os.path.basename(output)}", duration=duration)
        except httpx.ConnectError:
            return TTSResult(success=False, error=f"Cannot connect to CosyVoice ({self.server_url})")
        except Exception as e:
            logger.error(f"CosyVoice: {e}")
            return TTSResult(success=False, error=str(e))
    async def health(self):
        try:
            import httpx
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{self.server_url}/health")
                if resp.status_code == 200: return {"status": "ok", "engine": self.name, "server": self.server_url}
                return {"status": "error", "engine": self.name, "error": f"HTTP {resp.status_code}"}
        except Exception as e:
            return {"status": "error", "engine": self.name, "error": str(e)}
