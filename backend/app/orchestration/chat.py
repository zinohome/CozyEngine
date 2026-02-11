"""ChatOrchestrator - 聊天编排核心"""

import json
import time
import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config.manager import get_config
from app.core.exceptions import (
    NotFoundError,
)
from app.core.personalities.models import PersonalityRegistry
from app.context.service import ContextService
from app.engines.ai import ChatMessage
from app.engines.registry import EngineRegistry
from app.engines.tools import ToolsEngine
from app.engines.tools.basic import BasicToolsEngine
from app.observability.logging import get_logger
from app.services.audit import AuditService
from app.storage.database import db_manager
from app.storage.models import Message, Session

logger = get_logger(__name__)


class ChatOrchestrator:
    """聊天编排器 - 处理请求、调用引擎、持久化消息"""

    def __init__(
        self,
        personality_registry: PersonalityRegistry,
        engine_registry: EngineRegistry,
        context_service: ContextService | None = None,
    ):
        self.personality_registry = personality_registry
        self.engine_registry = engine_registry
        self.tools_engine: ToolsEngine | None = None
        self.max_tool_iterations = 10  # 默认最大迭代次数
        self.context_service = context_service or ContextService(engine_registry)

    async def initialize_tools_engine(self) -> None:
        """初始化工具引擎"""
        if self.tools_engine is None:
            self.tools_engine = BasicToolsEngine()
            await self.tools_engine.initialize()
            logger.info("Tools engine initialized")

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

            # 2. 获取模型参数
            ai_config = personality.ai
            model_temperature = temperature if temperature is not None else ai_config.temperature
            model_max_tokens = max_tokens if max_tokens is not None else ai_config.max_tokens
            model_top_p = top_p if top_p is not None else ai_config.top_p

            # 3. 构建上下文
            context_bundle = await self.context_service.build_context_bundle(
                user_id=user_id,
                session_id=session_id,
                current_message=message,
                personality=personality,
                max_tokens=model_max_tokens,
                request_id=request_id,
            )
            messages = self.context_service.to_messages(context_bundle, message)

            # 4. 获取引擎
            engine_type = ai_config.provider
            engine = await self.engine_registry.get_or_create(
                engine_type,
                {
                    "api_key": self._get_api_key(engine_type),
                    "base_url": self._get_base_url(engine_type),
                    "model": ai_config.model,
                },
            )

            # 4.5. 准备工具（如果启用）
            allowed_tools = self._get_allowed_tools(personality, tools)
            openai_tools = None
            if allowed_tools and engine.supports_tools:
                await self.initialize_tools_engine()
                if self.tools_engine:
                    openai_tools = self.tools_engine.to_openai_tools(allowed_tools)

            # 5. 调用 AI 引擎（带工具调用循环）
            logger.info(
                "Calling AI engine",
                request_id=request_id,
                engine_type=engine_type,
                temperature=model_temperature,
                tools_enabled=bool(openai_tools),
            )

            # 工具调用循环
            iteration = 0
            while iteration < self.max_tool_iterations:
                response = await engine.chat(
                    messages=messages,
                    temperature=model_temperature,
                    max_tokens=model_max_tokens,
                    top_p=model_top_p,
                    tools=openai_tools,
                )

                # 检查是否有工具调用
                if response.finish_reason == "tool_calls" and response.tool_calls:
                    iteration += 1
                    logger.info(
                        "Tool calls detected",
                        request_id=request_id,
                        iteration=iteration,
                        tool_count=len(response.tool_calls),
                    )

                    # 执行工具调用
                    tool_results = await self._execute_tool_calls(
                        response.tool_calls,
                        user_id,
                        session_id,
                        personality_id,
                        request_id,
                    )

                    # 回填工具调用结果到消息列表
                    messages.append(
                        ChatMessage(
                            role="assistant",
                            content=response.content or "",
                            tool_calls=response.tool_calls,
                        )
                    )
                    for tool_result in tool_results:
                        messages.append(
                            ChatMessage(
                                role="tool",
                                content=tool_result["content"],
                                tool_calls={"id": tool_result["tool_call_id"]},
                            )
                        )

                    # 继续下一轮调用
                    continue

                # 没有工具调用，退出循环
                break

            if iteration >= self.max_tool_iterations:
                logger.warning(
                    "Tool iteration limit reached",
                    request_id=request_id,
                    max_iterations=self.max_tool_iterations,
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
                    "context": context_bundle.metadata,
                    "token_budget": context_bundle.token_budget.sections,
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

            # 2. 获取模型参数
            ai_config = personality.ai
            model_temperature = temperature if temperature is not None else ai_config.temperature
            model_max_tokens = max_tokens if max_tokens is not None else ai_config.max_tokens
            model_top_p = top_p if top_p is not None else ai_config.top_p

            # 3. 构建上下文
            context_bundle = await self.context_service.build_context_bundle(
                user_id=user_id,
                session_id=session_id,
                current_message=message,
                personality=personality,
                max_tokens=model_max_tokens,
                request_id=request_id,
            )
            messages = self.context_service.to_messages(context_bundle, message)

            # 4. 获取引擎
            engine_type = ai_config.provider
            engine = await self.engine_registry.get_or_create(
                engine_type,
                {
                    "api_key": self._get_api_key(engine_type),
                    "base_url": self._get_base_url(engine_type),
                    "model": ai_config.model,
                },
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

            # 6. 准备工具（如果支持）
            openai_tools = None
            if engine.supports_tools and self.tools_engine:
                allowed_tools = self._get_allowed_tools(personality, tools)
                if allowed_tools:
                    openai_tools = self.tools_engine.to_openai_tools(allowed_tools)
                    logger.info(
                        "Tools prepared for stream",
                        request_id=request_id,
                        tool_count=len(allowed_tools),
                    )

            # 7. 工具循环（流式）
            iteration = 0
            full_response = ""
            final_tool_calls = None

            while iteration < self.max_tool_iterations:
                logger.info(
                    "Calling AI engine (stream)",
                    request_id=request_id,
                    engine_type=engine_type,
                    iteration=iteration,
                )

                # 流式调用 AI 引擎
                current_response = ""
                current_tool_calls = None
                finish_reason = None

                async for chunk in engine.chat_stream(
                    messages=messages,
                    temperature=model_temperature,
                    max_tokens=model_max_tokens,
                    top_p=model_top_p,
                    tools=openai_tools,
                ):
                    current_response += chunk.get("content", "")
                    finish_reason = chunk.get("finish_reason")

                    # 检测工具调用（流式chunk可能携带tool_calls）
                    if "tool_calls" in chunk:
                        current_tool_calls = chunk.get("tool_calls")

                    # Yield chunk给客户端
                    yield {
                        "id": f"chatcmpl-{request_id}",
                        "object": "chat.completion.chunk",
                        "created": int(datetime.now().timestamp()),
                        "model": ai_config.model,
                        "choices": [
                            {
                                "index": 0,
                                "delta": {"content": chunk.get("content", "")},
                                "finish_reason": finish_reason,
                            }
                        ],
                    }

                # 检查是否需要工具调用
                if finish_reason == "tool_calls" and current_tool_calls:
                    iteration += 1
                    final_tool_calls = current_tool_calls

                    logger.info(
                        "Tool calls detected in stream",
                        request_id=request_id,
                        tool_count=len(current_tool_calls),
                        iteration=iteration,
                    )

                    # 执行工具
                    tool_results = await self._execute_tool_calls(
                        current_tool_calls, user_id, session_id, personality_id, request_id
                    )

                    # 回填消息
                    messages.append(
                        ChatMessage(
                            role="assistant",
                            content=current_response or "",
                            tool_calls=current_tool_calls,
                        )
                    )

                    for tool_result in tool_results:
                        messages.append(
                            ChatMessage(
                                role="tool",
                                content=tool_result["content"],
                                tool_call_id=tool_result["tool_call_id"],
                            )
                        )

                    # Yield工具执行进度
                    yield {
                        "id": f"chatcmpl-{request_id}",
                        "object": "chat.completion.chunk",
                        "created": int(datetime.now().timestamp()),
                        "model": ai_config.model,
                        "choices": [
                            {
                                "index": 0,
                                "delta": {"role": "tool", "content": f"[Tools executed: {len(tool_results)}]"},
                                "finish_reason": None,
                            }
                        ],
                    }

                    continue

                # 无工具调用，保存响应并退出循环
                full_response = current_response
                break

            # 工具迭代限制警告
            if iteration >= self.max_tool_iterations:
                logger.warning(
                    "Tool iteration limit reached in stream",
                    request_id=request_id,
                    max_iterations=self.max_tool_iterations,
                )

            # 8. 流式完成后持久化助手消息
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
        normalized_user_id = self._normalize_uuid(user_id, uuid.NAMESPACE_DNS)
        normalized_session_id = self._normalize_uuid(session_id, uuid.NAMESPACE_URL)

        session_obj = await self._get_or_create_session(
            session=session,
            session_id=normalized_session_id,
            user_id=normalized_user_id,
            personality_id=personality_id,
            external_session_id=session_id,
        )

        message = Message(
            session_id=session_obj.id,
            user_id=normalized_user_id,
            role=role,
            content=content,
            message_metadata={"request_id": request_id},
        )
        session.add(message)

        session_obj.message_count += 1
        session_obj.last_message_at = datetime.utcnow()

        logger.debug(
            "Message persisted",
            user_id=str(normalized_user_id),
            session_id=str(session_obj.id),
            role=role,
            request_id=request_id,
        )
        return {"id": str(message.id), "role": role}

    @staticmethod
    def _normalize_uuid(value: str, namespace: uuid.UUID) -> uuid.UUID:
        try:
            return uuid.UUID(value)
        except ValueError:
            return uuid.uuid5(namespace, value)

    async def _get_or_create_session(
        self,
        session: AsyncSession,
        session_id: uuid.UUID,
        user_id: uuid.UUID,
        personality_id: str,
        external_session_id: str,
    ) -> Session:
        result = await session.execute(select(Session).where(Session.id == session_id))
        session_obj = result.scalar_one_or_none()
        if session_obj:
            return session_obj

        session_obj = Session(
            id=session_id,
            user_id=user_id,
            personality_id=personality_id,
            message_count=0,
            session_metadata={"external_session_id": external_session_id},
        )
        session.add(session_obj)
        return session_obj

    def _get_api_key(self, engine_type: str) -> str:
        """获取引擎 API 密钥"""
        import os

        if engine_type == "openai":
            return os.getenv("OPENAI_API_KEY", "")
        raise ValueError(f"Unknown engine type: {engine_type}")

    def _get_base_url(self, engine_type: str) -> str:
        """获取引擎 Base URL"""
        import os

        if engine_type == "openai":
            # 如果未设置环境变量，使用默认 OpenAI URL
            return os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
        raise ValueError(f"Unknown engine type: {engine_type}")

    def _get_allowed_tools(self, personality, requested_tools: list[dict] | None) -> list[str]:
        """获取允许的工具列表"""
        # 1. 从人格配置获取允许的工具
        personality_tools = []
        if hasattr(personality, "tools") and personality.tools:
            # Handle both dict (legacy) and PersonalityTools dataclass
            if hasattr(personality.tools, "allowed_tools"):
                personality_tools = personality.tools.allowed_tools
            elif isinstance(personality.tools, dict):
                personality_tools = personality.tools.get("allowed_tools", [])

        # 2. 如果请求中指定了工具，取交集
        if requested_tools:
            requested_tool_names = [t.get("function", {}).get("name") for t in requested_tools if "function" in t]
            if personality_tools:
                return list(set(personality_tools) & set(requested_tool_names))
            return requested_tool_names

        return personality_tools

    async def _execute_tool_calls(
        self,
        tool_calls: list[dict],
        user_id: str,
        session_id: str,
        personality_id: str,
        request_id: str,
    ) -> list[dict]:
        """执行工具调用并记录审计"""
        results = []

        for tool_call in tool_calls:
            tool_call_id = tool_call.get("id")
            function = tool_call.get("function", {})
            tool_name = function.get("name")
            arguments_str = function.get("arguments", "{}")

            try:
                # 解析参数
                arguments = json.loads(arguments_str) if isinstance(arguments_str, str) else arguments_str

                logger.info(
                    "Executing tool",
                    request_id=request_id,
                    tool_name=tool_name,
                    tool_call_id=tool_call_id,
                )

                # 执行工具
                if not self.tools_engine:
                    raise RuntimeError("Tools engine not initialized")

                result = await self.tools_engine.invoke(
                    name=tool_name,
                    arguments=arguments,
                    context={
                        "user_id": user_id,
                        "session_id": session_id,
                        "personality_id": personality_id,
                    },
                )

                # 记录审计日志
                await AuditService.log_tool_invocation(
                    user_id=user_id,
                    session_id=session_id,
                    tool_name=tool_name,
                    arguments=arguments,
                    result={"result": result.result} if result.success else {"error": result.error},
                    success=result.success,
                    execution_time=result.execution_time,
                    request_id=request_id,
                    personality_id=personality_id,
                )

                # 构造工具结果消息
                if result.success:
                    content = json.dumps(result.result) if isinstance(result.result, dict) else str(result.result)
                else:
                    content = json.dumps({"error": result.error, "tool_name": tool_name})

                results.append({
                    "tool_call_id": tool_call_id,
                    "content": content,
                })

            except Exception as e:
                logger.error(
                    "Tool execution failed",
                    request_id=request_id,
                    tool_name=tool_name,
                    error=str(e),
                    exc_info=True,
                )

                # 工具失败仍然返回结果（让模型处理）
                results.append({
                    "tool_call_id": tool_call_id,
                    "content": json.dumps({
                        "error": str(e),
                        "tool_name": tool_name,
                    }),
                })

        return results


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
        context_service=ContextService(engine_registry),
    )
    
    # 初始化工具引擎
    await _orchestrator.initialize_tools_engine()
    
    logger.info("ChatOrchestrator initialized with tools engine")
    return _orchestrator
