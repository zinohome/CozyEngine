"""AI 引擎 - 接口定义"""

from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator
from dataclasses import dataclass

import httpx


@dataclass
class ChatMessage:
    """聊天消息"""

    role: str  # user, assistant, system, tool
    content: str
    tool_calls: dict | list[dict] | None = None  # For assistant role with tool calls
    tool_call_id: str | None = None  # For tool role responses


@dataclass
class ChatResponse:
    """聊天响应"""

    content: str
    finish_reason: str  # stop, length, end_turn, tool_calls
    usage: dict | None = None
    tool_calls: list[dict] | None = None


class AIEngine(ABC):
    """AI 引擎基类"""

    @abstractmethod
    async def initialize(self) -> None:
        """初始化引擎"""
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """健康检查"""
        pass

    @abstractmethod
    async def close(self) -> None:
        """关闭引擎"""
        pass

    @abstractmethod
    async def chat(
        self,
        messages: list[ChatMessage],
        temperature: float = 0.7,
        max_tokens: int = 2000,
        top_p: float = 1.0,
        tools: list[dict] | None = None,
    ) -> ChatResponse:
        """非流式聊天"""
        pass

    @abstractmethod
    def chat_stream(
        self,
        messages: list[ChatMessage],
        temperature: float = 0.7,
        max_tokens: int = 2000,
        top_p: float = 1.0,
        tools: list[dict] | None = None,
    ) -> AsyncGenerator[dict, None]:
        """流式聊天 - 返回异步迭代器"""
        ...

    @property
    def supports_tools(self) -> bool:
        """是否支持工具调用"""
        return False

    @property
    def supports_vision(self) -> bool:
        """是否支持视觉"""
        return False


class OpenAIProvider(AIEngine):
    """OpenAI 提供商"""

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.openai.com/v1",
        model: str = "gpt-4",
    ):
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.client = None
        self._initialized = False

    async def initialize(self) -> None:
        """初始化 OpenAI 客户端"""
        if self._initialized:
            return

        from app.observability.logging import get_logger

        logger = get_logger(__name__)
        logger.info("Initializing OpenAI provider", base_url=self.base_url)
        self._initialized = True

    async def health_check(self) -> bool:
        """健康检查 - 检查 API 连接"""
        try:
            async with httpx.AsyncClient(
                base_url=self.base_url, headers={"Authorization": f"Bearer {self.api_key}"}
            ) as client:
                response = await client.get("/models", timeout=5.0)
                return response.status_code == 200
        except Exception:
            return False

    async def close(self) -> None:
        """关闭连接"""
        pass

    async def chat(
        self,
        messages: list[ChatMessage],
        temperature: float = 0.7,
        max_tokens: int = 2000,
        top_p: float = 1.0,
        tools: list[dict] | None = None,
    ) -> ChatResponse:
        """非流式聊天"""
        try:
            import openai

            client = openai.AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)

            # 转换消息格式
            openai_messages = [
                {"role": msg.role, "content": msg.content} for msg in messages
            ]

            kwargs = {
                "model": self.model,
                "messages": openai_messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "top_p": top_p,
            }

            if tools:
                kwargs["tools"] = [{"type": "function", "function": t} for t in tools]

            response = await client.chat.completions.create(**kwargs)

            # 提取响应
            choice = response.choices[0]
            tool_calls = None
            if choice.message.tool_calls:
                tool_calls = [
                    {
                        "id": tc.id,
                        "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                    }
                    for tc in choice.message.tool_calls
                ]

            return ChatResponse(
                content=choice.message.content or "",
                finish_reason=choice.finish_reason,
                usage={
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens,
                } if response.usage else None,
                tool_calls=tool_calls,
            )
        except Exception as e:
            from app.core.exceptions import ExternalServiceError

            raise ExternalServiceError(service="OpenAI", message=str(e)) from e

    async def chat_stream(
        self,
        messages: list[ChatMessage],
        temperature: float = 0.7,
        max_tokens: int = 2000,
        top_p: float = 1.0,
        tools: list[dict] | None = None,
    ):
        """流式聊天"""
        try:
            import openai

            client = openai.AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)

            # 转换消息格式
            openai_messages = [
                {"role": msg.role, "content": msg.content} for msg in messages
            ]

            kwargs = {
                "model": self.model,
                "messages": openai_messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "top_p": top_p,
                "stream": True,
            }

            if tools:
                kwargs["tools"] = [{"type": "function", "function": t} for t in tools]

            stream = await client.chat.completions.create(**kwargs)

            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta:
                    delta = chunk.choices[0].delta
                    yield {
                        "content": delta.content or "",
                        "finish_reason": chunk.choices[0].finish_reason,
                    }
        except Exception as e:
            from app.core.exceptions import ExternalServiceError

            raise ExternalServiceError(service="OpenAI", message=str(e)) from e

    @property
    def supports_tools(self) -> bool:
        """OpenAI 支持工具调用"""
        return True

    @property
    def supports_vision(self) -> bool:
        """OpenAI 支持视觉"""
        return True
