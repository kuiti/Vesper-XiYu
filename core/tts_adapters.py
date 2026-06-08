"""多 TTS 引擎适配器 — 统一接口，支持多个 TTS 后端。"""
import os
import re
import logging
import tempfile
import uuid
from abc import ABC, abstractmethod
from typing import Optional, List

import httpx

logger = logging.getLogger(__name__)


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


class BaseTTS(ABC):
    """TTS 引擎基类。"""

    name: str = "base"
    description: str = ""

    @abstractmethod
    async def synthesize(self, text: str, **kwargs) -> TTSResult:
        """合成语音。

        Args:
            text: 要合成的文本
            **kwargs: 引擎特定参数（emotion、voice 等）

        Returns:
            TTSResult
        """
        pass

    async def health(self) -> dict:
        """检查引擎状态。"""
        return {"status": "ok", "engine": self.name}

    def clean_text(self, text: str) -> str:
        return _strip_markdown(text)


class EdgeTTS(BaseTTS):
    """微软 Edge TTS — 免费，在线，多语言。"""

    name = "edge"
    description = "Edge TTS（免费在线）"

    VOICES = {
        "xiaoyi": "zh-CN-XiaoyiNeural",      # 女声，温柔
        "xiaoxiao": "zh-CN-XiaoxiaoNeural",   # 女声，活泼
        "yunxi": "zh-CN-YunxiNeural",          # 男声，阳光
        "yunjian": "zh-CN-YunjianNeural",      # 男声，沉稳
    }

    def __init__(self, voice: str = "xiaoyi"):
        self.voice_id = self.VOICES.get(voice, voice)

    async def synthesize(self, text: str, **kwargs) -> TTSResult:
        voice = kwargs.get("voice", self.voice_id)
        # 如果传的是中文名，转换为 ID
        if voice in self.VOICES:
            voice = self.VOICES[voice]

        clean = self.clean_text(text)
        if not clean:
            return TTSResult(success=False, error="Empty text")

        try:
            import edge_tts
            tmpdir = tempfile.gettempdir()
            output = os.path.join(tmpdir, f"edge_tts_{uuid.uuid4().hex}.mp3")

            communicate = edge_tts.Communicate(clean, voice)
            await communicate.save(output)

            if not os.path.exists(output):
                return TTSResult(success=False, error="Generation failed")

            # 获取时长
            duration = 0.0
            try:
                from mutagen.mp3 import MP3
                audio = MP3(output)
                duration = audio.info.length
            except Exception:
                pass

            return TTSResult(
                success=True,
                audio_path=output,
                audio_url=f"/tts/audio/{os.path.basename(output)}",
                duration=duration,
            )
        except Exception as e:
            logger.error(f"Edge TTS error: {e}")
            return TTSResult(success=False, error=str(e))

    async def health(self) -> dict:
        try:
            import edge_tts
            return {"status": "ok", "engine": self.name, "voice": self.voice_id}
        except ImportError:
            return {"status": "error", "engine": self.name, "error": "edge_tts not installed"}


class XiaomiTTS(BaseTTS):
    """小米 MiMo TTS — 在线 API（OpenAI 兼容格式）。"""

    name = "xiaomi"
    description = "小米 TTS（在线）"

    # 预置音色列表
    VOICES = {
        "mimo_default": "mimo_default",  # 默认（中国集群=冰糖）
        "冰糖": "冰糖",    # 中文女声
        "茉莉": "茉莉",    # 中文女声
        "苏打": "苏打",    # 中文男声
        "白桦": "白桦",    # 中文男声
        "Mia": "Mia",      # 英文女声
        "Chloe": "Chloe",  # 英文女声
        "Milo": "Milo",    # 英文男声
        "Dean": "Dean",    # 英文男声
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
        """加载声音克隆参考音频并缓存 base64。优先读取预编码的 .b64 文件。"""
        if self._clone_base64 is not None:
            return self._clone_base64
        if not self.clone_audio_path or not os.path.exists(self.clone_audio_path):
            return ""
        try:
            # 优先读取预编码的 .b64 文件
            b64_path = self.clone_audio_path + ".b64"
            if os.path.exists(b64_path):
                with open(b64_path, "r", encoding="utf-8") as f:
                    self._clone_base64 = f.read().strip()
                logger.info(f"Loaded pre-encoded clone audio: {len(self._clone_base64)} chars")
                return self._clone_base64

            # 没有预编码文件，现场编码
            import base64
            with open(self.clone_audio_path, "rb") as f:
                data = f.read()
            if len(data) > 7 * 1024 * 1024:
                logger.warning(f"Clone audio too large: {len(data)} bytes")
                return ""
            b64 = base64.b64encode(data).decode("utf-8")
            ext = os.path.splitext(self.clone_audio_path)[1].lower()
            mime = "audio/mpeg" if ext == ".mp3" else "audio/wav"
            self._clone_base64 = f"data:{mime};base64,{b64}"

            # 保存预编码文件供下次使用
            try:
                with open(b64_path, "w", encoding="utf-8") as f:
                    f.write(self._clone_base64)
                logger.info(f"Saved pre-encoded clone audio: {b64_path}")
            except Exception:
                pass

            return self._clone_base64
        except Exception as e:
            logger.error(f"Load clone audio error: {e}")
            return ""

    async def synthesize(self, text: str, **kwargs) -> TTSResult:
        """调用小米 MiMo TTS API。"""
        clean = self.clean_text(text)
        if not clean:
            return TTSResult(success=False, error="Empty text")

        if not self.api_key:
            return TTSResult(success=False, error="小米 TTS API Key 未配置")

        voice = kwargs.get("voice", self.voice)
        style = kwargs.get("style", "")  # 风格指令（自然语言）
        clone_audio = kwargs.get("clone_audio", "")  # 临时克隆音频（base64）
        mode = kwargs.get("mode", "auto")  # preset=预设, clone=克隆, auto=自动

        # 根据模式判断是否使用声音克隆
        if mode == "preset":
            use_clone = False
        elif mode == "clone":
            use_clone = True
        else:  # auto
            use_clone = bool(clone_audio or self.clone_audio_path)

        if use_clone and not clone_audio:
            clone_audio = self._load_clone_audio()

        model = "mimo-v2.5-tts-voiceclone" if use_clone else "mimo-v2.5-tts"
        voice_value = clone_audio if use_clone else voice

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                messages = []
                # user message: 风格指令（可选）
                if style:
                    messages.append({"role": "user", "content": style})
                # assistant message: 要合成的文本
                messages.append({"role": "assistant", "content": clean})

                payload = {
                    "model": model,
                    "messages": messages,
                    "audio": {
                        "format": "wav",
                        "voice": voice_value,
                    },
                }

                headers = {
                    "api-key": self.api_key,
                    "Content-Type": "application/json",
                }

                resp = await client.post(self.api_url, json=payload, headers=headers)

                if resp.status_code != 200:
                    error_text = resp.text[:200]
                    return TTSResult(success=False, error=f"API {resp.status_code}: {error_text}")

                data = resp.json()

                # 解析返回的音频数据
                try:
                    audio_data = data["choices"][0]["message"]["audio"]["data"]
                except (KeyError, IndexError) as e:
                    return TTSResult(success=False, error=f"Invalid response format: {e}")

                # base64 解码并保存
                import base64
                audio_bytes = base64.b64decode(audio_data)

                tmpdir = tempfile.gettempdir()
                output = os.path.join(tmpdir, f"xiaomi_tts_{uuid.uuid4().hex}.wav")
                with open(output, "wb") as f:
                    f.write(audio_bytes)

                # 获取时长
                duration = 0.0
                try:
                    import wave
                    with wave.open(output, "rb") as wf:
                        duration = wf.getnframes() / wf.getframerate()
                except Exception:
                    pass

                return TTSResult(
                    success=True,
                    audio_path=output,
                    audio_url=f"/tts/audio/{os.path.basename(output)}",
                    duration=duration,
                )
        except httpx.TimeoutException:
            return TTSResult(success=False, error="小米 TTS 请求超时")
        except Exception as e:
            logger.error(f"Xiaomi TTS error: {e}")
            return TTSResult(success=False, error=str(e))

    async def health(self) -> dict:
        if not self.api_key:
            return {"status": "not_configured", "engine": self.name, "error": "API Key 未设置"}
        return {"status": "ok", "engine": self.name, "voice": self.voice}


# ===== 引擎注册表 =====

TTS_ENGINES = {
    "off": None,
    "edge": EdgeTTS,
    "xiaomi": XiaomiTTS,
}

ENGINE_LABELS = {
    "off": "关闭语音",
    "edge": "Edge TTS（免费在线）",
    "xiaomi": "小米 TTS（在线）",
}


def create_tts_engine(engine: str, **config) -> Optional[BaseTTS]:
    """根据名称创建 TTS 引擎实例。"""
    if engine == "off" or engine not in TTS_ENGINES:
        return None
    cls = TTS_ENGINES[engine]
    try:
        return cls(**config)
    except Exception as e:
        logger.error(f"Failed to create TTS engine {engine}: {e}")
        return None
