"""Redis storage manager."""

import os
from typing import Any

from redis import asyncio as aioredis
from redis.exceptions import ConnectionError, TimeoutError

from app.core.config.manager import get_config
from app.observability.logging import get_logger

logger = get_logger(__name__)


class RedisManager:
    """Redis manager (singleton)."""

    def __init__(self):
        self._redis: aioredis.Redis | None = None
        self._url: str | None = None

    async def initialize(self, redis_url: str | None = None) -> None:
        """Initialize Redis connection."""
        if self._redis is not None:
            return

        self._url = redis_url
        if not self._url:
            # Try to get from config settings first
            try:
                settings = get_config().settings
                self._url = settings.redis_url
            except Exception:
                pass
        
        if not self._url:
            self._url = os.getenv("REDIS_URL")

        if not self._url:
            logger.warning("REDIS_URL not configured, Redis features will be disabled")
            return

        try:
            self._redis = aioredis.from_url(
                self._url,
                encoding="utf-8",
                decode_responses=True,
                max_connections=50,  # Default pool size
                socket_timeout=5.0,
            )
            await self._redis.ping()
            logger.info("Redis connected successfully")
        except (ConnectionError, TimeoutError) as e:
            logger.error("Failed to connect to Redis", error=str(e))
            self._redis = None

    async def close(self) -> None:
        """Close Redis connection."""
        if self._redis:
            await self._redis.close()
            self._redis = None

    async def get(self, key: str) -> Any | None:
        """Get value from Redis."""
        if not self._redis:
            return None
        try:
            return await self._redis.get(key)
        except Exception as e:
            logger.error("Redis get failed", key=key, error=str(e))
            return None

    async def set(self, key: str, value: Any, expire: int | None = None) -> bool:
        """Set value in Redis."""
        if not self._redis:
            return False
        try:
            await self._redis.set(key, value, ex=expire)
            return True
        except Exception as e:
            logger.error("Redis set failed", key=key, error=str(e))
            return False

    @property
    def client(self) -> aioredis.Redis | None:
        return self._redis


redis_manager = RedisManager()
