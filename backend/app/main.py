"""FastAPI application entry point."""

import json

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import Config, ConfigurationError, get_config

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

app = FastAPI(
    title=config.app.name,
    description=config.app.description,
    version=config.app.version,
    debug=config.app.debug,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS middleware
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
    return {"status": "healthy"}


@app.get("/config")
async def config_info():
    """Configuration information endpoint (sanitized)."""
    return config.get_sanitized_config_summary()
