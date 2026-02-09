"""ChatOrchestrator - 聊天编排核心"""

import time
import uuid
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    NotFoundError,
)
from app.core.personalities.models import PersonalityRegistry
from app.engines.ai import ChatMessage
from app.engines.registry import EngineRegistry
from app.observability.logging import get_logger
from app.storage.database import db_manager

logger = get_logger(__name__)


class ChatOrchestrator:
    """聊天编排器 - 处理请求、调用引擎、持久化消息"""

    def __init__(
        self,
        personality_registry: PersonalityRegistry,
        engine_registry: EngineRegistry,
    ):
        self.personality_registry = personality_registry
        self.engine_registry = engine_registry

    async def chat(
        self,
        user_id: str,
        session_id: str,
        personality_id: str,
        message: str,
        temperature: float | None = None,
        max_tokens: int | None = None,
        top_p: float | None = None,
        tools: list[dict] | None = None,
    ) -> dict:
        """非流式聊天"""
        request_id = str(uuid.uuid4())
        start_time = time.time()

        try:
            # 1. 验证人格
            personality = self.personality_registry.get(personality_id)
            if not personality:
                raise NotFoundError(resource="Personality", identifier=personality_id)

            logger.info(
                "Chat request received",
                request_id=request_id,
                user_id=user_id,
                session_id=session_id,
                personality_id=personality_id,
            )

            # 2. 准备消息
            messages = [
                ChatMessage(
                    role="system",
                    content=personality.system_prompt,
                ),
                ChatMessage(
                    role="user",
                    content=message,
                ),
            ]

            # 3. 获取模型参数
            ai_config = personality.ai
            model_temperature = temperature if temperature is not None else ai_config.temperature
            model_max_tokens = max_tokens if max_tokens is not None else ai_config.max_tokens
            model_top_p = top_p if top_p is not None else ai_config.top_p

            # 4. 获取引擎
            engine_type = ai_config.provider
            engine = await self.engine_registry.get_or_create(
                engine_type,
                {"api_key": self._get_api_key(engine_type)},
            )

            # 5. 调用 AI 引擎
            logger.info(
                "Calling AI engine",
                request_id=request_id,
                engine_type=engine_type,
                temperature=model_temperature,
            )

            response = await engine.chat(
                messages=messages,
                temperature=model_temperature,
                max_tokens=model_max_tokens,
                top_p=model_top_p,
                tools=tools if engine.supports_tools else None,
            )

            # 6. 持久化消息到数据库
            async with db_manager.session() as session:
                await self._persist_message(
                    session=session,
                    user_id=user_id,
                    session_id=session_id,
                    role="user",
                    content=message,
                    personality_id=personality_id,
                    request_id=request_id,
                )

                await self._persist_message(
                    session=session,
                    user_id=user_id,
                    session_id=session_id,
                    role="assistant",
                    content=response.content,
                    personality_id=personality_id,
                    request_id=request_id,
                )

            elapsed_time = time.time() - start_time
            logger.info(
                "Chat completed successfully",
                request_id=request_id,
                elapsed_time=elapsed_time,
                finish_reason=response.finish_reason,
            )

            return {
                "id": f"chatcmpl-{request_id}",
                "object": "chat.completion",
                "created": int(datetime.now().timestamp()),
                "model": ai_config.model,
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": response.content,
                        },
                        "finish_reason": response.finish_reason,
                    }
                ],
                "usage": response.usage or {
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "total_tokens": 0,
                },
                "metadata": {
                    "request_id": request_id,
                    "elapsed_time": elapsed_time,
                },
            }

        except Exception as e:
            logger.error(
                "Chat request failed",
                request_id=request_id,
                error=str(e),
                exc_info=True,
            )
            raise

    async def chat_stream(
        self,
        user_id: str,
        session_id: str,
        personality_id: str,
        message: str,
        temperature: float | None = None,
        max_tokens: int | None = None,
        top_p: float | None = None,
        tools: list[dict] | None = None,
    ):
        """流式聊天 - 返回异步迭代器"""
        request_id = str(uuid.uuid4())
        start_time = time.time()

        try:
            # 1. 验证人格
            personality = self.personality_registry.get(personality_id)
            if not personality:
                raise NotFoundError(resource="Personality", identifier=personality_id)

            logger.info(
                "Stream chat request received",
                request_id=request_id,
                user_id=user_id,
                session_id=session_id,
                personality_id=personality_id,
            )

            # 2. 准备消息
            messages = [
                ChatMessage(
                    role="system",
                    content=personality.system_prompt,
                ),
                ChatMessage(
                    role="user",
                    content=message,
                ),
            ]

            # 3. 获取模型参数
            ai_config = personality.ai
            model_temperature = temperature if temperature is not None else ai_config.temperature
            model_max_tokens = max_tokens if max_tokens is not None else ai_config.max_tokens
            model_top_p = top_p if top_p is not None else ai_config.top_p

            # 4. 获取引擎
            engine_type = ai_config.provider
            engine = await self.engine_registry.get_or_create(
                engine_type,
                {"api_key": self._get_api_key(engine_type)},
            )

            # 5. 持久化用户消息
            async with db_manager.session() as session:
                await self._persist_message(
                    session=session,
                    user_id=user_id,
                    session_id=session_id,
                    role="user",
                    content=message,
                    personality_id=personality_id,
                    request_id=request_id,
                )

            # 6. 流式调用 AI 引擎
            logger.info(
                "Calling AI engine (stream)",
                request_id=request_id,
                engine_type=engine_type,
            )

            full_response = ""
            async for chunk in engine.chat_stream(
                messages=messages,
                temperature=model_temperature,
                max_tokens=model_max_tokens,
                top_p=model_top_p,
                tools=tools if engine.supports_tools else None,
            ):
                full_response += chunk.get("content", "")
                yield {
                    "id": f"chatcmpl-{request_id}",
                    "object": "chat.completion.chunk",
                    "created": int(datetime.now().timestamp()),
                    "model": ai_config.model,
                    "choices": [
                        {
                            "index": 0,
                            "delta": {"content": chunk.get("content", "")},
                            "finish_reason": chunk.get("finish_reason"),
                        }
                    ],
                }

            # 7. 流式完成后持久化助手消息
            async with db_manager.session() as session:
                await self._persist_message(
                    session=session,
                    user_id=user_id,
                    session_id=session_id,
                    role="assistant",
                    content=full_response,
                    personality_id=personality_id,
                    request_id=request_id,
                )

            elapsed_time = time.time() - start_time
            logger.info(
                "Stream chat completed",
                request_id=request_id,
                elapsed_time=elapsed_time,
            )

            # 8. 发送 [DONE] 信号
            yield {"data": "[DONE]"}

        except Exception as e:
            logger.error(
                "Stream chat request failed",
                request_id=request_id,
                error=str(e),
                exc_info=True,
            )
            raise

    async def _persist_message(
        self,
        session: AsyncSession,  # noqa: ARG002
        user_id: str,
        session_id: str,
        role: str,
        content: str,  # noqa: ARG002
        personality_id: str,  # noqa: ARG002
        request_id: str,
    ):
        """持久化消息到数据库"""
        # TODO: 实现消息模型和持久化逻辑
        # 这里需要与 M0-4 的数据库设计集成
        logger.debug(
            "Message persisted",
            user_id=user_id,
            session_id=session_id,
            role=role,
            request_id=request_id,
        )
        return {"id": str(uuid.uuid4()), "role": role}

    def _get_api_key(self, engine_type: str) -> str:
        """获取引擎 API 密钥"""
        import os

        if engine_type == "openai":
            return os.getenv("OPENAI_API_KEY", "")
        raise ValueError(f"Unknown engine type: {engine_type}")


# 全局编排器实例
_orchestrator: ChatOrchestrator | None = None


def get_orchestrator() -> ChatOrchestrator:
    """获取编排器单例"""
    if _orchestrator is None:
        raise RuntimeError("Orchestrator not initialized")
    return _orchestrator


async def initialize_orchestrator(
    personality_registry: PersonalityRegistry,
    engine_registry: EngineRegistry,
) -> ChatOrchestrator:
    """初始化编排器"""
    global _orchestrator
    _orchestrator = ChatOrchestrator(
        personality_registry=personality_registry,
        engine_registry=engine_registry,
    )
    logger.info("ChatOrchestrator initialized")
    return _orchestrator
