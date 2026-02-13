"""Task queue service backed by Redis."""

import json
from typing import Any, Optional

from app.observability.logging import get_logger
from app.storage.redis import redis_manager

logger = get_logger(__name__)


class TaskQueueService:
    """Simple Redis-based task queue."""

    def __init__(self):
        pass

    async def enqueue(self, queue_name: str, task: dict[str, Any]) -> bool:
        """Enqueue a task to the specified queue."""
        redis = redis_manager.get_client()
        if not redis:
            logger.warning(f"Redis is not available, dropping task for queue {queue_name}")
            return False

        try:
            payload = json.dumps(task)
            await redis.lpush(queue_name, payload)
            # Optional: Trim queue if too long?
            return True
        except Exception as e:
            logger.error(f"Failed to enqueue task to {queue_name}: {e}")
            return False

    async def dequeue(self, queue_name: str, timeout: int = 5) -> Optional[dict[str, Any]]:
        """Dequeue a task from the specified queue (blocking with timeout)."""
        redis = redis_manager.get_client()
        if not redis:
            return None

        try:
            # brpop returns (key, value)
            result = await redis.brpop(queue_name, timeout=timeout)
            if result:
                _, payload = result
                return json.loads(payload)
            return None
        except Exception as e:
            # Don't log timeout errors as errors (common in loop)
            if "timeout" not in str(e).lower():
                logger.error(f"Failed to dequeue from {queue_name}: {e}")
            return None
        
    async def get_queue_size(self, queue_name: str) -> int:
        """Get current queue size."""
        redis = redis_manager.get_client()
        if not redis:
            return 0
        return await redis.llen(queue_name)


task_queue = TaskQueueService()
