"""Memobase User Profile Engine implementation."""

from typing import Any

from app.engines.base_remote import BaseRemoteEngine
from app.engines.user_profile import UserProfileEngine, UserProfileResult
from app.observability.logging import get_logger
from app.storage.queue import task_queue

logger = get_logger(__name__)


class MemobaseUserProfileEngine(BaseRemoteEngine, UserProfileEngine):
    """Memobase implementation for User Profile Engine."""

    def __init__(self, api_url: str, api_token: str, timeout: float = 3.0):
        super().__init__(base_url=api_url, api_key=api_token, timeout=timeout)
        self.queue_name = "cozy:queue:profile_updates"

    async def initialize(self) -> None:
        """Initialize HTTP client."""
        await super().initialize()
        logger.info("Memobase engine initialized", base_url=self.base_url)

    async def health_check(self) -> bool:
        """Check if Memobase is reachable."""
        try:
            resp = await self.client.get("/health")
            return resp.status_code == 200
        except Exception:
            return False

    async def get_profile(self, user_id: str, max_token_size: int) -> UserProfileResult:
        """Get user profile from Memobase."""

        async def _call():
            params = {"user_id": user_id, "max_tokens": max_token_size}
            # Assuming standard get profile endpoint
            resp = await self.client.get("/profile", params=params)
            resp.raise_for_status()
            data = resp.json()
            
            return UserProfileResult(
                profile_text=data.get("summary", ""),
                token_size=data.get("tokens"),
                metadata=data.get("metadata", {}),
            )

        # Execute safely with cached read
        cache_key = f"profile:{user_id}:{max_token_size}"
        result = await self._safe_cached_call(cache_key, _call)
        
        # Fallback if failed
        if result is None:
            return UserProfileResult(
                profile_text="",
                metadata={"error": "UserProfileEngine unavailable"},
            )
            
        if isinstance(result, dict):
            return UserProfileResult(**result)
            
        return result

    async def update_profile(self, user_id: str, messages: list[dict]) -> bool:
        """Update user profile asynchronously via queue."""
        payload = {
            "type": "update_profile",
            "user_id": user_id,
            "messages": messages,
            "timestamp": "iso-time-placeholder" # todo
        }
        return await task_queue.enqueue(self.queue_name, payload)

    async def _perform_update(self, payload: dict) -> bool:
        """Actual update logic executed by worker."""
        user_id = payload.get("user_id")
        messages = payload.get("messages")
        
        async def _call():
            data = {"user_id": user_id, "messages": messages}
            resp = await self.client.post("/profile/update", json=data)
            resp.raise_for_status()
            return True

        # Use safe_call (circuit breaker) but no cache needed for write
        result = await self._safe_call(_call)
        return result is True
