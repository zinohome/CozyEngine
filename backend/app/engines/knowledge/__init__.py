"""Knowledge engine interfaces."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class KnowledgeItem:
    """Knowledge search result."""

    content: str
    score: float | None = None
    source: str | None = None
    dataset_name: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class KnowledgeEngine(ABC):
    """Knowledge engine base interface."""

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
    async def search_knowledge(
        self,
        query: str,
        dataset_names: list[str] | None = None,
        top_k: int = 5,
    ) -> list[KnowledgeItem]:
        """Search knowledge content."""
        pass

    @abstractmethod
    async def add_knowledge(
        self,
        content: str,
        dataset_name: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Add knowledge content."""
        pass


class NullKnowledgeEngine(KnowledgeEngine):
    """No-op knowledge engine for default usage."""

    async def initialize(self) -> None:
        return None

    async def health_check(self) -> bool:
        return True

    async def close(self) -> None:
        return None

    async def search_knowledge(
        self,
        query: str,
        dataset_names: list[str] | None = None,
        top_k: int = 5,
    ) -> list[KnowledgeItem]:
        return []

    async def add_knowledge(
        self,
        content: str,
        dataset_name: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        return ""


__all__ = ["KnowledgeEngine", "KnowledgeItem", "NullKnowledgeEngine"]
