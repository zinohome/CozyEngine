"""Voice engines (STT/TTS) interfaces and base classes."""

from abc import ABC, abstractmethod
from typing import IO, AsyncIterator

class STTEngine(ABC):
    """Speech-to-Text Engine Interface."""

    @abstractmethod
    async def transcribe(self, audio_file: IO[bytes], filename: str = "audio.wav") -> str:
        """Transcribe audio file to text."""
        pass

class TTSEngine(ABC):
    """Text-to-Speech Engine Interface."""

    @abstractmethod
    async def generate(self, text: str, voice: str | None = None) -> bytes:
        """Generate audio from text (non-streaming)."""
        pass

    @abstractmethod
    async def generate_stream(self, text: str, voice: str | None = None) -> AsyncIterator[bytes]:
        """Generate audio stream from text."""
        pass
