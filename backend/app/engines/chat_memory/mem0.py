"""Mem0 Chat Memory Engine implementation."""

from typing import Any

from app.engines.base_remote import BaseRemoteEngine
from app.engines.chat_memory import ChatMemoryEngine, MemoryItem
from app.observability.logging import get_logger

logger = get_logger(__name__)


class Mem0ChatMemoryEngine(BaseRemoteEngine, ChatMemoryEngine):
    """Mem0 implementation for Chat Memory Engine."""

    def __init__(self, api_url: str, api_token: str, timeout: float = 3.0):
        super().__init__(base_url=api_url, api_key=api_token, timeout=timeout)

    async def initialize(self) -> None:
        """Initialize HTTP client."""
        await super().initialize()
        logger.info("Mem0 engine initialized", base_url=self.base_url)

    async def health_check(self) -> bool:
        """Check if Mem0 is reachable."""
        try:
            resp = await self.client.get("/health")
            return resp.status_code == 200
        except Exception:
            return False

    async def search_memories(
        self,
        query: str,
        user_id: str,
        session_id: str,
        top_k: int = 5,
    ) -> list[MemoryItem]:
        """Search chat memories from Mem0."""

        async def _call():
            payload = {
                "query": query,
                "user_id": user_id,
                "session_id": session_id,
                "top_k": top_k,
            }
            # Assuming standard memory search endpoint
            resp = await self.client.post("/v1/memories/search", json=payload)
            resp.raise_for_status()
            data = resp.json()
            
            # Map response to MemoryItem list
            # Assuming mem0 response format: {"memories": [{"content": "...", "score": 0.8, ...}]}
            results = []
            for item in data.get("memories", []):
                results.append(
                    MemoryItem(
                        content=item.get("memory", item.get("content", "")),
                        score=item.get("score"),
                        source=item.get("metadata", {}).get("source", "mem0"),
                        metadata={
                            "id": item.get("id"),
                            "created_at": item.get("created_at"),
                            **item.get("metadata", {}),
                        },
                    )
                )
            return results

        # Execute safely with cached read
        cache_key = f"search:{user_id}:{session_id}:{query}:{top_k}"
        result = await self._safe_cached_call(cache_key, _call)
        
        # Determine strict type if cache returns raw dicts
        final_results = []
        if result:
            for r in result:
                if isinstance(r, dict):
                    # Reconstruct MemoryItem from dict
                    # Note: Handle field mapping if dict keys differ from dataclass fields
                    # Here assuming direct mapping or subset
                    final_results.append(MemoryItem(**r))
                else:
                    final_results.append(r)
        
        return final_results

    async def add_memory(
        self,
        user_id: str,
        session_id: str,
        messages: list[dict],
    ) -> list[str]:
        """Add chat memory to Mem0."""

        async def _call():
            payload = {
                "user_id": user_id,
                "session_id": session_id,
                "messages": messages,
            }
            # Assuming standard memory add endpoint
            resp = await self.client.post("/v1/memories/add", json=payload)
            resp.raise_for_status()
            data = resp.json()
            return data.get("ids", []) if "ids" in data else [data.get("id")] if "id" in data else []

        result = await self._safe_call(_call)
        return result if result is not None else []
