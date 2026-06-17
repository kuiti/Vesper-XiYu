# core/tts/aliyun.py
import os, logging
from . import BaseTTS, TTSResult, _save_audio_bytes, _get_audio_duration, _register_temp_file
logger = logging.getLogger(__name__)
class AliyunTTS(BaseTTS):
    name = "aliyun"
    description = "Aliyun TTS"
    needs_key = True
    supports_clone = True
    def __init__(self, api_key="", voice="", api_url="", **kwargs):
        self.api_key = api_key
        self.voice = voice
        self.api_url = (api_url or "https://nls-gateway.cn-shanghai.aliyuncs.com").rstrip("/")
        parts = api_key.split("|") if api_key else ["", "", ""]
        self.access_key_id = parts[0] if len(parts) > 0 else ""
        self.access_key_secret = parts[1] if len(parts) > 1 else ""
        self.app_key = parts[2] if len(parts) > 2 else ""
    async def synthesize(self, text, **kwargs):
        if not self.api_key: return TTSResult(success=False, error="Aliyun API Key not configured")
        if not all([self.access_key_id, self.access_key_secret, self.app_key]):
            return TTSResult(success=False, error="Key format: AccessKeyId|AccessKeySecret|AppKey")
        voice = kwargs.get("voice", self.voice) or "longxiaochun"
        clean = self.clean_text(text)
        if not clean: return TTSResult(success=False, error="empty text")
        try:
            import httpx
            async with httpx.AsyncClient(timeout=10.0) as client:
                token_resp = await client.post("https://nls-meta.cn-shanghai.aliyuncs.com/v2.0/tts/token",
                    headers={"Content-Type": "application/json"},
                    json={"access_key_id": self.access_key_id, "access_key_secret": self.access_key_secret, "app_key": self.app_key})
                if token_resp.status_code != 200: return TTSResult(success=False, error=f"Aliyun token fail: {token_resp.text[:200]}")
                token_data = token_resp.json()
                nls_token = token_data.get("token") or token_data.get("Data", {}).get("Token", "")
            if not nls_token: return TTSResult(success=False, error="Aliyun token failed")
            async with httpx.AsyncClient(timeout=120.0) as client:
                tts_resp = await client.post("https://nls-gateway.cn-shanghai.aliyuncs.com/stream/v1/tts",
                    headers={"X-NLS-Token": nls_token, "Content-Type": "application/json"},
                    json={"appkey": self.app_key, "text": clean, "format": "wav", "voice": voice, "sample_rate": 16000,
                        "volume": 50, "speech_rate": int(kwargs.get("speed", 1.0) * 100), "pitch_rate": 100})
                if tts_resp.status_code != 200: return TTSResult(success=False, error=f"API {tts_resp.status_code}: {tts_resp.text[:200]}")
                output = _save_audio_bytes(tts_resp.content, prefix="aliyun_tts", ext=".wav")
                duration = _get_audio_duration(output)
                _register_temp_file(output)
                return TTSResult(success=True, audio_path=output, audio_url=f"/tts/audio/{os.path.basename(output)}", duration=duration)
        except Exception as e:
            logger.error(f"Aliyun TTS: {e}")
            return TTSResult(success=False, error=str(e))
