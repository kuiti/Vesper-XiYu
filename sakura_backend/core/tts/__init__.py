# core/tts/__init__.py
from __future__ import annotations
import os, re, uuid, wave, tempfile, logging
from abc import ABC, abstractmethod
logger = logging.getLogger(__name__)
def _strip_markdown(text):
    text = re.sub(r'[\uff08(][^\uff09)]*[\uff09)]', '', text)
    text = re.sub(r'\u3010[^\u3011]*\u3011', '', text)
    text = re.sub(r'\u300c[^\u300d]*\u300d', '', text)
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
ENGINE_LABELS = {"off": "\u5173\u95ed\u8bed\u97f3", "edge": "Edge TTS\uff08\u514d\u8d39\u5728\u7ebf\uff09", "openai": "OpenAI TTS\uff08\u5728\u7ebf\uff09", "volcano": "\u706b\u5c71\u5f15\u64ce TTS\uff08\u5728\u7ebf\uff09", "baidu": "\u767e\u5ea6 TTS\uff08\u5728\u7ebf\uff09", "aliyun": "\u963f\u91cc\u4e91 TTS\uff08\u5728\u7ebf\uff09", "fish_audio": "Fish Audio\uff08\u5728\u7ebf\uff0c\u652f\u6301\u514b\u9686\uff09", "cosyvoice": "CosyVoice\uff08\u672c\u5730\u90e8\u7f72\uff09", "gpt_sovits": "GPT-SoVITS\uff08\u672c\u5730\u90e8\u7f72\uff09", "spark": "\u8baf\u98de Spark TTS\uff08\u5728\u7ebf\uff09", "xiaomi": "\u5c0f\u7c73 TTS\uff08\u5728\u7ebf\uff09"}
ENGINE_FEATURES = {name: {"needs_key": getattr(cls, "needs_key", False) if cls else False, "needs_local": getattr(cls, "needs_local", False) if cls else False, "supports_clone": getattr(cls, "supports_clone", False) if cls else False, "supports_emotion": getattr(cls, "supports_emotion", False) if cls else False} for name, cls in TTS_ENGINES.items()}
def create_tts_engine(engine, **config):
    if engine == "off" or engine not in TTS_ENGINES:
        return None
    cls = TTS_ENGINES[engine]
    try:
        return cls(**config)
    except Exception as e:
        logger.error(f"\u521b\u5efa TTS \u5f15\u64ce {engine} \u5931\u8d25: {e}")
        return None
def get_cleanup_prefixes():
    return ["edge_tts_", "openai_tts_", "volcano_tts_", "baidu_tts_", "aliyun_tts_", "fish_tts_", "cosyvoice_tts_", "gptsovits_tts_", "spark_tts_", "xiaomi_tts_"]