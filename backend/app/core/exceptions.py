"""统一异常定义与错误模型"""

from typing import Any

from pydantic import BaseModel


class ErrorResponse(BaseModel):
    """统一错误响应模型"""

    error: "ErrorDetail"


class ErrorDetail(BaseModel):
    """错误详情"""

    code: str
    message: str
    request_id: str | None = None
    details: dict[str, Any] | None = None


class CozyEngineError(Exception):
    """CozyEngine 基础异常"""

    def __init__(
        self,
        message: str,
        code: str = "INTERNAL_ERROR",
        status_code: int = 500,
        details: dict[str, Any] | None = None,
    ):
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)


class ValidationError(CozyEngineError):
    """参数验证错误"""

    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(
            message=message, code="VALIDATION_ERROR", status_code=422, details=details
        )


class AuthenticationError(CozyEngineError):
    """认证错误"""

    def __init__(self, message: str = "Authentication failed"):
        super().__init__(message=message, code="AUTHENTICATION_ERROR", status_code=401)


class AuthorizationError(CozyEngineError):
    """授权错误"""

    def __init__(self, message: str = "Permission denied"):
        super().__init__(message=message, code="AUTHORIZATION_ERROR", status_code=403)


class NotFoundError(CozyEngineError):
    """资源未找到"""

    def __init__(self, resource: str, identifier: str):
        message = f"{resource} not found: {identifier}"
        super().__init__(message=message, code="NOT_FOUND", status_code=404)


class RateLimitError(CozyEngineError):
    """速率限制错误"""

    def __init__(self, message: str = "Rate limit exceeded"):
        super().__init__(message=message, code="RATE_LIMIT_EXCEEDED", status_code=429)


class ExternalServiceError(CozyEngineError):
    """外部服务错误"""

    def __init__(self, service: str, message: str):
        super().__init__(
            message=f"{service}: {message}",
            code="EXTERNAL_SERVICE_ERROR",
            status_code=502,
        )


class ConfigurationError(CozyEngineError):
    """配置错误"""

    def __init__(self, message: str):
        super().__init__(
            message=message, code="CONFIGURATION_ERROR", status_code=500
        )
