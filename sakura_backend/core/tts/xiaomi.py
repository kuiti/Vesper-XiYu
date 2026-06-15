# core/tts/xiaomi.py
import os, base64, logging
from core.retry import silent_exc
from . import BaseTTS, TTSResult, _save_audio_bytes, _get_audio_duration, _register_temp_file
logger = logging.getLogger(__name__)
class XiaomiTTS(BaseTTS):
    name = "xiaomi"
    description = "Xiaomi MiMo TTS"
    needs_key = True
    supports_clone = True
    VOICES = {"ice_candy": "ice_candy", "jasmine": "jasmine", "soda": "soda", "birch": "birch",
        "Mia": "Mia", "Chloe": "Chloe", "Milo": "Milo", "Dean": "Dean"}
    API_URL = "https://api.xiaomimimo.com/v1/chat/completions"
    def __init__(self, api_key="", voice="ice_candy", clone_audio_path="", api_url="", **kwargs):
        self.api_key = api_key
        self.voice = self.VOICES.get(voice, voice)
        self.clone_audio_path = clone_audio_path
        self._clone_base64 = None
        self.api_url = api_url or self.API_URL
    def _load_clone_audio(self):
        if self._clone_base64 is not None: return self._clone_base64
        if not self.clone_audio_path or not os.path.exists(self.clone_audio_path): return ""
        try:
            b64_path = self.clone_audio_path + ".b64"
            if os.path.exists(b64_path):
                with open(b64_path, "r", encoding="utf-8") as f: self._clone_base64 = f.read().strip()
                return self._clone_base64
            with open(self.clone_audio_path, "rb") as f: data = f.read()
            if len(data) > 7 * 1024 * 1024: logger.warning(f"Clone audio too large: {len(data)} bytes"); return ""
            b64 = base64.b64encode(data).decode("utf-8")
            ext = os.path.splitext(self.clone_audio_path)[1].lower()
            mime = "audio/mpeg" if ext == ".mp3" else "audio/wav"
            self._clone_base64 = f"data:{mime};base64,{b64}"
            try:
                with open(b64_path, "w", encoding="utf-8") as f: f.write(self._clone_base64)
            except Exception as e: silent_exc("_load_clone_audio", e)
            return self._clone_base64
        except Exception as e:
            logger.error(f"Load clone audio failed: {e}")
            return ""
    async def synthesize(self, text, **kwargs):
        if not self.api_key: return TTSResult(success=False, error="Xiaomi API Key not configured")
        clean = self.clean_text(text)
        if not clean: return TTSResult(success=False, error="empty text")
        voice = kwargs.get("voice", self.voice)
        style = kwargs.get("style", "")
        clone_audio = kwargs.get("clone_audio", "")
        mode = kwargs.get("mode", "auto")
        use_clone = (mode == "clone" or (mode == "auto" and bool(clone_audio or self.clone_audio_path)))
        if use_clone and not clone_audio: clone_audio = self._load_clone_audio()
        model = "mimo-v2.5-tts-voiceclone" if use_clone else "mimo-v2.5-tts"
        voice_value = clone_audio if use_clone else (voice or "ice_candy")
        try:
            import httpx
            async with httpx.AsyncClient(timeout=60.0) as client:
                messages = []
                if style: messages.append({"role": "user", "content": style})
                messages.append({"role": "assistant", "content": clean})
                payload = {"model": model, "messages": messages, "audio": {"format": "wav", "voice": voice_value}}
                resp = await client.post(self.api_url, json=payload, timeout=60.0,
                    headers={"api-key": self.api_key, "Content-Type": "application/json"})
                if resp.status_code != 200: return TTSResult(success=False, error=f"API {resp.status_code}: {resp.text[:200]}")
                data = resp.json()
                try:
                    audio_data = data["choices"][0]["message"]["audio"]["data"]
                except (KeyError, IndexError) as e:
                    return TTSResult(success=False, error=f"Response format error: {e}")
                audio_bytes = base64.b64decode(audio_data)
                output = _save_audio_bytes(audio_bytes, prefix="xiaomi_tts", ext=".wav")
                duration = _get_audio_duration(output)
                _register_temp_file(output)
                return TTSResult(success=True, audio_path=output, audio_url=f"/tts/audio/{os.path.basename(output)}", duration=duration)
        except httpx.TimeoutException:
            return TTSResult(success=False, error="Xiaomi TTS timeout")
        except Exception as e:
            logger.error(f"Xiaomi TTS: {e}")
            return TTSResult(success=False, error=str(e))
