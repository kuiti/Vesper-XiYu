# core/tts/spark.py
import os, base64, hmac, logging
from datetime import datetime
from hashlib import sha256
from . import BaseTTS, TTSResult, _save_audio_bytes, _get_audio_duration, _register_temp_file
logger = logging.getLogger(__name__)
class SparkTTS(BaseTTS):
    name = "spark"
    description = "Xunfei Spark TTS"
    needs_key = True
    def __init__(self, api_key="", voice="x4_zh", api_url="", **kwargs):
        self.api_key = api_key
        self.voice = voice
        self.api_url = api_url or "wss://tts-api.xfyun.cn/v2/tts"
        parts = api_key.split("|") if api_key else ["", "", ""]
        self.appid = parts[0] if len(parts) > 0 else ""
        self.api_secret = parts[1] if len(parts) > 1 else ""
        self.api_key_value = parts[2] if len(parts) > 2 else ""
    async def synthesize(self, text, **kwargs):
        if not self.api_key: return TTSResult(success=False, error="Spark API Key not configured (appid|api_secret|api_key)")
        clean = self.clean_text(text)
        if not clean: return TTSResult(success=False, error="empty text")
        try:
            import httpx
            url = "https://tts-api.xfyun.cn/v2/tts"
            timestamp = datetime.utcnow().strftime("%a, %d %b %Y %H:%M:%S GMT")
            signature_str = f"host: tts-api.xfyun.cn\ndate: {timestamp}\nPOST /v2/tts HTTP/1.1"
            signature = hmac.new(self.api_secret.encode("utf-8"), signature_str.encode("utf-8"), sha256).digest()
            authorization = base64.b64encode(signature).decode("utf-8")
            business = {"aue": "lame", "sfl": 1, "auf": "audio/L16;rate=16000",
                "vcn": kwargs.get("voice", self.voice) or "x4_zh", "speed": int(kwargs.get("speed", 1.0) * 50),
                "volume": 50, "pitch": 50, "bgs": 0}
            data_payload = {"common": {"app_id": self.appid}, "business": business,
                "data": {"text": base64.b64encode(clean.encode("utf-8")).decode("utf-8"), "status": 2}}
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(url, headers={"Content-Type": "application/json", "Authorization": authorization, "Date": timestamp}, json=data_payload)
                if resp.status_code != 200: return TTSResult(success=False, error=f"Spark {resp.status_code}: {resp.text[:200]}")
                result = resp.json()
                if result.get("code") != 0: return TTSResult(success=False, error=f"Spark: {result.get('message', '')} (code={result.get('code')})")
                audio_b64 = result.get("data", {}).get("audio", "")
                if not audio_b64: return TTSResult(success=False, error="no audio data")
                audio_bytes = base64.b64decode(audio_b64)
                output = _save_audio_bytes(audio_bytes, prefix="spark_tts", ext=".mp3")
                duration = _get_audio_duration(output)
                _register_temp_file(output)
                return TTSResult(success=True, audio_path=output, audio_url=f"/tts/audio/{os.path.basename(output)}", duration=duration)
        except Exception as e:
            logger.error(f"Spark TTS: {e}")
            return TTSResult(success=False, error=str(e))
