"""错误处理中间件"""

import traceback
from collections.abc import Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.exceptions import CozyEngineError, ErrorDetail, ErrorResponse
from app.observability.logging import get_logger

logger = get_logger(__name__)


class ErrorHandlerMiddleware(BaseHTTPMiddleware):
    """统一错误处理中间件"""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        try:
            response = await call_next(request)
            return response
        except CozyEngineError as exc:
            # 业务异常（可控）
            request_id = request.state.request_id if hasattr(request.state, "request_id") else None

            logger.warning(
                "Business error occurred",
                error_code=exc.code,
                error_message=exc.message,
                status_code=exc.status_code,
                request_id=request_id,
                path=request.url.path,
            )

            error_response = ErrorResponse(
                error=ErrorDetail(
                    code=exc.code,
                    message=exc.message,
                    request_id=request_id,
                    details=exc.details,
                )
            )

            return JSONResponse(
                status_code=exc.status_code,
                content=error_response.model_dump(),
            )

        except Exception as exc:
            # 未预期的系统异常
            request_id = request.state.request_id if hasattr(request.state, "request_id") else None

            logger.error(
                "Unhandled exception",
                error=str(exc),
                traceback=traceback.format_exc(),
                request_id=request_id,
                path=request.url.path,
            )

            error_response = ErrorResponse(
                error=ErrorDetail(
                    code="INTERNAL_ERROR",
                    message="An internal error occurred",
                    request_id=request_id,
                )
            )

            return JSONResponse(
                status_code=500,
                content=error_response.model_dump(),
            )
