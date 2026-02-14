"""引擎注册表和工厂"""

import asyncio
from typing import Any

from app.core.config.manager import get_config
from app.engines.ai import AIEngine, MockProvider, OpenAIProvider
from app.engines.chat_memory import ChatMemoryEngine, NullChatMemoryEngine
from app.engines.chat_memory.mem0 import Mem0ChatMemoryEngine
from app.engines.knowledge import KnowledgeEngine, NullKnowledgeEngine
from app.engines.knowledge.cognee import CogneeKnowledgeEngine
from app.engines.user_profile import NullUserProfileEngine, UserProfileEngine
from app.engines.user_profile.memobase import MemobaseUserProfileEngine
from app.engines.voice import STTEngine, TTSEngine
from app.engines.voice.stt.openai import OpenAISTTEngine
from app.engines.voice.tts.openai import OpenAITTSEngine
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
        
        # Voice Engines
        self._stt_engines: dict[str, STTEngine] = {}
        self._stt_locks: dict[str, asyncio.Lock] = {}
        self._tts_engines: dict[str, TTSEngine] = {}
        self._tts_locks: dict[str, asyncio.Lock] = {}

    async def get_or_create(self, engine_type: str, config: dict[str, Any]) -> AIEngine:
        """获取或创建引擎实例"""
        engine_key = self._engine_cache_key(engine_type, config)

        # 确保只有一个线程创建引擎
        if engine_key not in self._locks:
            self._locks[engine_key] = asyncio.Lock()

        async with self._locks[engine_key]:
            # 检查缓存
            if engine_key in self._engines:
                return self._engines[engine_key]

            # 创建新实例
            engine = self._create_engine(engine_type, config)
            await engine.initialize()

            self._engines[engine_key] = engine
            logger.info("Engine created and cached", engine_key=engine_key)
            return engine

    def _create_engine(self, engine_type: str, config: dict[str, Any]) -> AIEngine:
        """根据类型创建引擎"""
        if engine_type == "openai":
            api_key = config.get("api_key")
            base_url = config.get("base_url", "https://api.openai.com/v1")
            model = config.get("model", "gpt-4")
            if not api_key:
                raise ValueError("OpenAI API key is required")
            return OpenAIProvider(api_key=api_key, base_url=base_url, model=model)
        
        if engine_type == "mock":
            return MockProvider()

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
        if engine_type == "cognee":
            settings = get_config().settings
            api_url = settings.cognee_api_url
            api_token = settings.cognee_api_token
            timeout = config.get("timeout", 5.0)

            if not api_url or not api_token:
                logger.warning("Cognee config missing, falling back to NullEngine", engine="cognee")
                return NullKnowledgeEngine()

            return CogneeKnowledgeEngine(
                api_url=api_url,
                api_token=api_token.get_secret_value(),
                timeout=timeout,
            )

        return NullKnowledgeEngine()

    def _create_user_profile_engine(
        self, engine_type: str, config: dict[str, Any]
    ) -> UserProfileEngine:
        """根据类型创建用户画像引擎"""
        if engine_type == "memobase":
            settings = get_config().settings
            # Assuming memobase uses project_url as base_url
            api_url = settings.memobase_project_url
            api_token = settings.memobase_api_key
            timeout = config.get("timeout", 3.0)

            if not api_url or not api_token:
                logger.warning(
                    "Memobase config missing, falling back to NullEngine", engine="memobase"
                )
                return NullUserProfileEngine()

            return MemobaseUserProfileEngine(
                api_url=api_url,
                api_token=api_token.get_secret_value(),
                timeout=timeout,
            )

        return NullUserProfileEngine()

    def _create_chat_memory_engine(
        self, engine_type: str, config: dict[str, Any]
    ) -> ChatMemoryEngine:
        """根据类型创建聊天记忆引擎"""
        if engine_type == "mem0":
            settings = get_config().settings
            api_url = settings.mem0_api_url
            api_token = settings.mem0_api_key
            timeout = config.get("timeout", 3.0)

            if not api_url or not api_token:
                logger.warning("Mem0 config missing, falling back to NullEngine", engine="mem0")
                return NullChatMemoryEngine()

            return Mem0ChatMemoryEngine(
                api_url=api_url,
                api_token=api_token.get_secret_value(),
                timeout=timeout,
            )

        return NullChatMemoryEngine()

    async def get_or_create_stt(
        self, engine_type: str, config: dict[str, Any]
    ) -> STTEngine | None:
        """Get or create STT engine."""
        if engine_type not in self._stt_locks:
            self._stt_locks[engine_type] = asyncio.Lock()

        async with self._stt_locks[engine_type]:
            if engine_type in self._stt_engines:
                return self._stt_engines[engine_type]

            engine = self._create_stt_engine(engine_type, config)
            if engine:
                self._stt_engines[engine_type] = engine
                logger.info("STT engine created and cached", engine_type=engine_type)
            return engine

    async def get_or_create_tts(
        self, engine_type: str, config: dict[str, Any]
    ) -> TTSEngine | None:
        """Get or create TTS engine."""
        if engine_type not in self._tts_locks:
            self._tts_locks[engine_type] = asyncio.Lock()

        async with self._tts_locks[engine_type]:
            if engine_type in self._tts_engines:
                return self._tts_engines[engine_type]

            engine = self._create_tts_engine(engine_type, config)
            if engine:
                self._tts_engines[engine_type] = engine
                logger.info("TTS engine created and cached", engine_type=engine_type)
            return engine

    def _create_stt_engine(self, engine_type: str, config: dict[str, Any]) -> STTEngine | None:
        """Create STT engine implementation."""
        if engine_type == "openai":
            api_key = get_config().secrets.openai_api_key
            if not api_key:
                logger.warning("OpenAI API key missing, STT disabled")
                return None
            return OpenAISTTEngine(
                api_key=api_key.get_secret_value(),
                model=config.get("model", "whisper-1"),
                timeout=config.get("timeout", 10.0),
            )
        return None

    def _create_tts_engine(self, engine_type: str, config: dict[str, Any]) -> TTSEngine | None:
        """Create TTS engine implementation."""
        if engine_type == "openai":
            api_key = get_config().secrets.openai_api_key
            if not api_key:
                logger.warning("OpenAI API key missing, TTS disabled")
                return None
            return OpenAITTSEngine(
                api_key=api_key.get_secret_value(),
                model=config.get("model", "tts-1"),
                voice=config.get("voice", "alloy"),
                response_format=config.get("response_format", "mp3"),
                timeout=config.get("timeout", 10.0),
            )
        return None

    async def get(self, engine_type: str) -> AIEngine | None:
        """获取已缓存的引擎"""
        return self._engines.get(engine_type)

    @staticmethod
    def _engine_cache_key(engine_type: str, config: dict[str, Any]) -> str:
        model = config.get("model")
        if model:
            return f"{engine_type}:{model}"
        return engine_type

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
