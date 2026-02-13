"""OpenAI STT Engine implementation."""

from typing import IO

from openai import AsyncOpenAI

from app.engines.voice import STTEngine
from app.observability.logging import get_logger

logger = get_logger(__name__)

class OpenAISTTEngine(STTEngine):
    """OpenAI Whisper STT Engine."""

    def __init__(self, api_key: str, model: str = "whisper-1", timeout: float = 10.0):
        self.client = AsyncOpenAI(api_key=api_key) # Use correct timeout injection if needed
        self.model = model
        self.timeout = timeout

    async def transcribe(self, audio_file: IO[bytes], filename: str = "audio.wav") -> str:
        """Transcribe audio using Whisper."""
        try:
            # OpenAI requires a file-like object with a name attribute or a tuple
            # Ensure audio_file is at start
            if audio_file.seekable():
                audio_file.seek(0)
            
            resp = await self.client.audio.transcriptions.create(
                model=self.model,
                file=(filename, audio_file, "audio/wav"), # Basic mime type, openai checks header usually
                response_format="text"
            )
            # When response_format is text, it returns strict str
            if isinstance(resp, str):
                return resp
            return resp.text # Should not happen with response_format="text"
            
        except Exception as e:
            logger.error(f"OpenAI STT failed: {e}")
            raise
