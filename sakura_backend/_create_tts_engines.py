#!/usr/bin/env python3
"""Helper script to create all TTS engine files for the core/tts/ package."""
import os

TTS_DIR = os.path.join(os.path.dirname(__file__), "core", "tts")

ENGINES = {
    "__init__.py": """from __future__ import annotations
import os, re, uuid, wave, tempfile, logging
from abc import ABC, abstractmethod
from typing import Optional
logger = logging.getLogger(__name__)
def _strip_markdown(text):
    text = re.sub(r'[\\uff08(][^\\uff09)]*[\\uff09)]', '', text)
    text = re.sub(r'\\u3010[^\\u3011]*\\u3011', '', text)
    text = re.sub(r'\\u300c[^\\u300d]*\\u300d', '', text)
    text = re.sub(r'\\*\\*(.+?)\\*\\*', r'\\1', text)
    text = re.sub(r'\\*(.+?)\\*', r'\\1', text)
    text = re.sub(r'__(.+?)__', r'\\1', text)
    text = re.sub(r'_(.+?)_', r'\\1', text)
    text = re.sub(r'`{1,3}[^`]*`{1,3}', '', text)
    text = re.sub(r'~~(.+?)~~', r'\\1', text)
    text = re.sub(r'^#{1,6}\\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'^[-*+]\\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'^>\\s+', '', text, flags=re.MULTILINE)
    return text.strip()
def _get_audio_duration(path):
    ext = os.path.splitext(path)[1].lower()
    try:
        if ext == ".wav":
            with wave.open(path, "rb") as wf:
                return wf.getnframes() / wf.getframerate()
        else:
            from mutagen.mp3 import MP3
            audio = MP3(path)
            return audio.info.length
    except Exception:
        return 0.0
def _save_audio_bytes(data, prefix="tts", ext=".wav"):
    tmpdir = tempfile.gettempdir()
    path = os.path.join(tmpdir, f"{prefix}_{uuid.uuid4().hex}{ext}")
    with open(path, "wb") as f:
        f.write(data)
    return path
_TEMP_FILES = {}
def _register_temp_file(path):
    prefix = os.path.basename(path).rsplit("_", 1)[0]
    _TEMP_FILES.setdefault(prefix, set()).add(path)
class TTSResult:
    def __init__(self, success, audio_path="", audio_url="", duration=0.0, inference_time=0.0, error=""):
        self.success = success
        self.audio_path = audio_path
        self.audio_url = audio_url
        self.duration = duration
        self.inference_time = inference_time
        self.error = error
    def to_dict(self):
        return {"success": self.success, "audio_path": self.audio_path, "audio_url": self.audio_url, "duration": self.duration, "inference_time": self.inference_time, "error": self.error}
class BaseTTS(ABC):
    name = "base"
    description = ""
    supports_clone = False
    supports_emotion = False
    supports_speed = True
    needs_key = False
    needs_local = False
    @abstractmethod
    async def synthesize(self, text, **kwargs):
        pass
    async def health(self):
        return {"status": "ok", "engine": self.name}
    def clean_text(self, text):
        return _strip_markdown(text)
from .edge import EdgeTTS
from .openai import OpenAITTS
from .volcano import VolcanoTTS
from .baidu import BaiduTTS
from .aliyun import AliyunTTS
from .fish_audio import FishAudioTTS
from .cosyvoice import CosyVoiceTTS
from .gpt_sovits import GPTSovitsTTS
from .spark import SparkTTS
from .xiaomi import XiaomiTTS
TTS_ENGINES = {"off": None, "edge": EdgeTTS, "openai": OpenAITTS, "volcano": VolcanoTTS, "baidu": BaiduTTS, "aliyun": AliyunTTS, "fish_audio": FishAudioTTS, "cosyvoice": CosyVoiceTTS, "gpt_sovits": GPTSovitsTTS, "spark": SparkTTS, "xiaomi": XiaomiTTS}
ENGINE_LABELS = {"off": "Off", "edge": "Edge TTS", "openai": "OpenAI TTS", "volcano": "Volcano TTS", "baidu": "Baidu TTS", "aliyun": "Aliyun TTS", "fish_audio": "Fish Audio", "cosyvoice": "CosyVoice", "gpt_sovits": "GPT-SoVITS", "spark": "Spark TTS", "xiaomi": "Xiaomi TTS"}
ENGINE_FEATURES = {name: {"needs_key": getattr(cls, "needs_key", False) if cls else False, "needs_local": getattr(cls, "needs_local", False) if cls else False, "supports_clone": getattr(cls, "supports_clone", False) if cls else False, "supports_emotion": getattr(cls, "supports_emotion", False) if cls else False} for name, cls in TTS_ENGINES.items()}
def create_tts_engine(engine, **config):
    if engine == "off" or engine not in TTS_ENGINES: return None
    cls = TTS_ENGINES[engine]
    try: return cls(**config)
    except Exception as e: logger.error(f"create tts {engine} failed: {e}"); return None
def get_cleanup_prefixes():
    return ["edge_tts_", "openai_tts_", "volcano_tts_", "baidu_tts_", "aliyun_tts_", "fish_tts_", "cosyvoice_tts_", "gptsovits_tts_", "spark_tts_", "xiaomi_tts_"]
""",
    "openai.py": """# core/tts/openai.py
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
""",
    "volcano.py": """# core/tts/volcano.py
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
""",
    "baidu.py": """# core/tts/baidu.py
import os, base64, logging
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
                    "spd": int(kwargs.get("speed", 1.0) * 5), "pit": 5, "vol": 15, "aue": 6, "cuid": "sakura_ai", "lan": "zh", "ctp": 1})
                ct = resp.headers.get("content-type", "")
                if "json" in ct: return TTSResult(success=False, error=f"Baidu: {resp.json().get('err_msg', 'unknown')}")
                output = _save_audio_bytes(resp.content, prefix="baidu_tts", ext=".wav")
                duration = _get_audio_duration(output)
                _register_temp_file(output)
                return TTSResult(success=True, audio_path=output, audio_url=f"/tts/audio/{os.path.basename(output)}", duration=duration)
        except Exception as e:
            logger.error(f"Baidu TTS: {e}")
            return TTSResult(success=False, error=str(e))
""",
    "aliyun.py": """# core/tts/aliyun.py
import os, base64, logging
from datetime import datetime
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
""",
    "fish_audio.py": """# core/tts/fish_audio.py
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
""",
    "cosyvoice.py": """# core/tts/cosyvoice.py
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
""",
    "gpt_sovits.py": """# core/tts/gpt_sovits.py
import os, logging
from . import BaseTTS, TTSResult, _save_audio_bytes, _get_audio_duration, _register_temp_file
logger = logging.getLogger(__name__)
class GPTSovitsTTS(BaseTTS):
    name = "gpt_sovits"
    description = "GPT-SoVITS Local"
    needs_key = False
    needs_local = True
    supports_clone = True
    def __init__(self, server_url="http://127.0.0.1:9880", voice="", **kwargs):
        self.server_url = server_url.rstrip("/")
        self.voice = voice or "default"
    async def synthesize(self, text, **kwargs):
        clean = self.clean_text(text)
        if not clean: return TTSResult(success=False, error="empty text")
        try:
            import httpx
            voice = kwargs.get("voice", self.voice)
            params = {"text": clean, "text_lang": kwargs.get("lang", "zh"),
                "ref_audio_path": kwargs.get("ref_audio", voice),
                "prompt_text": kwargs.get("prompt_text", ""), "prompt_lang": kwargs.get("prompt_lang", "zh"),
                "text_split_method": kwargs.get("split_method", "cut5"), "speed_factor": kwargs.get("speed", 1.0)}
            async with httpx.AsyncClient(timeout=180.0) as client:
                resp = await client.get(f"{self.server_url}/tts", params=params)
                if resp.status_code != 200: return TTSResult(success=False, error=f"GPT-SoVITS {resp.status_code}: {resp.text[:200]}")
                output = _save_audio_bytes(resp.content, prefix="gptsovits_tts", ext=".wav")
                duration = _get_audio_duration(output)
                _register_temp_file(output)
                return TTSResult(success=True, audio_path=output, audio_url=f"/tts/audio/{os.path.basename(output)}", duration=duration)
        except httpx.ConnectError:
            return TTSResult(success=False, error=f"Cannot connect to GPT-SoVITS ({self.server_url})")
        except Exception as e:
            logger.error(f"GPT-SoVITS: {e}")
            return TTSResult(success=False, error=str(e))
    async def health(self):
        try:
            import httpx
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{self.server_url}/status")
                if resp.status_code == 200: return {"status": "ok", "engine": self.name, "server": self.server_url}
                return {"status": "error", "engine": self.name, "error": f"HTTP {resp.status_code}"}
        except Exception as e:
            return {"status": "error", "engine": self.name, "error": str(e)}
""",
    "spark.py": """# core/tts/spark.py
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
            signature_str = f"host: tts-api.xfyun.cn\\ndate: {timestamp}\\nPOST /v2/tts HTTP/1.1"
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
""",
    "xiaomi.py": """# core/tts/xiaomi.py
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
""",
}

for name, content in ENGINES.items():
    path = os.path.join(TTS_DIR, name)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content.strip() + "\n")
    print(f"Created {name} ({os.path.getsize(path)} bytes)")

print(f"\nFinal listing: {os.listdir(TTS_DIR)}")