"""限流中间件"""

import time
from collections import defaultdict
from collections.abc import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.exceptions import RateLimitError
from app.observability.logging import get_logger

logger = get_logger(__name__)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    简单的内存限流中间件

    生产环境应使用 Redis 实现分布式限流
    """

    def __init__(self, app, requests_per_minute: int = 60):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.window_size = 60  # 秒
        self.requests: dict[str, list[float]] = defaultdict(list)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # 获取客户端标识（IP 或 用户 ID）
        client_id = self._get_client_id(request)
        current_time = time.time()

        # 清理过期记录
        self.requests[client_id] = [
            req_time
            for req_time in self.requests[client_id]
            if current_time - req_time < self.window_size
        ]

        # 检查限流
        if len(self.requests[client_id]) >= self.requests_per_minute:
            logger.warning(
                "Rate limit exceeded",
                client_id=client_id,
                requests_count=len(self.requests[client_id]),
                limit=self.requests_per_minute,
            )
            raise RateLimitError()

        # 记录本次请求
        self.requests[client_id].append(current_time)

        return await call_next(request)

    def _get_client_id(self, request: Request) -> str:
        """获取客户端唯一标识"""
        # 优先使用用户 ID（如果已认证）
        if hasattr(request.state, "user_id") and request.state.user_id:
            return f"user:{request.state.user_id}"

        # 否则使用 IP
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return f"ip:{forwarded.split(',')[0].strip()}"

        client_host = request.client.host if request.client else "unknown"
        return f"ip:{client_host}"
