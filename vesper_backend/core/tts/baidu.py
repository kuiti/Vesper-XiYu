# core/tts/baidu.py
import os, logging
from . import BaseTTS, TTSResult, _save_audio_bytes, _get_audio_duration, _register_temp_file
logger = logging.getLogger(__name__)
class BaiduTTS(BaseTTS):
    name = "baidu"
    description = "Baidu TTS"
    needs_key = True
    VOICES = {"0": "female normal", "1": "male normal", "3": "female emotion", "4": "male emotion"}
    def __init__(self, api_key="", voice="0", api_url="", **kwargs):
        self.api_key = api_key
        self.voice = voice if voice in self.VOICES else "0"
        self._appid, self._secret = api_key.split("|", 1) if "|" in api_key else ("", "")
        self.api_url = (api_url or "https://tsn.baidu.com/text2audio").rstrip("/")
    async def _get_access_token(self):
        import httpx
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post("https://aip.baidubce.com/oauth/2.0/token",
                    params={"grant_type": "client_credentials", "client_id": self._appid, "client_secret": self._secret})
                return resp.json().get("access_token", "")
        except Exception as e:
            logger.error(f"Baidu token error: {e}")
            return ""
    async def synthesize(self, text, **kwargs):
        if not self.api_key: return TTSResult(success=False, error="Baidu API Key not configured")
        if not self._appid or not self._secret: return TTSResult(success=False, error="Key format: appid|secret")
        voice = kwargs.get("voice", self.voice)
        clean = self.clean_text(text)
        if not clean: return TTSResult(success=False, error="empty text")
        try:
            import httpx
            token = await self._get_access_token()
            if not token: return TTSResult(success=False, error="token failed")
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(self.api_url, data={"tok": token, "tex": clean, "per": voice,
                    "spd": int(kwargs.get("speed", 1.0) * 5), "pit": 5, "vol": 15, "aue": 6, "cuid": "vesper_ai", "lan": "zh", "ctp": 1})
                ct = resp.headers.get("content-type", "")
                if "json" in ct: return TTSResult(success=False, error=f"Baidu: {resp.json().get('err_msg', 'unknown')}")
                output = _save_audio_bytes(resp.content, prefix="baidu_tts", ext=".wav")
                duration = _get_audio_duration(output)
                _register_temp_file(output)
                return TTSResult(success=True, audio_path=output, audio_url=f"/tts/audio/{os.path.basename(output)}", duration=duration)
        except Exception as e:
            logger.error(f"Baidu TTS: {e}")
            return TTSResult(success=False, error=str(e))
