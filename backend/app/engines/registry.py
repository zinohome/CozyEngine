"""引擎注册表和工厂"""

import asyncio
from typing import Any

from app.engines.ai import AIEngine, OpenAIProvider
from app.engines.chat_memory import ChatMemoryEngine, NullChatMemoryEngine
from app.engines.knowledge import KnowledgeEngine, NullKnowledgeEngine
from app.engines.user_profile import NullUserProfileEngine, UserProfileEngine
from app.observability.logging import get_logger

logger = get_logger(__name__)


class EngineRegistry:
    """引擎注册表 - 管理和缓存 AI 引擎实例"""

    def __init__(self):
        self._engines: dict[str, AIEngine] = {}
        self._locks: dict[str, asyncio.Lock] = {}
        self._knowledge_engines: dict[str, KnowledgeEngine] = {}
        self._knowledge_locks: dict[str, asyncio.Lock] = {}
        self._user_profile_engines: dict[str, UserProfileEngine] = {}
        self._user_profile_locks: dict[str, asyncio.Lock] = {}
        self._chat_memory_engines: dict[str, ChatMemoryEngine] = {}
        self._chat_memory_locks: dict[str, asyncio.Lock] = {}

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

    async def get_or_create_knowledge(
        self, engine_type: str, config: dict[str, Any]
    ) -> KnowledgeEngine:
        """获取或创建知识引擎实例"""
        if engine_type not in self._knowledge_locks:
            self._knowledge_locks[engine_type] = asyncio.Lock()

        async with self._knowledge_locks[engine_type]:
            if engine_type in self._knowledge_engines:
                return self._knowledge_engines[engine_type]

            engine = self._create_knowledge_engine(engine_type, config)
            await engine.initialize()

            self._knowledge_engines[engine_type] = engine
            logger.info("Knowledge engine created and cached", engine_type=engine_type)
            return engine

    async def get_or_create_user_profile(
        self, engine_type: str, config: dict[str, Any]
    ) -> UserProfileEngine:
        """获取或创建用户画像引擎实例"""
        if engine_type not in self._user_profile_locks:
            self._user_profile_locks[engine_type] = asyncio.Lock()

        async with self._user_profile_locks[engine_type]:
            if engine_type in self._user_profile_engines:
                return self._user_profile_engines[engine_type]

            engine = self._create_user_profile_engine(engine_type, config)
            await engine.initialize()

            self._user_profile_engines[engine_type] = engine
            logger.info("User profile engine created and cached", engine_type=engine_type)
            return engine

    async def get_or_create_chat_memory(
        self, engine_type: str, config: dict[str, Any]
    ) -> ChatMemoryEngine:
        """获取或创建聊天记忆引擎实例"""
        if engine_type not in self._chat_memory_locks:
            self._chat_memory_locks[engine_type] = asyncio.Lock()

        async with self._chat_memory_locks[engine_type]:
            if engine_type in self._chat_memory_engines:
                return self._chat_memory_engines[engine_type]

            engine = self._create_chat_memory_engine(engine_type, config)
            await engine.initialize()

            self._chat_memory_engines[engine_type] = engine
            logger.info("Chat memory engine created and cached", engine_type=engine_type)
            return engine

    def _create_knowledge_engine(
        self, engine_type: str, config: dict[str, Any]
    ) -> KnowledgeEngine:
        """根据类型创建知识引擎"""
        _ = config
        return NullKnowledgeEngine()

    def _create_user_profile_engine(
        self, engine_type: str, config: dict[str, Any]
    ) -> UserProfileEngine:
        """根据类型创建用户画像引擎"""
        _ = config
        return NullUserProfileEngine()

    def _create_chat_memory_engine(
        self, engine_type: str, config: dict[str, Any]
    ) -> ChatMemoryEngine:
        """根据类型创建聊天记忆引擎"""
        _ = config
        return NullChatMemoryEngine()

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
        for engine in self._knowledge_engines.values():
            try:
                await engine.close()
            except Exception as e:
                logger.error("Error closing knowledge engine", error=str(e))
        for engine in self._user_profile_engines.values():
            try:
                await engine.close()
            except Exception as e:
                logger.error("Error closing user profile engine", error=str(e))
        for engine in self._chat_memory_engines.values():
            try:
                await engine.close()
            except Exception as e:
                logger.error("Error closing chat memory engine", error=str(e))

        self._engines.clear()
        self._knowledge_engines.clear()
        self._user_profile_engines.clear()
        self._chat_memory_engines.clear()

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
