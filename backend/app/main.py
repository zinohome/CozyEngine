"""FastAPI application entry point."""

import json

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import Config, ConfigurationError, get_config
from app.middleware import (
    ErrorHandlerMiddleware,
    RequestContextMiddleware,
    RateLimitMiddleware,
)
from app.observability import configure_logging, get_logger

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

app = FastAPI(
    title=config.app.name,
    description=config.app.description,
    version=config.app.version,
    debug=config.app.debug,
    docs_url="/docs",
    redoc_url="/redoc",
)

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


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    logger.debug("Health check endpoint accessed")
    return {"status": "healthy"}


@app.get("/config")
async def config_info():
    """Configuration information endpoint (sanitized)."""
    return config.get_sanitized_config_summary()
