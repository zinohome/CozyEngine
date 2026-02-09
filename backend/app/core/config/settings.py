"""Environment variables settings using Pydantic Settings."""

from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment variables settings.

    These settings are loaded from environment variables and override YAML configuration.
    Priority: Environment Variables > YAML > Code Defaults
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ============================================================================
    # Application
    # ============================================================================

    app_name: str = Field(default="CozyEngine", alias="APP_NAME")
    app_env: Literal["development", "staging", "production"] = Field(
        default="development", alias="APP_ENV"
    )
    debug: bool = Field(default=False, alias="DEBUG")
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO", alias="LOG_LEVEL"
    )

    # Server
    host: str = Field(default="0.0.0.0", alias="HOST")
    port: int = Field(default=8000, ge=1, le=65535, alias="PORT")
    reload: bool = Field(default=False, alias="RELOAD")

    # CORS
    allowed_origins: str = Field(default="", alias="ALLOWED_ORIGINS")

    # ============================================================================
    # Security & Secrets (REQUIRED in production)
    # ============================================================================

    secret_key: SecretStr | None = Field(default=None, alias="SECRET_KEY")
    jwt_secret_key: SecretStr | None = Field(default=None, alias="JWT_SECRET_KEY")

    # ============================================================================
    # Database & Storage (REQUIRED)
    # ============================================================================

    database_url: SecretStr | None = Field(default=None, alias="DATABASE_URL")
    database_pool_size: int = Field(default=10, ge=1, le=100, alias="DATABASE_POOL_SIZE")
    database_max_overflow: int = Field(default=20, ge=0, le=100, alias="DATABASE_MAX_OVERFLOW")

    redis_url: str | None = Field(default=None, alias="REDIS_URL")
    redis_max_connections: int = Field(default=50, ge=1, le=1000, alias="REDIS_MAX_CONNECTIONS")

    # ============================================================================
    # AI Providers (At least one REQUIRED)
    # ============================================================================

    # OpenAI
    openai_api_key: SecretStr | None = Field(default=None, alias="OPENAI_API_KEY")
    openai_org_id: str | None = Field(default=None, alias="OPENAI_ORG_ID")
    openai_base_url: str | None = Field(default=None, alias="OPENAI_BASE_URL")

    # Anthropic
    anthropic_api_key: SecretStr | None = Field(default=None, alias="ANTHROPIC_API_KEY")
    anthropic_base_url: str | None = Field(default=None, alias="ANTHROPIC_BASE_URL")

    # Ollama (optional, for local models)
    ollama_base_url: str | None = Field(default=None, alias="OLLAMA_BASE_URL")

    # ============================================================================
    # Personalization Engines (Optional)
    # ============================================================================

    # Cognee
    cognee_api_url: str | None = Field(default=None, alias="COGNEE_API_URL")
    cognee_api_token: SecretStr | None = Field(default=None, alias="COGNEE_API_TOKEN")

    # Memobase
    memobase_project_url: str | None = Field(default=None, alias="MEMOBASE_PROJECT_URL")
    memobase_api_key: SecretStr | None = Field(default=None, alias="MEMOBASE_API_KEY")

    # Mem0
    mem0_api_url: str | None = Field(default=None, alias="MEM0_API_URL")
    mem0_api_key: SecretStr | None = Field(default=None, alias="MEM0_API_KEY")

    # ============================================================================
    # Observability (Optional)
    # ============================================================================

    # OpenTelemetry
    otel_enabled: bool = Field(default=False, alias="OTEL_ENABLED")
    otel_exporter_otlp_endpoint: str | None = Field(
        default=None, alias="OTEL_EXPORTER_OTLP_ENDPOINT"
    )
    otel_service_name: str = Field(default="cozyengine", alias="OTEL_SERVICE_NAME")

    # Sentry
    sentry_dsn: SecretStr | None = Field(default=None, alias="SENTRY_DSN")
    sentry_enabled: bool = Field(default=False, alias="SENTRY_ENABLED")
    sentry_environment: str | None = Field(default=None, alias="SENTRY_ENVIRONMENT")

    # ============================================================================
    # Feature Flags (Optional)
    # ============================================================================

    enable_metrics: bool = Field(default=True, alias="ENABLE_METRICS")
    enable_tracing: bool = Field(default=False, alias="ENABLE_TRACING")

    def get_allowed_origins_list(self) -> list[str]:
        """Parse allowed origins from comma-separated string."""
        if not self.allowed_origins:
            return []
        return [origin.strip() for origin in self.allowed_origins.split(",") if origin.strip()]

    def validate_required_secrets(self, environment: str) -> list[str]:
        """Validate that required secrets are present.

        Args:
            environment: Current environment (development, staging, production)

        Returns:
            List of missing required secrets
        """
        missing = []

        # In production, these are always required
        if environment == "production":
            if not self.secret_key:
                missing.append("SECRET_KEY")
            if not self.database_url:
                missing.append("DATABASE_URL")

        # At least one AI provider must be configured
        if not any(
            [
                self.openai_api_key,
                self.anthropic_api_key,
                self.ollama_base_url,
            ]
        ):
            missing.append(
                "AI_PROVIDER (at least one of: OPENAI_API_KEY, "
                "ANTHROPIC_API_KEY, or OLLAMA_BASE_URL)"
            )

        # Development can run without database for testing
        if environment != "development" and not self.database_url:
            missing.append("DATABASE_URL")

        return missing
