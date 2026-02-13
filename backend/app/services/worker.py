"""Async worker service for processing background tasks."""

import asyncio
from typing import Any

from app.engines.registry import engine_registry
# Note: dynamic Dispatch or structural typing is preferred over strict class checks to avoid circular imports if generic
from app.observability.logging import get_logger
from app.storage.queue import task_queue

logger = get_logger(__name__)

PROFILE_QUEUE = "cozy:queue:profile_updates"
MEMORY_QUEUE = "cozy:queue:memory_updates"


class AsyncWorkerService:
    """Service to process background tasks from Redis queues."""

    def __init__(self):
        self.running = False
        self._task = None

    async def start(self):
        """Start the worker loop."""
        if self.running:
            return
        self.running = True
        self._task = asyncio.create_task(self._loop())
        logger.info("AsyncWorkerService started")

    async def stop(self):
        """Stop the worker loop."""
        self.running = False
        if self._task:
            try:
                # Wait for current iteration to finish or timeout
                await asyncio.wait_for(self._task, timeout=5.0)
            except Exception:
                pass
        logger.info("AsyncWorkerService stopped")

    async def _loop(self):
        """Main processing loop."""
        logger.info("AsyncWorker loop running...")
        while self.running:
            try:
                # 1. Process Profile Updates
                # We prioritize one queue or round-robin
                processed_profile = await self._process_queue_item(PROFILE_QUEUE, self._handle_profile_update)
                
                # 2. Process Memory Updates
                processed_memory = await self._process_queue_item(MEMORY_QUEUE, self._handle_memory_update)
                
                # If both were empty, sleep a bit to yield
                if not processed_profile and not processed_memory:
                    await asyncio.sleep(1.0)
                else:
                    # Yield slightly to allow other tasks in event loop
                    await asyncio.sleep(0.01)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in async worker loop: {e}")
                await asyncio.sleep(5)  # Backoff on error

    async def _process_queue_item(self, queue_name: str, handler) -> bool:
        """Process a single item from queue. Returns True if item was processed."""
        # Use short timeout (1s) so we can check other queues / stop signal frequently
        task = await task_queue.dequeue(queue_name, timeout=1)
        if task:
            try:
                await handler(task)
                return True
            except Exception as e:
                logger.error(f"Failed to process task from {queue_name}: {e}")
                # TODO: Implement Dead Letter Queue or Retry logic here
                return True # Consumed but failed
        return False

    async def _handle_profile_update(self, payload: dict):
        engine = engine_registry.get_user_profile_engine()
        # Structural typing: check if it has the internal method
        if hasattr(engine, "_perform_update"):
            user_id = payload.get("user_id", "unknown")
            logger.debug(f"Worker: Processing profile update for user {user_id}")
            await engine._perform_update(payload)
        else:
            # Maybe it's a NullEngine or Mock
            pass

    async def _handle_memory_update(self, payload: dict):
        engine = engine_registry.get_chat_memory_engine()
        if hasattr(engine, "_perform_add"):
            session_id = payload.get("session_id", "unknown")
            logger.debug(f"Worker: Processing memory update for session {session_id}")
            await engine._perform_add(payload)
        else:
            pass


async_worker = AsyncWorkerService()
