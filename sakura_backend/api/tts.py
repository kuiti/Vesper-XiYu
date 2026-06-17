# api/tts.py — 多引擎 TTS API
"""统一语音合成 API，支持多引擎切换。"""
import os
import time
import asyncio
import tempfile
import logging
import threading
from core.retry import silent_exc
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from pydantic import BaseModel

from core.tts import (
    TTS_ENGINES, ENGINE_LABELS, ENGINE_FEATURES, BaseTTS, TTSResult,
    get_cleanup_prefixes,
)
from core.voice_emotion import get_voice_preset
from core.db import get_config, set_config

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/tts", tags=["tts"])

AUDIO_TTL = 600  # 清理 10 分钟前的临时音频
_lock = asyncio.Lock()
_engine_lock = threading.Lock()

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
    """获取当前引擎的通用配置。"""
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
    with _engine_lock:
        if name != _engine_name or _engine is None:
            config = _get_engine_config()
            _engine = _create_engine(name, config)
            _engine_name = name
    return _engine


def _create_engine(name: str, config: dict) -> BaseTTS:
    """创建引擎实例，自动过滤无效参数。"""
    if name == "off" or name not in TTS_ENGINES:
        return None
    cls = TTS_ENGINES[name]
    import inspect
    sig = inspect.signature(cls.__init__)
    valid_params = set(sig.parameters.keys()) - {'self'}
    filtered = {k: v for k, v in config.items() if k in valid_params and v is not None}
    try:
        return cls(**filtered)
    except Exception as e:
        logger.error(f"创建引擎 {name} 失败: {e}")
        return None


# ===== Pydantic 模型 =====

class TTSRequest(BaseModel):
    text: str
    voice: str = ""
    speed: float = 1.0
    affection: int = 0
    trust: int = 50
    mode: str = "auto"           # preset / clone / auto
    emotion: str = ""            # 情感（支持的引擎可用）
    style: str = ""              # 风格描述（自然语言）
    lang: str = "zh"             # 语言
    ref_audio: str = ""          # 克隆参考音频路径/ID
    prompt_text: str = ""        # 参考音频的文本（GPT-SoVITS）


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
    needs_key: bool = False
    needs_local: bool = False
    supports_clone: bool = False
    supports_emotion: bool = False


# ===== API 端点 =====

@router.get("/engines")
async def list_engines():
    """列出所有可用 TTS 引擎及其特性。"""
    engines = []
    for name, label in ENGINE_LABELS.items():
        feat = ENGINE_FEATURES.get(name, {})
        engines.append(EngineInfo(
            name=name,
            label=label,
            available=name in TTS_ENGINES and name != "off",
            needs_key=feat.get("needs_key", False),
            needs_local=feat.get("needs_local", False),
            supports_clone=feat.get("supports_clone", False),
            supports_emotion=feat.get("supports_emotion", False),
        ))
    current = _get_engine_name()
    return {"engines": engines, "current": current}


@router.get("/health")
async def health():
    engine = _get_engine()
    if engine is None:
        return {"status": "off", "engine": "off", "message": "TTS 已关闭"}
    return await engine.health()


@router.post("/tts", response_model=TTSResponse)
async def generate_tts(request: TTSRequest):
    """生成语音（自动选择引擎参数）。"""
    engine = _get_engine()
    if engine is None:
        return TTSResponse(success=False, error="TTS 未启用，请在设置中选择 TTS 引擎")

    async with _lock:
        kwargs = {}
        eng = engine.name

        # ── 通用参数 ──
        if request.voice:
            kwargs["voice"] = request.voice
        if request.speed != 1.0:
            kwargs["speed"] = request.speed
        if request.emotion:
            kwargs["emotion"] = request.emotion

        # ── 引擎专用参数 ──
        if eng == "edge":
            # 根据好感度自动选音色
            if not request.voice:
                aff, tr = request.affection, request.trust
                if aff == 0 and tr == 50:
                    try:
                        from core.relationship import get_relationship
                        aff, tr = get_relationship()
                    except Exception as e:
                        silent_exc("generate_tts", e)
                preset = get_voice_preset(aff, tr)
                edge_voice_map = {
                    "verylow": "zh-CN-YunxiNeural",
                    "low": "zh-CN-XiaoxiaoNeural",
                    "high": "zh-CN-XiaoyiNeural",
                }
                kwargs["voice"] = edge_voice_map.get(preset, "zh-CN-XiaoxiaoNeural")

        elif eng == "xiaomi":
            kwargs["mode"] = request.mode
            if request.style:
                kwargs["style"] = request.style

        elif eng in ("gpt_sovits",):
            kwargs["lang"] = request.lang
            if request.ref_audio:
                kwargs["ref_audio"] = request.ref_audio
            if request.prompt_text:
                kwargs["prompt_text"] = request.prompt_text

        elif eng in ("cosyvoice",):
            if request.emotion:
                kwargs["emotion"] = request.emotion

        elif eng == "fish_audio":
            if request.ref_audio:
                kwargs["reference_audio"] = request.ref_audio

        elif eng == "baidu":
            if request.speed != 1.0:
                kwargs["speed"] = request.speed

        elif eng == "aliyun":
            if request.speed != 1.0:
                kwargs["speed"] = request.speed

        elif eng == "volcano":
            if request.speed != 1.0:
                kwargs["speed"] = request.speed

        elif eng == "spark":
            if request.speed != 1.0:
                kwargs["speed"] = request.speed

        result: TTSResult = await engine.synthesize(request.text, **kwargs)
        _cleanup_old_audio()

        return TTSResponse(
            success=result.success,
            audio_url=result.audio_url,
            audio_path=result.audio_path,
            duration=result.duration,
            inference_time=result.inference_time,
            engine=eng,
            error=result.error,
        )


@router.get("/audio/{filename}")
async def get_audio(filename: str):
    """返回音频文件。"""
    safe = Path(filename).name
    if not safe or safe != filename or safe.startswith("."):
        raise HTTPException(400, "文件名无效")

    for d in [tempfile.gettempdir()]:
        audio_path = Path(d) / safe
        if audio_path.exists():
            ext = audio_path.suffix.lower()
            mime_map = {".wav": "audio/wav", ".mp3": "audio/mpeg", ".ogg": "audio/ogg"}
            return FileResponse(str(audio_path), media_type=mime_map.get(ext, "audio/wav"))

    raise HTTPException(404, "音频文件未找到")


@router.post("/upload-voice")
async def upload_voice_clone(file: UploadFile = File(...)):
    """上传声音克隆参考音频。"""
    if not file.filename:
        raise HTTPException(400, "未选择文件")
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in (".wav", ".mp3", ".ogg"):
        raise HTTPException(400, "仅支持 wav/mp3/ogg 格式")

    save_dir = Path(__file__).parent.parent / "data" / "voice_clone"
    save_dir.mkdir(parents=True, exist_ok=True)
    ext_clean = ext if ext in (".wav", ".mp3") else ".wav"
    save_path = save_dir / f"clone_ref{ext_clean}"

    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(400, "文件过大（最大 10MB）")

    with open(save_path, "wb") as f:
        f.write(content)

    set_config("tts_clone_audio", str(save_path))

    # 清除引擎缓存
    global _engine, _engine_name
    _engine = None
    _engine_name = ""

    return {"status": "ok", "path": str(save_path), "size": len(content)}


def _cleanup_old_audio():
    """清理所有引擎的过期临时音频文件。"""
    tmpdir = Path(tempfile.gettempdir())
    now = time.time()
    try:
        for prefix in get_cleanup_prefixes():
            for f in tmpdir.glob(f"{prefix}*"):
                if f.suffix in (".wav", ".mp3", ".ogg"):
                    if now - f.stat().st_mtime > AUDIO_TTL:
                        f.unlink(missing_ok=True)
    except Exception as e:
        silent_exc("_cleanup_old_audio", e)
