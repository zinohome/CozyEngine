"""聊天完成端点 - OpenAI 兼容"""

import json
from collections.abc import AsyncGenerator
from typing import Union

from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import StreamingResponse

from app.observability.logging import get_logger
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
    user_id: str = Header(None),
    session_id: str = Header(None),
) -> Union[dict, StreamingResponse]:
    """
    聊天完成端点 (OpenAI 兼容)

    请求头:
    - user_id: 用户 ID
    - session_id: 会话 ID

    请求体:
    {
        "model": "default",
        "messages": [{"role": "user", "content": "你好"}],
        "temperature": 0.7,
        "max_tokens": 2000,
        "stream": false
    }
    """
    try:
        # 验证必需字段
        if not body.get("messages"):
            raise HTTPException(status_code=400, detail="messages is required")

        if not user_id:
            raise HTTPException(status_code=400, detail="user_id header is required")

        if not session_id:
            raise HTTPException(status_code=400, detail="session_id header is required")

        # 解析请求
        req = parse_request_body(body)

        # 获取最后一条消息内容
        if not req.messages:
            raise HTTPException(status_code=400, detail="messages cannot be empty")

        last_message = req.messages[-1]
        if last_message.get("role") != "user":
            raise HTTPException(status_code=400, detail="last message must be from user")

        user_message = last_message.get("content", "")

        # 获取编排器
        orchestrator = get_orchestrator()

        # 确定使用的人格 ID (从 model 参数)
        personality_id = req.model if req.model != "default" else "default"

        # 流式响应
        if req.stream:
            return StreamingResponse(
                _stream_response(
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

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Chat request failed", error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e


async def _stream_response(
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
    try:
        async for chunk in orchestrator.chat_stream(
            user_id=user_id,
            session_id=session_id,
            personality_id=personality_id,
            message=message,
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=top_p,
            tools=tools,
        ):
            if chunk.get("data") == "[DONE]":
                yield "data: [DONE]\n\n"
            else:
                yield f"data: {json.dumps(chunk)}\n\n"
    except Exception as e:
        logger.error("Stream failed", error=str(e), exc_info=True)
        yield f"data: {json.dumps({'error': str(e)})}\n\n"
