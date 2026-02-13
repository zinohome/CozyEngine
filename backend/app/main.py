"""FastAPI application entry point."""

import json
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.health import router as health_router
from app.api.v1.chat import router as chat_router
from app.api.v1.personalities import router as personalities_router
from app.api.v1.voice import router as voice_router
from app.core.config import Config, ConfigurationError, get_config
from app.core.exceptions import ErrorDetail, ErrorResponse
from app.core.personalities import PersonalityLoader, PersonalityRegistry, initialize_personality_registry
from app.engines.registry import engine_registry
from app.middleware import (
    ErrorHandlerMiddleware,
    RateLimitMiddleware,
    RequestContextMiddleware,
)
from app.observability import configure_logging, get_logger
from app.orchestration import initialize_orchestrator
from app.storage.database import db_manager
from app.storage.redis import redis_manager
from app.services.worker import async_worker

# Initialize configuration
try:
    config = get_config()
    print("\n" + "=" * 80)
    print("CozyEngine Configuration Loaded Successfully")
    print("=" * 80)
    config_summary = config.get_sanitized_config_summary()
    print(json.dumps(config_summary, indent=2))
    print("=" * 80 + "\n")
except ConfigurationError as e:
    print(f"\n❌ Configuration Error: {e}\n")
    raise

# Configure logging
configure_logging(log_level=config.app.log_level if hasattr(config.app, "log_level") else "INFO")
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    # Startup
    logger.info("Starting CozyEngine...")
    
    # Initialize database
    db_manager.initialize()
    logger.info("Database connection pool initialized")

    # Initialize Redis
    await redis_manager.initialize()
    if redis_manager.client:
        logger.info("Redis connection initialized")
    else:
        logger.warning("Redis connection failed or disabled")
    
    # Initialize personality registry
    personality_registry = initialize_personality_registry()
    logger.info("Personality registry initialized")
    
    # Initialize orchestrator
    orchestrator = await initialize_orchestrator(personality_registry, engine_registry)
    logger.info("ChatOrchestrator initialized")

    # Start Background Worker (Async Write-back)
    await async_worker.start()
    
    yield
    
    # Shutdown
    logger.info("Shutting down CozyEngine...")
    
    # Stop Background Worker
    await async_worker.stop()
    
    # Close all engines
    await engine_registry.close_all()
    logger.info("All engines closed")
    
    # Close Redis
    await redis_manager.close()
    logger.info("Redis connection closed")

    # Close database
    await db_manager.close()
    logger.info("Database connection pool closed")


app = FastAPI(
    title=config.app.name,
    description=config.app.description,
    version=config.app.version,
    debug=config.app.debug,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """统一 HTTP 异常响应格式"""
    request_id = getattr(request.state, "request_id", None)
    error_response = ErrorResponse(
        error=ErrorDetail(
            code="HTTP_ERROR",
            message=str(exc.detail),
            request_id=request_id,
        )
    )
    return JSONResponse(status_code=exc.status_code, content=error_response.model_dump())


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """统一请求校验错误响应格式"""
    request_id = getattr(request.state, "request_id", None)
    error_response = ErrorResponse(
        error=ErrorDetail(
            code="VALIDATION_ERROR",
            message="Validation failed",
            request_id=request_id,
            details={"errors": exc.errors()},
        )
    )
    return JSONResponse(status_code=422, content=error_response.model_dump())

# Add middleware stack (order matters - first added = outermost)
# 1. Request context (outermost - sets request_id)
app.add_middleware(RequestContextMiddleware)

# 2. Error handler (catches all exceptions)
app.add_middleware(ErrorHandlerMiddleware)

# 3. Rate limiting
app.add_middleware(RateLimitMiddleware, requests_per_minute=60)

# 4. CORS middleware (innermost - closest to routes)
if config.app.cors.enabled:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.app.cors.allow_origins or ["*"],
        allow_credentials=config.app.cors.allow_credentials,
        allow_methods=config.app.cors.allow_methods,
        allow_headers=config.app.cors.allow_headers,
    )

# Register routers
app.include_router(health_router, prefix="/api/v1")
app.include_router(chat_router, prefix="/api")
app.include_router(personalities_router, prefix="/api")
app.include_router(voice_router, prefix="/api/v1") # Mounts at /api/v1/audio/...


@app.get("/")
async def root():
    """Root endpoint."""
    logger.info("Root endpoint accessed")
    return {
        "name": config.app.name,
        "version": config.app.version,
        "config_version": config.config_version,
        "environment": config.environment,
        "status": "operational",
    }


@app.get("/config")
async def config_info():
    """Configuration information endpoint (sanitized)."""
    return config.get_sanitized_config_summary()
