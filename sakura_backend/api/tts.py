"""TTS API — 多引擎语音合成。"""
import os
import re
import time
import asyncio
import tempfile
import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from pydantic import BaseModel

from core.tts_adapters import (
    TTS_ENGINES, ENGINE_LABELS, BaseTTS, TTSResult,
    EdgeTTS, XiaomiTTS,
    _strip_markdown,
)
from core.db import get_config, set_config

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/tts", tags=["tts"])

AUDIO_TTL = 600
import asyncio as _asyncio
_lock = _asyncio.Lock()

# 当前引擎实例（懒加载）
_engine: BaseTTS = None
_engine_name: str = ""


def _get_engine_name() -> str:
    """从配置获取当前 TTS 引擎名。"""
    try:
        voice_cfg = get_config("voice", {})
        return voice_cfg.get("tts_engine", "off")
    except Exception:
        return os.environ.get("TTS_BACKEND", "off")


def _get_engine_config() -> dict:
    """获取当前引擎配置。"""
    try:
        voice_cfg = get_config("voice", {})
        return {
            "api_key": voice_cfg.get("tts_api_key", ""),
            "voice": voice_cfg.get("tts_voice", ""),
            "server_url": voice_cfg.get("tts_server_url", "http://127.0.0.1:9880"),
            "api_url": voice_cfg.get("tts_api_url", ""),
            "clone_audio_path": get_config("tts_clone_audio", ""),
        }
    except Exception:
        return {}


def _get_engine() -> BaseTTS:
    """获取当前 TTS 引擎（懒加载，配置变更时自动切换）。"""
    global _engine, _engine_name
    name = _get_engine_name()
    if name != _engine_name or _engine is None:
        config = _get_engine_config()
        _engine = _create_engine(name, config)
        _engine_name = name
    return _engine


def _create_engine(name: str, config: dict) -> BaseTTS:
    """创建引擎实例。"""
    if name == "off" or name not in TTS_ENGINES:
        return None
    cls = TTS_ENGINES[name]
    # 过滤掉不属于该引擎的参数
    import inspect
    sig = inspect.signature(cls.__init__)
    valid_params = set(sig.parameters.keys()) - {'self'}
    filtered = {k: v for k, v in config.items() if k in valid_params and v is not None}
    try:
        return cls(**filtered)
    except Exception as e:
        logger.error(f"Create engine {name} failed: {e}")
        return None


# ===== Pydantic 模型 =====

class TTSRequest(BaseModel):
    text: str
    # 通用参数
    voice: str = ""
    speed: float = 1.0
    affection: int = 0
    trust: int = 50
    # 模式：preset=预设音色, clone=声音克隆, auto=自动（默认）
    mode: str = "auto"


class TTSResponse(BaseModel):
    success: bool
    audio_url: str = ""
    audio_path: str = ""
    duration: float = 0.0
    inference_time: float = 0.0
    engine: str = ""
    error: str = ""


class EngineInfo(BaseModel):
    name: str
    label: str
    available: bool


# ===== API 端点 =====

@router.get("/engines")
async def list_engines():
    """列出所有可用 TTS 引擎。"""
    engines = []
    for name, label in ENGINE_LABELS.items():
        engines.append(EngineInfo(
            name=name,
            label=label,
            available=name in TTS_ENGINES and name != "off",
        ))
    current = _get_engine_name()
    return {"engines": engines, "current": current}


@router.get("/health")
async def health():
    """检查当前 TTS 引擎状态。"""
    engine = _get_engine()
    if engine is None:
        return {"status": "off", "engine": "off", "message": "TTS 已关闭"}
    return await engine.health()


@router.post("/tts", response_model=TTSResponse)
async def generate_tts(request: TTSRequest):
    """生成语音。"""

    engine = _get_engine()
    if engine is None:
        return TTSResponse(success=False, error="TTS 未启用，请在设置中选择 TTS 引擎")

    async with _lock:
        kwargs = {}
        # Edge TTS 专用参数
        if engine.name == "edge":
            if request.voice:
                kwargs["voice"] = request.voice
        # 小米 TTS 专用参数
        elif engine.name == "xiaomi":
            if request.voice:
                kwargs["voice"] = request.voice
            kwargs["speed"] = request.speed
            kwargs["mode"] = request.mode

        result: TTSResult = await engine.synthesize(request.text, **kwargs)

        # 清理旧文件
        _cleanup_old_audio()

        return TTSResponse(
            success=result.success,
            audio_url=result.audio_url,
            audio_path=result.audio_path,
            duration=result.duration,
            inference_time=result.inference_time,
            engine=engine.name,
            error=result.error,
        )


@router.get("/audio/{filename}")
async def get_audio(filename: str):
    """返回音频文件。"""
    safe = Path(filename).name
    if not safe or safe != filename or safe.startswith("."):
        raise HTTPException(400, "Invalid filename")

    # 在多个目录搜索
    for d in [tempfile.gettempdir()]:
        audio_path = Path(d) / safe
        if audio_path.exists():
            # 根据扩展名设置 MIME
            ext = audio_path.suffix.lower()
            mime_map = {".wav": "audio/wav", ".mp3": "audio/mpeg", ".ogg": "audio/ogg"}
            mime = mime_map.get(ext, "audio/wav")
            return FileResponse(str(audio_path), media_type=mime)

    raise HTTPException(404, "Audio file not found")


@router.post("/upload-voice")
async def upload_voice_clone(file: UploadFile = File(...)):
    """上传声音克隆参考音频（小米 TTS voiceclone 专用）。"""
    if not file.filename:
        raise HTTPException(400, "No file")

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in (".wav", ".mp3"):
        raise HTTPException(400, "仅支持 wav 和 mp3 格式")

    # 保存到固定位置
    save_dir = Path(__file__).parent.parent / "data" / "voice_clone"
    save_dir.mkdir(parents=True, exist_ok=True)
    save_path = save_dir / f"clone_ref{ext}"

    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(400, "文件过大（最大 10MB）")

    with open(save_path, "wb") as f:
        f.write(content)

    # 单独存储克隆音频路径（不嵌套在 voice 下，避免被 saveVoice 覆盖）
    set_config("tts_clone_audio", str(save_path))

    # 清除引擎缓存，使其重新加载
    global _engine, _engine_name
    _engine = None
    _engine_name = ""

    return {"status": "ok", "path": str(save_path), "size": len(content)}


def _cleanup_old_audio():
    tmpdir = Path(tempfile.gettempdir())
    now = time.time()
    try:
        for prefix in ["edge_tts_", "xiaomi_tts_"]:
            for f in tmpdir.glob(f"{prefix}*"):
                if f.suffix in (".wav", ".mp3", ".ogg"):
                    if now - f.stat().st_mtime > AUDIO_TTL:
                        f.unlink(missing_ok=True)
    except Exception:
        pass
