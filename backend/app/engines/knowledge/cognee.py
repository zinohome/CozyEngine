"""Cognee Knowledge Engine implementation."""

from typing import Any

import httpx

from app.engines.base_remote import BaseRemoteEngine
from app.engines.knowledge import KnowledgeEngine, KnowledgeItem
from app.observability.logging import get_logger

logger = get_logger(__name__)


class CogneeKnowledgeEngine(BaseRemoteEngine, KnowledgeEngine):
    """Cognee implementation for Knowledge Engine."""

    def __init__(self, api_url: str, api_token: str, timeout: float = 5.0):
        super().__init__(base_url=api_url, api_key=api_token, timeout=timeout)

    async def initialize(self) -> None:
        """Initialize HTTP client."""
        await super().initialize()
        logger.info("Cognee engine initialized", base_url=self.base_url)

    async def health_check(self) -> bool:
        """Check if Cognee is reachable."""
        try:
            # Assuming standard health check endpoint
            resp = await self.client.get("/health")
            return resp.status_code == 200
        except Exception:
            return False

    async def search_knowledge(
        self,
        query: str,
        dataset_names: list[str] | None = None,
        top_k: int = 5,
    ) -> list[KnowledgeItem]:
        """Search knowledge from Cognee."""
        
        async def _call():
            payload = {
                "query": query,
                "top_k": top_k,
                "dataset_names": dataset_names or [],
            }
            # Assuming standard search endpoint
            resp = await self.client.post("/search", json=payload)
            resp.raise_for_status()
            data = resp.json()
            
            # Map response to KnowledgeItem list
            # Assuming response format: {"results": [{"content": "...", "score": 0.9, ...}]}
            results = []
            for item in data.get("results", []):
                results.append(
                    KnowledgeItem(
                        content=item.get("content", ""),
                        score=item.get("score"),
                        source=item.get("source"),
                        dataset_name=item.get("dataset"),
                        metadata=item.get("metadata", {}),
                    )
                )
            return results

        # Execute safely with cached read
        cache_key = f"search:{query}:{top_k}:{','.join(sorted(dataset_names or []))}"
        result = await self._safe_cached_call(cache_key, _call)
        
        # Reconstruct objects if cache returned dicts
        final_results = []
        if result:
            for r in result:
                if isinstance(r, dict):
                    final_results.append(KnowledgeItem(**r))
                else:
                    final_results.append(r)
        
        return final_results

    async def add_knowledge(
        self,
        content: str,
        dataset_name: str = "default",
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Add knowledge to Cognee."""

        async def _call():
            payload = {
                "content": content,
                "dataset_name": dataset_name,
                "metadata": metadata or {},
            }
            resp = await self.client.post("/add", json=payload)
            resp.raise_for_status()
            return resp.json().get("id", "")

        result = await self._safe_call(_call)
        if result is None:
            raise RuntimeError("Failed to add knowledge (circuit breaker open or error)")
        return result
