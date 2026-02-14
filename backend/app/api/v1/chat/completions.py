"""聊天完成端点 - OpenAI 兼容"""

import json
import time
from collections.abc import AsyncGenerator
from typing import Union

from fastapi import APIRouter, Header, Request
from fastapi.responses import StreamingResponse

from app.core.exceptions import ValidationError
from app.observability.logging import get_logger
from app.observability.logging import bind_request_context
from app.orchestration.chat import get_orchestrator

logger = get_logger(__name__)

router = APIRouter(prefix="/v1/chat", tags=["chat"])


class ChatCompletionRequest:
    """聊天完成请求"""

    def __init__(
        self,
        model: str,
        messages: list[dict],
        temperature: float | None = None,
        max_tokens: int | None = None,
        top_p: float | None = None,
        stream: bool = False,
        tools: list[dict] | None = None,
    ):
        self.model = model
        self.messages = messages
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.top_p = top_p
        self.stream = stream
        self.tools = tools


def parse_request_body(body: dict) -> ChatCompletionRequest:
    """解析请求体"""
    return ChatCompletionRequest(
        model=body.get("model", "default"),
        messages=body.get("messages", []),
        temperature=body.get("temperature"),
        max_tokens=body.get("max_tokens"),
        top_p=body.get("top_p"),
        stream=body.get("stream", False),
        tools=body.get("tools"),
    )


@router.post("/completions", response_model=None)
async def chat_completions(
    body: dict,
    request: Request,
    user_id: str = Header(None, alias="X-User-Id"),
    session_id: str = Header(None, alias="X-Session-Id"),
) -> Union[dict, StreamingResponse]:
    """
    聊天完成端点 (OpenAI 兼容)

    请求头:
    - X-User-Id: 用户 ID
    - X-Session-Id: 会话 ID

    请求体:
    {
        "model": "default",
        "messages": [{"role": "user", "content": "你好"}],
        "temperature": 0.7,
        "max_tokens": 2000,
        "stream": false
    }
    """
    # 验证必需字段
    if not body.get("messages"):
        raise ValidationError("messages is required", details={"field": "messages"})

    if not user_id:
        raise ValidationError("user_id header is required", details={"field": "user_id"})

    if not session_id:
        raise ValidationError(
            "session_id header is required", details={"field": "session_id"}
        )

    # 解析请求
    req = parse_request_body(body)

    # 获取最后一条消息内容
    if not req.messages:
        raise ValidationError("messages cannot be empty", details={"field": "messages"})

    last_message = req.messages[-1]
    if last_message.get("role") != "user":
        raise ValidationError(
            "last message must be from user", details={"field": "messages[-1].role"}
        )

    user_message = last_message.get("content", "")

    # 获取编排器
    orchestrator = get_orchestrator()

    # 确定使用的人格 ID (从 model 参数)
    personality_id = req.model if req.model != "default" else "default"

    # 绑定完整上下文到日志
    request_id = getattr(request.state, "request_id", "unknown")
    bind_request_context(
        request_id=request_id,
        user_id=user_id,
        session_id=session_id,
        personality_id=personality_id,
    )

    # 流式响应
    if req.stream:
        return StreamingResponse(
            _stream_response(
                request=request,
                orchestrator=orchestrator,
                user_id=user_id,
                session_id=session_id,
                personality_id=personality_id,
                message=user_message,
                temperature=req.temperature,
                max_tokens=req.max_tokens,
                top_p=req.top_p,
                tools=req.tools,
            ),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
                "X-Request-ID": request_id,
            },
        )

    # 非流式响应
    response = await orchestrator.chat(
        user_id=user_id,
        session_id=session_id,
        personality_id=personality_id,
        message=user_message,
        temperature=req.temperature,
        max_tokens=req.max_tokens,
        top_p=req.top_p,
        tools=req.tools,
    )

    return response


async def _stream_response(
    request: Request,
    orchestrator,
    user_id: str,
    session_id: str,
    personality_id: str,
    message: str,
    temperature: float | None = None,
    max_tokens: int | None = None,
    top_p: float | None = None,
    tools: list[dict] | None = None,
) -> AsyncGenerator[str, None]:
    """流式响应生成器"""
    # 获取 request_id（从中间件设置）
    request_id = getattr(request.state, 'request_id', 'unknown')
    start_time = time.time()
    
    logger.info(
        "Stream chat started",
        request_id=request_id,
        user_id=user_id,
        session_id=session_id,
        personality_id=personality_id,
    )
    
    stream = orchestrator.chat_stream(
        user_id=user_id,
        session_id=session_id,
        personality_id=personality_id,
        message=message,
        temperature=temperature,
        max_tokens=max_tokens,
        top_p=top_p,
        tools=tools,
    )
    try:
        async for chunk in stream:
            if await request.is_disconnected():
                logger.info(
                    "Client disconnected from stream",
                    request_id=request_id,
                    user_id=user_id,
                    session_id=session_id,
                    personality_id=personality_id,
                )
                break
            if chunk.get("data") == "[DONE]":
                elapsed_time = time.time() - start_time
                logger.info(
                    "Stream chat completed",
                    request_id=request_id,
                    user_id=user_id,
                    session_id=session_id,
                    elapsed_time=elapsed_time,
                )
                yield "data: [DONE]\n\n"
            else:
                # 添加 request_id 到响应中
                chunk_with_id = {**chunk, "request_id": request_id}
                yield f"data: {json.dumps(chunk_with_id)}\n\n"
    except Exception as e:
        logger.error(
            "Stream failed",
            request_id=request_id,
            user_id=user_id,
            session_id=session_id,
            error=str(e),
            exc_info=True,
        )
        # 统一错误响应格式
        error_response = {
            "error": {
                "code": "STREAM_ERROR",
                "message": str(e),
                "request_id": request_id,
            }
        }
        yield f"data: {json.dumps(error_response)}\n\n"
    finally:
        # 安全地关闭 stream
        if hasattr(stream, 'aclose'):
            await stream.aclose()
