"""引擎注册表和工厂"""

import asyncio
from typing import Any

from app.engines.ai import AIEngine, OpenAIProvider
from app.observability.logging import get_logger

logger = get_logger(__name__)


class EngineRegistry:
    """引擎注册表 - 管理和缓存 AI 引擎实例"""

    def __init__(self):
        self._engines: dict[str, AIEngine] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    async def get_or_create(self, engine_type: str, config: dict[str, Any]) -> AIEngine:
        """获取或创建引擎实例"""
        # 确保只有一个线程创建引擎
        if engine_type not in self._locks:
            self._locks[engine_type] = asyncio.Lock()

        async with self._locks[engine_type]:
            # 检查缓存
            if engine_type in self._engines:
                return self._engines[engine_type]

            # 创建新实例
            engine = self._create_engine(engine_type, config)
            await engine.initialize()

            self._engines[engine_type] = engine
            logger.info("Engine created and cached", engine_type=engine_type)
            return engine

    def _create_engine(self, engine_type: str, config: dict[str, Any]) -> AIEngine:
        """根据类型创建引擎"""
        if engine_type == "openai":
            api_key = config.get("api_key")
            base_url = config.get("base_url", "https://api.openai.com/v1")
            if not api_key:
                raise ValueError("OpenAI API key is required")
            return OpenAIProvider(api_key=api_key, base_url=base_url)

        raise ValueError(f"Unknown engine type: {engine_type}")

    async def get(self, engine_type: str) -> AIEngine | None:
        """获取已缓存的引擎"""
        return self._engines.get(engine_type)

    async def close_all(self) -> None:
        """关闭所有引擎"""
        for engine in self._engines.values():
            try:
                await engine.close()
            except Exception as e:
                logger.error("Error closing engine", error=str(e))
        self._engines.clear()

    async def health_check(self, engine_type: str) -> bool:
        """引擎健康检查"""
        engine = self._engines.get(engine_type)
        if not engine:
            return False
        try:
            return await engine.health_check()
        except Exception as e:
            logger.error("Health check failed", engine_type=engine_type, error=str(e))
            return False


# 全局引擎注册表
engine_registry = EngineRegistry()
