# core/tts/edge.py
import os, logging
from . import BaseTTS, TTSResult, _save_audio_bytes, _get_audio_duration, _register_temp_file
logger = logging.getLogger(__name__)
class EdgeTTS(BaseTTS):
    name = "edge"
    description = "Edge TTS"
    needs_key = False
    VOICES = {"xiaoyi": "zh-CN-XiaoyiNeural", "xiaoxiao": "zh-CN-XiaoxiaoNeural", "yunxi": "zh-CN-YunxiNeural", "yunjian": "zh-CN-YunjianNeural"}
    def __init__(self, voice="xiaoxiao", **kwargs):
        self.voice = self.VOICES.get(voice, voice)
    async def synthesize(self, text, **kwargs):
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
            return TTSResult(success=True, audio_path=output, audio_url=f"/tts/audio/{os.path.basename(output)}", duration=duration)
        except Exception as e:
            logger.error(f"Edge TTS: {e}")
            return TTSResult(success=False, error=str(e))
    async def health(self):
        try:
            import edge_tts
            return {"status": "ok", "engine": self.name}
        except ImportError:
            return {"status": "error", "engine": self.name, "error": "edge-tts not installed"}
