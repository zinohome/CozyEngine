"""User profile engine interfaces."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class UserProfileResult:
    """User profile result."""

    profile_text: str
    token_size: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class UserProfileEngine(ABC):
    """User profile engine base interface."""

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
    async def get_profile(self, user_id: str, max_token_size: int) -> UserProfileResult:
        """Get user profile."""
        pass

    @abstractmethod
    async def update_profile(self, user_id: str, messages: list[dict]) -> bool:
        """Update user profile."""
        pass


class NullUserProfileEngine(UserProfileEngine):
    """No-op user profile engine for default usage."""

    async def initialize(self) -> None:
        return None

    async def health_check(self) -> bool:
        return True

    async def close(self) -> None:
        return None

    async def get_profile(self, user_id: str, max_token_size: int) -> UserProfileResult:
        return UserProfileResult(profile_text="", token_size=0, metadata={})

    async def update_profile(self, user_id: str, messages: list[dict]) -> bool:
        return False


__all__ = ["UserProfileEngine", "UserProfileResult", "NullUserProfileEngine"]
