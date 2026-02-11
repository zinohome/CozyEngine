"""Chat memory engine interfaces."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class MemoryItem:
    """Memory search result."""

    content: str
    score: float | None = None
    source: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class ChatMemoryEngine(ABC):
    """Chat memory engine base interface."""

    @abstractmethod
    async def initialize(self) -> None:
        """Initialize engine resources."""
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """Health check."""
        pass

    @abstractmethod
    async def close(self) -> None:
        """Release resources."""
        pass

    @abstractmethod
    async def search_memories(
        self,
        query: str,
        user_id: str,
        session_id: str,
        top_k: int = 5,
    ) -> list[MemoryItem]:
        """Search chat memories."""
        pass

    @abstractmethod
    async def add_memory(
        self,
        user_id: str,
        session_id: str,
        messages: list[dict],
    ) -> list[str]:
        """Add chat memories."""
        pass


class NullChatMemoryEngine(ChatMemoryEngine):
    """No-op chat memory engine for default usage."""

    async def initialize(self) -> None:
        return None

    async def health_check(self) -> bool:
        return True

    async def close(self) -> None:
        return None

    async def search_memories(
        self,
        query: str,
        user_id: str,
        session_id: str,
        top_k: int = 5,
    ) -> list[MemoryItem]:
        return []

    async def add_memory(
        self,
        user_id: str,
        session_id: str,
        messages: list[dict],
    ) -> list[str]:
        return []


__all__ = ["ChatMemoryEngine", "MemoryItem", "NullChatMemoryEngine"]
