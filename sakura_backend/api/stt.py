"""STT API — speech-to-text via Vosk offline recognition."""
import json
import logging
import subprocess
import tempfile
import threading
from pathlib import Path

from fastapi import APIRouter, UploadFile, File
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/stt", tags=["stt"])

SCRIPT_DIR = Path(__file__).parent.parent
# Vosk model path points to the actual model (am/final.mdl + conf/)
_VOSK_BASE = SCRIPT_DIR / "data" / "voice" / "vosk-model" / "vosk-api-0.3.50"
MODEL_PATH = _VOSK_BASE / "vosk-model-small-cn-0.22" / "vosk-model-small-cn-0.22"

_model = None
_model_lock = threading.Lock()


def _get_model():
    global _model
    if _model is None:
        with _model_lock:
            if _model is None:
                import vosk
                if not MODEL_PATH.exists():
                    raise FileNotFoundError(f"Vosk model not found: {MODEL_PATH}")
                _model = vosk.Model(str(MODEL_PATH))
    return _model


def _convert_to_pcm(audio_data: bytes) -> bytes:
    """Convert browser audio (webm/opus/etc) to 16kHz mono PCM WAV for Vosk."""
    with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as src:
        src.write(audio_data)
        src_path = src.name
    dst_path = src_path + ".wav"
    try:
        result = subprocess.run(
            ["ffmpeg", "-y", "-i", src_path, "-ar", "16000", "-ac", "1",
             "-f", "wav", dst_path],
            capture_output=True, timeout=15,
        )
        if Path(dst_path).exists() and Path(dst_path).stat().st_size > 0:
            with open(dst_path, "rb") as f:
                return f.read()
    except subprocess.TimeoutExpired:
        logger.warning("ffmpeg timed out, using raw audio")
    except FileNotFoundError:
        logger.warning("ffmpeg not installed")
    except Exception as e:
        logger.warning(f"ffmpeg conversion failed: {e}")
    finally:
        Path(src_path).unlink(missing_ok=True)
        Path(dst_path).unlink(missing_ok=True)
    raise RuntimeError("ffmpeg not installed - voice input unavailable")


class STTResponse(BaseModel):
    success: bool
    text: str = ""
    error: str = ""


@router.get("/health")
async def health():
    if MODEL_PATH.exists():
        return {"status": "ok", "model_path": str(MODEL_PATH)}
    return {"status": "error", "message": f"Model not found: {MODEL_PATH}"}


@router.post("/recognize", response_model=STTResponse)
async def recognize(file: UploadFile = File(...)):
    try:
        model = _get_model()

        audio_data = await file.read()
        if not audio_data:
            return STTResponse(success=False, error="Empty audio data")
        if len(audio_data) > 10 * 1024 * 1024:
            return STTResponse(success=False, error="Audio file too large (max 10MB)")

        pcm_data = _convert_to_pcm(audio_data)
        import vosk
        rec = vosk.KaldiRecognizer(model, 16000)
        rec.AcceptWaveform(pcm_data)

        result = json.loads(rec.FinalResult())
        text = result.get("text", "").strip()

        return STTResponse(success=True, text=text)
    except FileNotFoundError as e:
        return STTResponse(success=False, error=str(e))
    except Exception as e:
        logger.error(f"STT error: {e}")
        return STTResponse(success=False, error=str(e))
