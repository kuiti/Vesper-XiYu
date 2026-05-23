"""TTS API — text-to-speech via genie_tts (GPT-SoVITS ONNX)."""
import os
import re
import time
import uuid
import wave
import shutil
import asyncio
import tempfile
import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from core.voice_emotion import get_voice_preset

AUDIO_TTL = 600  # 10 minutes before cleanup

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/tts", tags=["tts"])

SCRIPT_DIR = Path(__file__).parent.parent
DATA_DIR = SCRIPT_DIR / "data" / "voice"
GENIE_DATA_DIR = DATA_DIR / "GenieData"
GENIE_TTS_DIR = DATA_DIR / "Genie-TTS"

os.environ.setdefault("GENIE_DATA_DIR", str(GENIE_DATA_DIR))
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

_genie = None
_loaded = False
_current_preset = {}
_lock = None


def _strip_markdown(text: str) -> str:
    # Remove parenthetical actions/emotions first
    text = re.sub(r'[（(][^）)]*[）)]', '', text)
    text = re.sub(r'【[^】]*】', '', text)
    text = re.sub(r'「[^」]*」', '', text)
    # Remove markdown formatting
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


def _get_genie():
    global _genie
    if _genie is None:
        import genie_tts as g
        _genie = g
    return _genie


class TTSRequest(BaseModel):
    text: str
    character: str = "YUKI"
    affection: int = 0
    trust: int = 50


class TTSResponse(BaseModel):
    success: bool
    audio_url: str = ""
    error: str = ""


def _cleanup_old_audio():
    tmpdir = Path(tempfile.gettempdir())
    now = time.time()
    try:
        for f in tmpdir.glob("sakura_tts_*.wav"):
            if now - f.stat().st_mtime > AUDIO_TTL:
                f.unlink(missing_ok=True)
    except Exception:
        pass


@router.get("/health")
async def health():
    _cleanup_old_audio()
    try:
        genie = _get_genie()
        return {"status": "ok", "genie_tts": True,
                "genie_data": GENIE_DATA_DIR.exists()}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@router.post("/warmup")
async def warmup():
    global _loaded
    if _loaded:
        return {"success": True, "character": "YUKI", "status": "already loaded"}
    try:
        genie = _get_genie()
        model_dir = GENIE_TTS_DIR / "models" / "yuki"
        ref_audio = GENIE_TTS_DIR / "reference" / "yuki_high.wav"

        if not model_dir.exists():
            raise HTTPException(500, f"Model dir not found: {model_dir}")

        genie.load_character(
            character_name="YUKI",
            onnx_model_dir=str(model_dir),
            language="Chinese",
        )
        if ref_audio.exists():
            genie.set_reference_audio(
                character_name="YUKI",
                audio_path=str(ref_audio),
                audio_text="娜塔莎姐姐说，克拉拉也是医生呢",
            )
        _loaded = True
        return {"success": True, "character": "YUKI"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def _tts_chunk(genie, character: str, text: str, path: str):
    genie.tts(character_name=character, text=text, play=False, save_path=path)


def _concat_wavs(wav_paths: list, output_path: str):
    if len(wav_paths) == 1:
        shutil.copy(wav_paths[0], output_path)
        return
    with wave.open(wav_paths[0], 'rb') as ref:
        params = ref.getparams()
    with wave.open(str(output_path), 'wb') as out:
        out.setparams(params)
        for wp in wav_paths:
            with wave.open(wp, 'rb') as w:
                out.writeframes(w.readframes(w.getnframes()))


MAX_CHUNK_CHARS = 50


@router.post("/tts", response_model=TTSResponse)
async def generate_tts(request: TTSRequest):
    global _lock
    if _lock is None:
        _lock = asyncio.Lock()
    async with _lock:
        try:
            genie = _get_genie()
            if not _loaded:
                result = await warmup()
                if not result.get("success"):
                    return TTSResponse(success=False, error=result.get("error", "TTS warmup failed"))

            clean_text = _strip_markdown(request.text)
            if not clean_text:
                return TTSResponse(success=False, error="Empty text after markdown stripping")

            preset = get_voice_preset(request.affection, request.trust)
            _apply_preset(genie, preset)

            character = request.character.upper()
            chunks = [s.strip() for s in re.split(r'(?<=[。！？!?，,])', clean_text) if s.strip()]
            if not chunks:
                chunks = [clean_text]

            tmpdir = Path(tempfile.gettempdir())
            chunk_paths = []
            for i, chunk in enumerate(chunks):
                cp = tmpdir / f"sakura_tts_{uuid.uuid4().hex}.wav"
                _tts_chunk(genie, character, chunk, str(cp))
                chunk_paths.append(str(cp))

            output_path = tmpdir / f"sakura_tts_{uuid.uuid4().hex}.wav"
            _concat_wavs(chunk_paths, str(output_path))

            # Cleanup chunks
            for cp in chunk_paths:
                Path(cp).unlink(missing_ok=True)

            return TTSResponse(success=True, audio_url=f"/tts/audio/{output_path.name}")
        except Exception as e:
            logger.error(f"TTS error: {e}")
            return TTSResponse(success=False, error=str(e))


@router.get("/audio/{filename}")
async def get_audio(filename: str):
    # Prevent path traversal: only allow safe filename chars
    safe = Path(filename).name
    if not safe or safe != filename or safe.startswith("."):
        raise HTTPException(400, "Invalid filename")
    audio_path = Path(tempfile.gettempdir()) / safe
    if not audio_path.exists():
        raise HTTPException(404, "Audio file not found")
    return FileResponse(str(audio_path), media_type="audio/wav")


def _apply_preset(genie, preset: str):
    global _current_preset
    if _current_preset.get("YUKI") == preset:
        return
    ref_dir = GENIE_TTS_DIR / "reference"
    ref_map = {
        "verylow": ("yuki_high.wav", "娜塔莎姐姐说，克拉拉也是医生呢"),
        "low": ("yuki_high.wav", "娜塔莎姐姐说，克拉拉也是医生呢"),
        "high": ("yuki_high.wav", "娜塔莎姐姐说，克拉拉也是医生呢"),
    }
    info = ref_map.get(preset)
    if not info:
        return
    audio_path = ref_dir / info[0]
    if audio_path.exists():
        genie.set_reference_audio("YUKI", audio_path=str(audio_path), audio_text=info[1])
        _current_preset["YUKI"] = preset
