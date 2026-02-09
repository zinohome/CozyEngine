"""Health Check API"""

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import text

from app.storage.database import db_manager

router = APIRouter(tags=["Health"])


class ServiceStatus(BaseModel):
    """单个服务状态"""

    name: str
    status: str  # healthy | degraded | unhealthy
    message: str | None = None


class HealthCheckResponse(BaseModel):
    """健康检查响应"""

    status: str  # healthy | degraded | unhealthy
    services: list[ServiceStatus]


@router.get("/health", response_model=HealthCheckResponse)
async def health_check():
    """
    健康检查端点

    检查各个服务的健康状态：
    - database: PostgreSQL 数据库连接
    - (未来) redis: Redis 缓存连接
    - (未来) external_engines: 外部引擎状态

    返回：
    - healthy: 所有服务正常
    - degraded: 部分服务异常但核心功能可用
    - unhealthy: 核心服务不可用
    """
    services = []
    overall_status = "healthy"

    # Check Database
    try:
        async with db_manager.session() as session:
            await session.execute(text("SELECT 1"))
        services.append(
            ServiceStatus(
                name="database", status="healthy", message="PostgreSQL connection OK"
            )
        )
    except Exception as e:
        services.append(
            ServiceStatus(
                name="database", status="unhealthy", message=f"Database error: {e!s}"
            )
        )
        overall_status = "unhealthy"  # 数据库是核心服务

    # TODO: Add Redis health check
    # TODO: Add external engines health check

    return HealthCheckResponse(status=overall_status, services=services)


@router.get("/health/ready")
async def readiness_check():
    """
    就绪检查（Kubernetes readiness probe）

    返回：
    - 200: 服务已就绪
    - 503: 服务未就绪
    """
    try:
        async with db_manager.session() as session:
            await session.execute(text("SELECT 1"))
        return {"status": "ready"}
    except Exception as e:
        from fastapi import HTTPException

        raise HTTPException(status_code=503, detail=f"Service not ready: {e!s}") from e


@router.get("/health/live")
async def liveness_check():
    """
    存活检查（Kubernetes liveness probe）

    返回：
    - 200: 服务存活
    """
    return {"status": "alive"}
