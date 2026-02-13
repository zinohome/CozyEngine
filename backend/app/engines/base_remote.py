"""Base class for remote engines with circuit breaker and timeout."""

import asyncio
import time
from abc import ABC

import json
from abc import ABC
from collections import OrderedDict
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Generic, TypeVar

import httpx

from app.core.config.manager import get_config
from app.observability.logging import get_logger
from app.storage.redis import redis_manager

logger = get_logger(__name__)

T = TypeVar("T")


class L1Cache(Generic[T]):
    """Simple L1 memory cache with TTL and LRU eviction."""

    def __init__(self, capacity: int = 100, ttl: float = 60.0):
        self.capacity = capacity
        self.ttl = ttl
        self.cache: OrderedDict[str, tuple[T, float]] = OrderedDict()

    def get(self, key: str) -> T | None:
        if key not in self.cache:
            return None
        
        value, expiry = self.cache[key]
        if time.time() > expiry:
            del self.cache[key]
            return None
        
        self.cache.move_to_end(key)
        return value

    def set(self, key: str, value: T) -> None:
        if key in self.cache:
            self.cache.move_to_end(key)
        
        self.cache[key] = (value, time.time() + self.ttl)
        if len(self.cache) > self.capacity:
            self.cache.popitem(last=False)


class EngineError(Exception):

    """Base engine error."""
    pass


class EngineTimeoutError(EngineError):
    """Engine timeout error."""
    pass


class EngineUnavailableError(EngineError):
    """Engine unavailable error (circuit breaker open)."""
    pass


class CircuitBreaker:
    """Simple circuit breaker."""

    def __init__(self, failure_threshold: int = 5, recovery_timeout: float = 30.0):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time = 0.0
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN

    def allow_request(self) -> bool:
        if self.state == "OPEN":
            if time.time() - self.last_failure_time > self.recovery_timeout:
                self.state = "HALF_OPEN"
                return True
            return False
        return True

    def record_success(self):
        self.failure_count = 0
        self.state = "CLOSED"

    def record_failure(self):
        self.failure_count += 1
        self.last_failure_time = time.time()
        if self.failure_count >= self.failure_threshold:
            self.state = "OPEN"
            logger.warning(
                "Circuit breaker opened",
                failure_count=self.failure_count,
                threshold=self.failure_threshold,
            )


class BaseRemoteEngine(ABC):
    """Base remote engine with HTTP client, circuit breaker, and L1/L2 cache."""

    def __init__(
        self,
        base_url: str,
        api_key: str | None = None,
        timeout: float = 10.0,
        cache_ttl: float = 300.0,
        cache_prefix: str = "engine",
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.circuit_breaker = CircuitBreaker()
        self.l1_cache = L1Cache(capacity=100, ttl=cache_ttl)
        self.cache_ttl = int(cache_ttl)
        self.cache_prefix = cache_prefix
        self.client: httpx.AsyncClient | None = None

    async def initialize(self) -> None:
        """Initialize HTTP client and Redis."""
        if not self.client:
            self.client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout,
                headers={"Authorization": f"Bearer {self.api_key}"} if self.api_key else {},
            )
        # Assuming Redis is globally initialized or handled by app startup

    async def close(self) -> None:
        """Close HTTP client."""
        if self.client:
            await self.client.aclose()
            self.client = None

    async def _safe_call(self, func: Callable[..., Any], *args, **kwargs) -> Any | None:
        """Execute call with circuit breaker and error handling."""
        if not self.circuit_breaker.allow_request():
            logger.warning("Circuit breaker open", engine=self.__class__.__name__)
            return None

        try:
            if not self.client:
                await self.initialize()

            # Execute the function
            result = await func(*args, **kwargs)
            
            self.circuit_breaker.record_success()
            return result

        except (httpx.TimeoutException, asyncio.TimeoutError) as e:
            logger.error("Engine timeout", engine=self.__class__.__name__, error=str(e))
            self.circuit_breaker.record_failure()
            return None
            
        except httpx.HTTPStatusError as e:
            logger.error(
                "Engine HTTP error",
                engine=self.__class__.__name__,
                status=e.response.status_code,
                error=str(e),
            )
            if e.response.status_code >= 500:
                self.circuit_breaker.record_failure()
            return None

        except Exception as e:
            logger.error("Engine error", engine=self.__class__.__name__, error=str(e))
            self.circuit_breaker.record_failure()
            return None

    async def _safe_cached_call(
        self, cache_key: str, func: Callable[..., Any], *args, **kwargs
    ) -> Any | None:
        """Execute call with L1/L2 cache + circuit breaker."""
        full_key = f"{self.cache_prefix}:{cache_key}"

        # 1. Check L1 Cache
        cached = self.l1_cache.get(full_key)
        if cached is not None:
            return cached

        # 2. Check L2 Cache (Redis)
        redis_client = redis_manager.client
        if redis_client:
            try:
                cached_json = await redis_client.get(full_key)
                if cached_json:
                    # Deserialize if stored as JSON string
                    # Note: complex objects need proper serialization
                    # Here assuming simple types or dicts that are json serializable
                    try:
                        val = json.loads(cached_json)
                        self.l1_cache.set(full_key, val)
                        return val
                    except json.JSONDecodeError:
                        pass
            except Exception:
                pass  # Ignore Redis errors

        # 3. Call remote function (with circuit breaker)
        # Re-implement _safe_call logic here because I can't easily wrap `func`
        
        if not self.circuit_breaker.allow_request():
            logger.warning("Circuit breaker open", engine=self.__class__.__name__)
            return None

        try:
            if not self.client:
                await self.initialize()

            result = await func(*args, **kwargs)
            
            self.circuit_breaker.record_success()

            # 4. Update L1/L2 Cache
            if result is not None:
                self.l1_cache.set(full_key, result)
                if redis_client:
                    try:
                        # Serialize result to JSON string if possible
                        # If result is Pydantic model or dataclass, convert to dict first
                        to_store = result
                        if hasattr(result, "model_dump"):
                            to_store = result.model_dump()
                        elif hasattr(result, "to_dict"):
                            to_store = result.to_dict()
                        elif hasattr(result, "__dict__"): # dataclass
                             from dataclasses import asdict
                             to_store = asdict(result)
                            
                        # Use set with expiry
                        await redis_client.set(full_key, json.dumps(to_store), ex=self.cache_ttl)
                    except Exception:
                        pass # Ignore serialization/redis errors

            return result

        except (httpx.TimeoutException, asyncio.TimeoutError) as e:
            logger.error("Engine timeout", engine=self.__class__.__name__, error=str(e))
            self.circuit_breaker.record_failure()
            return None
            
        except httpx.HTTPStatusError as e:
            logger.error(
                "Engine HTTP error",
                engine=self.__class__.__name__,
                status=e.response.status_code,
                error=str(e),
            )
            if e.response.status_code >= 500:
                self.circuit_breaker.record_failure()
            return None

        except Exception as e:
            logger.error("Engine error", engine=self.__class__.__name__, error=str(e))
            self.circuit_breaker.record_failure()
            return None

