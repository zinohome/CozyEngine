"""测试中间件"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.exceptions import ValidationError
from app.middleware import (
    ErrorHandlerMiddleware,
    RateLimitMiddleware,
    RequestContextMiddleware,
)
from app.observability import configure_logging

# Configure logging for tests
configure_logging(log_level="DEBUG")


@pytest.fixture
def app():
    """创建测试应用"""
    app = FastAPI()

    # Add middleware
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(ErrorHandlerMiddleware)

    # Test routes
    @app.get("/test")
    async def test_route():
        return {"message": "ok"}

    @app.get("/error")
    async def error_route():
        raise ValidationError("Test validation error")

    @app.get("/unhandled")
    async def unhandled_route():
        raise ValueError("Unhandled error")

    return app


def test_request_context_middleware(app):
    """测试请求上下文中间件"""
    client = TestClient(app)
    response = client.get("/test")

    assert response.status_code == 200
    assert "X-Request-ID" in response.headers
    assert len(response.headers["X-Request-ID"]) == 36  # UUID length


def test_error_handler_middleware_business_error(app):
    """测试业务错误处理"""
    client = TestClient(app)
    response = client.get("/error")

    assert response.status_code == 422
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "VALIDATION_ERROR"
    assert data["error"]["message"] == "Test validation error"
    assert "request_id" in data["error"]


def test_error_handler_middleware_unhandled_error(app):
    """测试未处理的异常"""
    client = TestClient(app)
    response = client.get("/unhandled")

    assert response.status_code == 500
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "INTERNAL_ERROR"
    assert "request_id" in data["error"]


def test_rate_limit_middleware():
    """测试限流中间件"""
    app = FastAPI()

    # 中间件顺序（FastAPI 是反向执行）: 先 RateLimit -> ErrorHandler -> RequestContext -> app
    # 所以要反向添加：先添加 RateLimit，最后添加 RequestContext
    app.add_middleware(RateLimitMiddleware, requests_per_minute=5)
    app.add_middleware(ErrorHandlerMiddleware)
    app.add_middleware(RequestContextMiddleware)

    @app.get("/test")
    async def test_route():
        return {"message": "ok"}

    client = TestClient(app)

    # 前 5 个请求应该成功
    for _ in range(5):
        response = client.get("/test")
        assert response.status_code == 200

    # 第 6 个请求应该被限流
    response = client.get("/test")
    assert response.status_code == 429
    data = response.json()
    assert data["error"]["code"] == "RATE_LIMIT_EXCEEDED"
