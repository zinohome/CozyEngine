"""OpenAI TTS Engine implementation."""

from typing import AsyncIterator

from openai import AsyncOpenAI

from app.engines.voice import TTSEngine
from app.observability.logging import get_logger

logger = get_logger(__name__)

class OpenAITTSEngine(TTSEngine):
    """OpenAI TTS Engine."""

    def __init__(self, api_key: str, model: str = "tts-1", voice: str = "alloy", response_format: str = "mp3", timeout: float = 10.0):
        self.client = AsyncOpenAI(api_key=api_key)
        self.model = model
        self.voice = voice
        self.response_format = response_format
        self.timeout = timeout

    async def generate(self, text: str, voice: str | None = None) -> bytes:
        """Generate audio bytes."""
        try:
            resp = await self.client.audio.speech.create(
                model=self.model,
                voice=voice or self.voice,
                input=text,
                response_format=self.response_format
            )
            return resp.content
        except Exception as e:
            logger.error(f"OpenAI TTS failed: {e}")
            raise

    async def generate_stream(self, text: str, voice: str | None = None) -> AsyncIterator[bytes]:
        """Generate audio stream."""
        try:
            async with self.client.audio.speech.with_streaming_response.create(
                model=self.model,
                voice=voice or self.voice,
                input=text,
                response_format=self.response_format
            ) as response:
                async for chunk in response.iter_bytes():
                    yield chunk
        except Exception as e:
            logger.error(f"OpenAI TTS stream failed: {e}")
            raise
