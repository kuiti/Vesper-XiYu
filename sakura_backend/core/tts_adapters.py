# core/tts_adapters.py — 多 TTS 引擎适配器
"""统一接口，支持多个 TTS 后端。

| 引擎          | 类型     | API Key | 本地部署 | 声音克隆 |
|---------------|----------|---------|----------|----------|
| Edge TTS      | 免费在线 | 不需要  | 不需要   | ❌       |
| OpenAI TTS    | 在线 API | 需要    | 不需要   | ❌       |
| 火山引擎 TTS  | 在线 API | 需要    | 不需要   | ❌       |
| 百度 TTS      | 在线 API | 需要    | 不需要   | ❌       |
| 阿里云 TTS    | 在线 API | 需要    | 不需要   | ❌       |
| Fish Audio    | 在线 API | 需要    | 不需要   | ✅       |
| CosyVoice     | 本地     | 不需要  | 需要     | ✅       |
| GPT-SoVITS    | 本地     | 不需要  | 需要     | ✅       |
| 讯飞 Spark    | 在线 API | 需要    | 不需要   | ❌       |
"""
from __future__ import annotations
import os
import re
import json
import base64
import hashlib
import logging
import tempfile
import uuid
import wave
from abc import ABC, abstractmethod
from typing import Optional
from datetime import datetime

logger = logging.getLogger(__name__)


# ─── 工具函数 ───

def _strip_markdown(text: str) -> str:
    """去除 markdown 格式和括号动作描述。"""
    text = re.sub(r'[（(][^）)]*[）)]', '', text)
    text = re.sub(r'【[^】]*】', '', text)
    text = re.sub(r'「[^」]*」', '', text)
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    text = re.sub(r'\*(.+?)\*', r'\1', text)
    text = re.sub(r'__(.+?)__', r'\1', text)
    text = re.sub(r'_(.+?)_', r'\1', text)
    text = re.sub(r'`{1,3}[^`]*`{1,3}', '', text)
    text = re.sub(r'~~(.+?)~~', r'\1', text)
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'^[-*+]\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'^>\s+', '', text, flags=re.MULTILINE)
    return text.strip()


def _get_audio_duration(path: str) -> float:
    """获取音频文件时长（秒），失败返回 0。"""
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


def _save_audio_bytes(data: bytes, prefix: str = "tts", ext: str = ".wav") -> str:
    """保存音频字节到临时文件，返回路径。"""
    tmpdir = tempfile.gettempdir()
    path = os.path.join(tmpdir, f"{prefix}_{uuid.uuid4().hex}{ext}")
    with open(path, "wb") as f:
        f.write(data)
    return path


_TEMP_FILES = {}  # prefix -> set of filenames (for cleanup tracking)


def _register_temp_file(path: str):
    """注册临时文件以便清理。"""
    prefix = os.path.basename(path).rsplit("_", 1)[0]
    _TEMP_FILES.setdefault(prefix, set()).add(path)


# ─── 数据类 ───

class TTSResult:
    """TTS 返回结果。"""
    def __init__(self, success: bool, audio_path: str = "", audio_url: str = "",
                 duration: float = 0.0, inference_time: float = 0.0, error: str = ""):
        self.success = success
        self.audio_path = audio_path
        self.audio_url = audio_url
        self.duration = duration
        self.inference_time = inference_time
        self.error = error

    def to_dict(self):
        return {
            "success": self.success,
            "audio_path": self.audio_path,
            "audio_url": self.audio_url,
            "duration": self.duration,
            "inference_time": self.inference_time,
            "error": self.error,
        }


# ─── 引擎基类 ───

class BaseTTS(ABC):
    """TTS 引擎基类。"""
    name: str = "base"
    description: str = ""
    # 引擎特性
    supports_clone: bool = False
    supports_emotion: bool = False
    supports_speed: bool = True
    needs_key: bool = False
    needs_local: bool = False

    @abstractmethod
    async def synthesize(self, text: str, **kwargs) -> TTSResult:
        """合成语音。"""
        pass

    async def health(self) -> dict:
        return {"status": "ok", "engine": self.name}

    def clean_text(self, text: str) -> str:
        return _strip_markdown(text)


# ═══════════════════════════════════════════
# 引擎实现
# ═══════════════════════════════════════════

# ─── 1. Edge TTS ───

class EdgeTTS(BaseTTS):
    """微软 Edge TTS — 免费在线，无需 API Key。"""
    name = "edge"
    description = "Edge TTS（免费在线）"
    needs_key = False

    VOICES = {
        "xiaoyi": "zh-CN-XiaoyiNeural",
        "xiaoxiao": "zh-CN-XiaoxiaoNeural",
        "yunxi": "zh-CN-YunxiNeural",
        "yunjian": "zh-CN-YunjianNeural",
    }

    def __init__(self, voice: str = "xiaoxiao", **kwargs):
        self.voice = self.VOICES.get(voice, voice)

    async def synthesize(self, text: str, **kwargs) -> TTSResult:
        try:
            import edge_tts
        except ImportError:
            return TTSResult(success=False, error="请安装 edge-tts: pip install edge-tts")

        voice = self.VOICES.get(kwargs.get("voice", ""), kwargs.get("voice", self.voice))
        clean = self.clean_text(text)
        if not clean:
            return TTSResult(success=False, error="空文本")

        try:
            output = _save_audio_bytes(b"", prefix="edge_tts", ext=".mp3")
            communicate = edge_tts.Communicate(clean, voice)
            await communicate.save(output)
            if not os.path.exists(output):
                return TTSResult(success=False, error="生成失败")
            duration = _get_audio_duration(output)
            _register_temp_file(output)
            return TTSResult(
                success=True, audio_path=output,
                audio_url=f"/tts/audio/{os.path.basename(output)}",
                duration=duration,
            )
        except Exception as e:
            logger.error(f"Edge TTS: {e}")
            return TTSResult(success=False, error=str(e))

    async def health(self) -> dict:
        try:
            import edge_tts
            return {"status": "ok", "engine": self.name}
        except ImportError:
            return {"status": "error", "engine": self.name, "error": "edge-tts not installed"}


# ─── 2. OpenAI TTS ───

class OpenAITTS(BaseTTS):
    """OpenAI TTS API — 五个预设音色，简单可靠。"""
    name = "openai"
    description = "OpenAI TTS（在线）"
    needs_key = True

    VOICES = ["alloy", "echo", "fable", "onyx", "nova", "shimmer"]
    MODELS = ["tts-1", "tts-1-hd"]

    def __init__(self, api_key: str = "", voice: str = "alloy", api_url: str = "", **kwargs):
        self.api_key = api_key
        self.voice = voice if voice in self.VOICES else "alloy"
        self.api_url = (api_url or "https://api.openai.com/v1").rstrip("/")

    async def synthesize(self, text: str, **kwargs) -> TTSResult:
        if not self.api_key:
            return TTSResult(success=False, error="OpenAI API Key 未配置")

        voice = kwargs.get("voice", self.voice)
        if voice not in self.VOICES:
            voice = "alloy"
        model = kwargs.get("model", "tts-1")

        clean = self.clean_text(text)
        if not clean:
            return TTSResult(success=False, error="空文本")

        try:
            import httpx
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(
                    f"{self.api_url}/audio/speech",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json={"model": model, "input": clean, "voice": voice,
                          "response_format": "wav"},
                )
                if resp.status_code != 200:
                    return TTSResult(success=False, error=f"API {resp.status_code}: {resp.text[:200]}")
                output = _save_audio_bytes(resp.content, prefix="openai_tts", ext=".wav")
                duration = _get_audio_duration(output)
                _register_temp_file(output)
                return TTSResult(
                    success=True, audio_path=output,
                    audio_url=f"/tts/audio/{os.path.basename(output)}",
                    duration=duration,
                )
        except Exception as e:
            logger.error(f"OpenAI TTS: {e}")
            return TTSResult(success=False, error=str(e))


# ─── 3. 火山引擎 TTS（字节跳动） ───

class VolcanoTTS(BaseTTS):
    """火山引擎（字节跳动）TTS — 音质优秀，支持情感控制。"""
    name = "volcano"
    description = "火山引擎 TTS（在线）"
    needs_key = True
    supports_emotion = True

    VOICES = {
        "BV001": "温柔女声", "BV002": "活泼女声",
        "BV003": "沉稳男声", "BV004": "阳光男声",
        "BV005": "可爱童声", "BV006": "知性女声",
        "BV007": "磁性男声", "BV008": "新闻女声",
    }
    DEFAULT_VOICE = "BV001"

    def __init__(self, api_key: str = "", voice: str = "BV001", api_url: str = "", **kwargs):
        self.api_key = api_key
        self.voice = voice if voice in self.VOICES else self.DEFAULT_VOICE
        self.api_url = (api_url or "https://openspeech.bytedance.com/api/v1/tts").rstrip("/")

    async def synthesize(self, text: str, **kwargs) -> TTSResult:
        if not self.api_key:
            return TTSResult(success=False, error="火山引擎 API Key 未配置")

        voice = kwargs.get("voice", self.voice)
        if voice not in self.VOICES:
            voice = self.DEFAULT_VOICE

        clean = self.clean_text(text)
        if not clean:
            return TTSResult(success=False, error="空文本")

        try:
            import httpx
            payload = {
                "app": {"appid": self.api_key.split("|")[0] if "|" in self.api_key else self.api_key},
                "user": {"uid": "sakura"},
                "request": {
                    "reqid": uuid.uuid4().hex,
                    "text": clean,
                    "text_type": "plain",
                    "operation": "query",
                    "voice_type": voice,
                    "audio_format": "wav",
                    "speed_ratio": kwargs.get("speed", 1.0),
                },
            }
            # 情感控制 (如果引擎支持)
            emotion = kwargs.get("emotion", "")
            if emotion:
                payload["request"]["emotion"] = emotion

            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(
                    f"{self.api_url}/tts",
                    headers={"Authorization": f"Bearer;{self.api_key}"},
                    json=payload,
                )
                if resp.status_code != 200:
                    return TTSResult(success=False, error=f"API {resp.status_code}: {resp.text[:200]}")

                data = resp.json()
                audio_b64 = data.get("data", "")
                if not audio_b64:
                    return TTSResult(success=False, error="返回无音频数据")

                audio_bytes = base64.b64decode(audio_b64)
                output = _save_audio_bytes(audio_bytes, prefix="volcano_tts", ext=".wav")
                duration = _get_audio_duration(output)
                _register_temp_file(output)
                return TTSResult(
                    success=True, audio_path=output,
                    audio_url=f"/tts/audio/{os.path.basename(output)}",
                    duration=duration,
                )
        except Exception as e:
            logger.error(f"Volcano TTS: {e}")
            return TTSResult(success=False, error=str(e))


# ─── 4. 百度 TTS ───

class BaiduTTS(BaseTTS):
    """百度短文本 TTS — REST API，简单稳定。"""
    name = "baidu"
    description = "百度 TTS（在线）"
    needs_key = True

    VOICES = {
        "0": "女声（普通）", "1": "男声（普通）",
        "3": "女声（情感）", "4": "男声（情感）",
        "5003": "女声（精品）", "111": "男声（情感加深）",
    }

    def __init__(self, api_key: str = "", voice: str = "0", api_url: str = "", **kwargs):
        self.api_key = api_key
        self.voice = voice if voice in self.VOICES else "0"
        # 百度 TTS API Key 格式: appid|secret
        self._appid = ""
        self._secret = ""
        if "|" in api_key:
            self._appid, self._secret = api_key.split("|", 1)
        self.api_url = (api_url or "https://tsn.baidu.com/text2audio").rstrip("/")

    async def _get_access_token(self) -> str:
        """获取百度 access_token（client_credentials 模式）。"""
        import httpx
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    "https://aip.baidubce.com/oauth/2.0/token",
                    params={
                        "grant_type": "client_credentials",
                        "client_id": self._appid,
                        "client_secret": self._secret,
                    },
                )
                data = resp.json()
                return data.get("access_token", "")
        except Exception as e:
            logger.error(f"百度 token 获取失败: {e}")
            return ""

    async def synthesize(self, text: str, **kwargs) -> TTSResult:
        if not self.api_key:
            return TTSResult(success=False, error="百度 API Key 未配置（格式: appid|secret）")
        if not self._appid or not self._secret:
            return TTSResult(success=False, error="API Key 格式错误，应为 appid|secret")

        voice = kwargs.get("voice", self.voice)
        clean = self.clean_text(text)
        if not clean:
            return TTSResult(success=False, error="空文本")

        try:
            import httpx
            token = await self._get_access_token()
            if not token:
                return TTSResult(success=False, error="获取 access_token 失败")

            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(
                    self.api_url,
                    data={
                        "tok": token,
                        "tex": clean,
                        "per": voice,
                        "spd": int(kwargs.get("speed", 1.0) * 5),
                        "pit": 5,
                        "vol": 15,
                        "aue": 6,  # wav
                        "cuid": "sakura_ai",
                        "lan": "zh",
                        "ctp": 1,
                    },
                )
                # 百度返回 content-type 区分成功(音频)和失败(JSON)
                ct = resp.headers.get("content-type", "")
                if "json" in ct:
                    err = resp.json().get("err_msg", "未知错误")
                    return TTSResult(success=False, error=f"百度 TTS: {err}")

                output = _save_audio_bytes(resp.content, prefix="baidu_tts", ext=".wav")
                duration = _get_audio_duration(output)
                _register_temp_file(output)
                return TTSResult(
                    success=True, audio_path=output,
                    audio_url=f"/tts/audio/{os.path.basename(output)}",
                    duration=duration,
                )
        except Exception as e:
            logger.error(f"Baidu TTS: {e}")
            return TTSResult(success=False, error=str(e))


# ─── 5. 阿里云 TTS（CosyVoice 云端版） ───

class AliyunTTS(BaseTTS):
    """阿里云 TTS（CosyVoice 云端 API）— 声音复刻，情感自然。"""
    name = "aliyun"
    description = "阿里云 TTS（在线）"
    needs_key = True
    supports_clone = True

    def __init__(self, api_key: str = "", voice: str = "", api_url: str = "", **kwargs):
        self.api_key = api_key
        self.voice = voice
        self.api_url = (api_url or "https://nls-gateway.cn-shanghai.aliyuncs.com").rstrip("/")
        # API Key 格式: AccessKeyId|AccessKeySecret|AppKey
        parts = api_key.split("|") if api_key else ["", "", ""]
        self.access_key_id = parts[0] if len(parts) > 0 else ""
        self.access_key_secret = parts[1] if len(parts) > 1 else ""
        self.app_key = parts[2] if len(parts) > 2 else ""

    async def synthesize(self, text: str, **kwargs) -> TTSResult:
        if not self.api_key:
            return TTSResult(success=False, error="阿里云 API Key 未配置（格式: AccessKeyId|AccessKeySecret|AppKey）")
        if not all([self.access_key_id, self.access_key_secret, self.app_key]):
            return TTSResult(success=False, error="API Key 格式错误，应为 AccessKeyId|AccessKeySecret|AppKey")

        voice = kwargs.get("voice", self.voice) or "longxiaochun"
        clean = self.clean_text(text)
        if not clean:
            return TTSResult(success=False, error="空文本")

        try:
            import httpx
            import hmac
            from hashlib import sha1

            # 阿里云 HTTP 直调（简化版，不走百炼 SDK）
            action = "CreateToken"
            timestamp = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

            # 先获取 token
            async with httpx.AsyncClient(timeout=10.0) as client:
                token_resp = await client.post(
                    f"https://nls-meta.cn-shanghai.aliyuncs.com/v2.0/tts/token",
                    headers={
                        "Content-Type": "application/json",
                    },
                    json={
                        "access_key_id": self.access_key_id,
                        "access_key_secret": self.access_key_secret,
                        "app_key": self.app_key,
                    },
                )
                if token_resp.status_code != 200:
                    return TTSResult(success=False, error=f"阿里云 token 失败: {token_resp.text[:200]}")
                token_data = token_resp.json()
                nls_token = token_data.get("token") or token_data.get("Data", {}).get("Token", "")

            if not nls_token:
                return TTSResult(success=False, error="获取阿里云 token 失败")

            # 调用 TTS
            async with httpx.AsyncClient(timeout=120.0) as client:
                tts_resp = await client.post(
                    f"https://nls-gateway.cn-shanghai.aliyuncs.com/stream/v1/tts",
                    headers={
                        "X-NLS-Token": nls_token,
                        "Content-Type": "application/json",
                    },
                    json={
                        "appkey": self.app_key,
                        "text": clean,
                        "format": "wav",
                        "voice": voice,
                        "sample_rate": 16000,
                        "volume": 50,
                        "speech_rate": int(kwargs.get("speed", 1.0) * 100),
                        "pitch_rate": 100,
                    },
                )
                if tts_resp.status_code != 200:
                    return TTSResult(success=False, error=f"API {tts_resp.status_code}: {tts_resp.text[:200]}")

                audio_bytes = tts_resp.content
                output = _save_audio_bytes(audio_bytes, prefix="aliyun_tts", ext=".wav")
                duration = _get_audio_duration(output)
                _register_temp_file(output)
                return TTSResult(
                    success=True, audio_path=output,
                    audio_url=f"/tts/audio/{os.path.basename(output)}",
                    duration=duration,
                )
        except Exception as e:
            logger.error(f"Aliyun TTS: {e}")
            return TTSResult(success=False, error=str(e))


# ─── 6. Fish Audio TTS ───

class FishAudioTTS(BaseTTS):
    """Fish Audio — 在线 TTS API，支持声音克隆。"""
    name = "fish_audio"
    description = "Fish Audio（在线，支持克隆）"
    needs_key = True
    supports_clone = True

    def __init__(self, api_key: str = "", voice: str = "", api_url: str = "", **kwargs):
        self.api_key = api_key
        self.voice = voice
        self.api_url = (api_url or "https://api.fish.audio/v1").rstrip("/")

    async def synthesize(self, text: str, **kwargs) -> TTSResult:
        if not self.api_key:
            return TTSResult(success=False, error="Fish Audio API Key 未配置")

        voice = kwargs.get("voice", self.voice) or "7f92f8af1b7d4a8a8f8b8c8d8e8f8a8b"
        reference_audio = kwargs.get("reference_audio", "")
        clean = self.clean_text(text)
        if not clean:
            return TTSResult(success=False, error="空文本")

        try:
            import httpx
            payload = {"text": clean, "voice": voice}
            if reference_audio:
                payload["reference_audio"] = reference_audio

            async with httpx.AsyncClient(timeout=120.0) as client:
                resp = await client.post(
                    f"{self.api_url}/tts",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
                if resp.status_code != 200:
                    return TTSResult(success=False, error=f"API {resp.status_code}: {resp.text[:200]}")

                output = _save_audio_bytes(resp.content, prefix="fish_tts", ext=".wav")
                duration = _get_audio_duration(output)
                _register_temp_file(output)
                return TTSResult(
                    success=True, audio_path=output,
                    audio_url=f"/tts/audio/{os.path.basename(output)}",
                    duration=duration,
                )
        except Exception as e:
            logger.error(f"Fish Audio TTS: {e}")
            return TTSResult(success=False, error=str(e))


# ─── 7. CosyVoice（本地部署） ───

class CosyVoiceTTS(BaseTTS):
    """CosyVoice 本地部署 — 阿里达摩院开源，声音克隆效果极佳。"""
    name = "cosyvoice"
    description = "CosyVoice（本地部署）"
    needs_key = False
    needs_local = True
    supports_clone = True
    supports_emotion = True

    def __init__(self, server_url: str = "http://127.0.0.1:50000", voice: str = "", **kwargs):
        self.server_url = server_url.rstrip("/")
        self.voice = voice or "default"

    async def synthesize(self, text: str, **kwargs) -> TTSResult:
        clean = self.clean_text(text)
        if not clean:
            return TTSResult(success=False, error="空文本")

        try:
            import httpx
            voice = kwargs.get("voice", self.voice)
            payload = {
                "text": clean,
                "voice": voice,
                "speed": kwargs.get("speed", 1.0),
            }
            emotion = kwargs.get("emotion", "")
            if emotion:
                payload["emotion"] = emotion

            async with httpx.AsyncClient(timeout=120.0) as client:
                resp = await client.post(
                    f"{self.server_url}/tts",
                    json=payload,
                )
                if resp.status_code != 200:
                    return TTSResult(success=False, error=f"CosyVoice {resp.status_code}: {resp.text[:200]}")

                output = _save_audio_bytes(resp.content, prefix="cosyvoice_tts", ext=".wav")
                duration = _get_audio_duration(output)
                _register_temp_file(output)
                return TTSResult(
                    success=True, audio_path=output,
                    audio_url=f"/tts/audio/{os.path.basename(output)}",
                    duration=duration,
                )
        except httpx.ConnectError:
            return TTSResult(success=False, error=f"无法连接 CosyVoice 服务 ({self.server_url})")
        except Exception as e:
            logger.error(f"CosyVoice: {e}")
            return TTSResult(success=False, error=str(e))

    async def health(self) -> dict:
        try:
            import httpx
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{self.server_url}/health")
                if resp.status_code == 200:
                    return {"status": "ok", "engine": self.name, "server": self.server_url}
                return {"status": "error", "engine": self.name, "error": f"HTTP {resp.status_code}"}
        except Exception as e:
            return {"status": "error", "engine": self.name, "error": str(e)}


# ─── 8. GPT-SoVITS（本地部署） ───

class GPTSovitsTTS(BaseTTS):
    """GPT-SoVITS 本地部署 — 少样本声音克隆，中文效果极佳。"""
    name = "gpt_sovits"
    description = "GPT-SoVITS（本地部署，支持克隆）"
    needs_key = False
    needs_local = True
    supports_clone = True

    def __init__(self, server_url: str = "http://127.0.0.1:9880", voice: str = "", **kwargs):
        self.server_url = server_url.rstrip("/")
        self.voice = voice or "default"

    async def synthesize(self, text: str, **kwargs) -> TTSResult:
        clean = self.clean_text(text)
        if not clean:
            return TTSResult(success=False, error="空文本")

        try:
            import httpx
            voice = kwargs.get("voice", self.voice)
            params = {
                "text": clean,
                "text_lang": kwargs.get("lang", "zh"),
                "ref_audio_path": kwargs.get("ref_audio", voice),
                "prompt_text": kwargs.get("prompt_text", ""),
                "prompt_lang": kwargs.get("prompt_lang", "zh"),
                "text_split_method": kwargs.get("split_method", "cut5"),
                "speed_factor": kwargs.get("speed", 1.0),
            }

            async with httpx.AsyncClient(timeout=180.0) as client:
                resp = await client.get(f"{self.server_url}/tts", params=params)
                if resp.status_code != 200:
                    return TTSResult(success=False, error=f"GPT-SoVITS {resp.status_code}: {resp.text[:200]}")

                output = _save_audio_bytes(resp.content, prefix="gptsovits_tts", ext=".wav")
                duration = _get_audio_duration(output)
                _register_temp_file(output)
                return TTSResult(
                    success=True, audio_path=output,
                    audio_url=f"/tts/audio/{os.path.basename(output)}",
                    duration=duration,
                )
        except httpx.ConnectError:
            return TTSResult(success=False, error=f"无法连接 GPT-SoVITS ({self.server_url})")
        except Exception as e:
            logger.error(f"GPT-SoVITS: {e}")
            return TTSResult(success=False, error=str(e))

    async def health(self) -> dict:
        try:
            import httpx
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{self.server_url}/status")
                if resp.status_code == 200:
                    return {"status": "ok", "engine": self.name, "server": self.server_url}
                return {"status": "error", "engine": self.name, "error": f"HTTP {resp.status_code}"}
        except Exception as e:
            return {"status": "error", "engine": self.name, "error": str(e)}


# ─── 9. 讯飞 Spark TTS ───

class SparkTTS(BaseTTS):
    """讯飞 Spark TTS — WebSocket 协议，不支持直接 HTTP。"""
    name = "spark"
    description = "讯飞 Spark TTS（在线）"
    needs_key = True

    def __init__(self, api_key: str = "", voice: str = "x4_zh", api_url: str = "", **kwargs):
        self.api_key = api_key
        self.voice = voice
        self.api_url = api_url or "wss://tts-api.xfyun.cn/v2/tts"
        # API Key 格式: appid|api_secret|api_key
        parts = api_key.split("|") if api_key else ["", "", ""]
        self.appid = parts[0] if len(parts) > 0 else ""
        self.api_secret = parts[1] if len(parts) > 1 else ""
        self.api_key_value = parts[2] if len(parts) > 2 else ""

    async def synthesize(self, text: str, **kwargs) -> TTSResult:
        if not self.api_key:
            return TTSResult(success=False, error="讯飞 API Key 未配置（格式: appid|api_secret|api_key）")

        clean = self.clean_text(text)
        if not clean:
            return TTSResult(success=False, error="空文本")

        try:
            import httpx
            from datetime import datetime

            # 讯飞 REST API（使用 HTTP 方式调用流式接口的简化封装）
            # 实际生产环境建议用 WebSocket，这里使用 HTTP 简化调用
            url = "https://tts-api.xfyun.cn/v2/tts"

            # 构建 authorization
            timestamp = datetime.utcnow().strftime("%a, %d %b %Y %H:%M:%S GMT")
            signature_str = f"host: tts-api.xfyun.cn\ndate: {timestamp}\nPOST /v2/tts HTTP/1.1"
            import hmac
            from hashlib import sha256, md5
            signature = hmac.new(
                self.api_secret.encode("utf-8"),
                signature_str.encode("utf-8"),
                sha256,
            ).digest()
            authorization = base64.b64encode(signature).decode("utf-8")

            # 构建请求
            business = {
                "aue": "lame",
                "sfl": 1,
                "auf": "audio/L16;rate=16000",
                "vcn": kwargs.get("voice", self.voice) or "x4_zh",
                "speed": int(kwargs.get("speed", 1.0) * 50),
                "volume": 50,
                "pitch": 50,
                "bgs": 0,
            }
            data_payload = {
                "common": {"app_id": self.appid},
                "business": business,
                "data": {
                    "text": base64.b64encode(clean.encode("utf-8")).decode("utf-8"),
                    "status": 2,
                },
            }

            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(
                    url,
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": authorization,
                        "Date": timestamp,
                    },
                    json=data_payload,
                )
                if resp.status_code != 200:
                    return TTSResult(success=False, error=f"讯飞 {resp.status_code}: {resp.text[:200]}")

                result = resp.json()
                if result.get("code") != 0:
                    return TTSResult(success=False, error=f"讯飞: {result.get('message', '')} (code={result.get('code')})")

                # 音频在 data.audio 中(base64)
                audio_b64 = result.get("data", {}).get("audio", "")
                if not audio_b64:
                    return TTSResult(success=False, error="返回无音频数据")

                audio_bytes = base64.b64decode(audio_b64)
                output = _save_audio_bytes(audio_bytes, prefix="spark_tts", ext=".mp3")
                duration = _get_audio_duration(output)
                _register_temp_file(output)
                return TTSResult(
                    success=True, audio_path=output,
                    audio_url=f"/tts/audio/{os.path.basename(output)}",
                    duration=duration,
                )
        except Exception as e:
            logger.error(f"Spark TTS: {e}")
            return TTSResult(success=False, error=str(e))


# ─── 10. 小米 MiMo TTS ───

class XiaomiTTS(BaseTTS):
    """小米 MiMo TTS — 在线 API（OpenAI 兼容格式），支持声音克隆。"""
    name = "xiaomi"
    description = "小米 TTS（在线）"
    needs_key = True
    supports_clone = True

    VOICES = {
        "冰糖": "冰糖", "茉莉": "茉莉", "苏打": "苏打", "白桦": "白桦",
        "Mia": "Mia", "Chloe": "Chloe", "Milo": "Milo", "Dean": "Dean",
    }
    API_URL = "https://api.xiaomimimo.com/v1/chat/completions"

    def __init__(self, api_key: str = "", voice: str = "冰糖",
                 clone_audio_path: str = "", api_url: str = "", **kwargs):
        self.api_key = api_key
        self.voice = self.VOICES.get(voice, voice)
        self.clone_audio_path = clone_audio_path
        self._clone_base64 = None
        self.api_url = api_url or self.API_URL

    def _load_clone_audio(self) -> str:
        if self._clone_base64 is not None:
            return self._clone_base64
        if not self.clone_audio_path or not os.path.exists(self.clone_audio_path):
            return ""
        try:
            b64_path = self.clone_audio_path + ".b64"
            if os.path.exists(b64_path):
                with open(b64_path, "r", encoding="utf-8") as f:
                    self._clone_base64 = f.read().strip()
                return self._clone_base64
            with open(self.clone_audio_path, "rb") as f:
                data = f.read()
            if len(data) > 7 * 1024 * 1024:
                logger.warning(f"克隆音频太大: {len(data)} bytes")
                return ""
            b64 = base64.b64encode(data).decode("utf-8")
            ext = os.path.splitext(self.clone_audio_path)[1].lower()
            mime = "audio/mpeg" if ext == ".mp3" else "audio/wav"
            self._clone_base64 = f"data:{mime};base64,{b64}"
            try:
                with open(b64_path, "w", encoding="utf-8") as f:
                    f.write(self._clone_base64)
            except Exception:
                pass
            return self._clone_base64
        except Exception as e:
            logger.error(f"加载克隆音频失败: {e}")
            return ""

    async def synthesize(self, text: str, **kwargs) -> TTSResult:
        if not self.api_key:
            return TTSResult(success=False, error="小米 TTS API Key 未配置")
        clean = self.clean_text(text)
        if not clean:
            return TTSResult(success=False, error="空文本")

        voice = kwargs.get("voice", self.voice)
        style = kwargs.get("style", "")
        clone_audio = kwargs.get("clone_audio", "")
        mode = kwargs.get("mode", "auto")

        use_clone = (
            mode == "clone" or
            (mode == "auto" and bool(clone_audio or self.clone_audio_path))
        )
        if use_clone and not clone_audio:
            clone_audio = self._load_clone_audio()

        model = "mimo-v2.5-tts-voiceclone" if use_clone else "mimo-v2.5-tts"
        voice_value = clone_audio if use_clone else (voice or "冰糖")

        try:
            import httpx
            async with httpx.AsyncClient(timeout=60.0) as client:
                messages = []
                if style:
                    messages.append({"role": "user", "content": style})
                messages.append({"role": "assistant", "content": clean})

                payload = {
                    "model": model,
                    "messages": messages,
                    "audio": {"format": "wav", "voice": voice_value},
                }
                resp = await client.post(
                    self.api_url, json=payload, timeout=60.0,
                    headers={"api-key": self.api_key, "Content-Type": "application/json"},
                )
                if resp.status_code != 200:
                    return TTSResult(success=False, error=f"API {resp.status_code}: {resp.text[:200]}")

                data = resp.json()
                try:
                    audio_data = data["choices"][0]["message"]["audio"]["data"]
                except (KeyError, IndexError) as e:
                    return TTSResult(success=False, error=f"响应格式异常: {e}")

                audio_bytes = base64.b64decode(audio_data)
                output = _save_audio_bytes(audio_bytes, prefix="xiaomi_tts", ext=".wav")
                duration = _get_audio_duration(output)
                _register_temp_file(output)
                return TTSResult(
                    success=True, audio_path=output,
                    audio_url=f"/tts/audio/{os.path.basename(output)}",
                    duration=duration,
                )
        except httpx.TimeoutException:
            return TTSResult(success=False, error="小米 TTS 请求超时")
        except Exception as e:
            logger.error(f"Xiaomi TTS: {e}")
            return TTSResult(success=False, error=str(e))


# ===== 引擎注册表 =====

TTS_ENGINES = {
    "off": None,
    "edge": EdgeTTS,
    "openai": OpenAITTS,
    "volcano": VolcanoTTS,
    "baidu": BaiduTTS,
    "aliyun": AliyunTTS,
    "fish_audio": FishAudioTTS,
    "cosyvoice": CosyVoiceTTS,
    "gpt_sovits": GPTSovitsTTS,
    "spark": SparkTTS,
    "xiaomi": XiaomiTTS,
}

ENGINE_LABELS = {
    "off": "关闭语音",
    "edge": "Edge TTS（免费在线）",
    "openai": "OpenAI TTS（在线）",
    "volcano": "火山引擎 TTS（在线）",
    "baidu": "百度 TTS（在线）",
    "aliyun": "阿里云 TTS（在线）",
    "fish_audio": "Fish Audio（在线，支持克隆）",
    "cosyvoice": "CosyVoice（本地部署）",
    "gpt_sovits": "GPT-SoVITS（本地部署）",
    "spark": "讯飞 Spark TTS（在线）",
    "xiaomi": "小米 TTS（在线）",
}

ENGINE_FEATURES = {
    name: {
        "needs_key": getattr(cls, "needs_key", False) if cls else False,
        "needs_local": getattr(cls, "needs_local", False) if cls else False,
        "supports_clone": getattr(cls, "supports_clone", False) if cls else False,
        "supports_emotion": getattr(cls, "supports_emotion", False) if cls else False,
    }
    for name, cls in TTS_ENGINES.items()
}


def create_tts_engine(engine: str, **config) -> Optional[BaseTTS]:
    """根据名称创建 TTS 引擎实例。"""
    if engine == "off" or engine not in TTS_ENGINES:
        return None
    cls = TTS_ENGINES[engine]
    try:
        return cls(**config)
    except Exception as e:
        logger.error(f"创建 TTS 引擎 {engine} 失败: {e}")
        return None


def get_cleanup_prefixes() -> list[str]:
    """获取所有引擎的临时文件前缀，用于清理。"""
    return [
        "edge_tts_", "openai_tts_", "volcano_tts_", "baidu_tts_",
        "aliyun_tts_", "fish_tts_", "cosyvoice_tts_", "gptsovits_tts_",
        "spark_tts_", "xiaomi_tts_",
    ]
