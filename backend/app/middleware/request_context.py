"""请求上下文中间件"""

import uuid
from collections.abc import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.observability.logging import bind_request_context, unbind_request_context


class RequestContextMiddleware(BaseHTTPMiddleware):
    """请求上下文中间件 - 为每个请求生成 request_id 并绑定到日志上下文"""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # 生成或获取 request_id
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id

        # 绑定可用的请求标识（来自 headers）
        user_id = request.headers.get("user_id")
        session_id = request.headers.get("session_id")
        request.state.user_id = user_id
        request.state.session_id = session_id

        # 绑定到日志上下文
        bind_request_context(request_id=request_id, user_id=user_id, session_id=session_id)

        try:
            response = await call_next(request)
            # 在响应头中返回 request_id
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            # 清理上下文
            unbind_request_context()
