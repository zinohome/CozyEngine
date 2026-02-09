"""测试异常处理"""

from app.core.exceptions import (
    AuthenticationError,
    AuthorizationError,
    ExternalServiceError,
    NotFoundError,
    RateLimitError,
    ValidationError,
)


def test_validation_error():
    """测试参数验证错误"""
    error = ValidationError("Invalid input", details={"field": "email"})
    assert error.code == "VALIDATION_ERROR"
    assert error.status_code == 422
    assert error.message == "Invalid input"
    assert error.details == {"field": "email"}


def test_authentication_error():
    """测试认证错误"""
    error = AuthenticationError()
    assert error.code == "AUTHENTICATION_ERROR"
    assert error.status_code == 401
    assert "Authentication failed" in error.message


def test_authorization_error():
    """测试授权错误"""
    error = AuthorizationError()
    assert error.code == "AUTHORIZATION_ERROR"
    assert error.status_code == 403
    assert "Permission denied" in error.message


def test_not_found_error():
    """测试资源未找到错误"""
    error = NotFoundError("User", "123")
    assert error.code == "NOT_FOUND"
    assert error.status_code == 404
    assert "User" in error.message
    assert "123" in error.message


def test_rate_limit_error():
    """测试速率限制错误"""
    error = RateLimitError()
    assert error.code == "RATE_LIMIT_EXCEEDED"
    assert error.status_code == 429


def test_external_service_error():
    """测试外部服务错误"""
    error = ExternalServiceError("OpenAI", "Connection timeout")
    assert error.code == "EXTERNAL_SERVICE_ERROR"
    assert error.status_code == 502
    assert "OpenAI" in error.message
    assert "Connection timeout" in error.message
