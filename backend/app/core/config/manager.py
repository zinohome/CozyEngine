"""Configuration manager with YAML and environment variable merging."""

from pathlib import Path
from typing import Any

from pydantic import ValidationError

from .exceptions import InvalidConfigurationError, MissingRequiredSecretError
from .loader import YAMLConfigLoader
from .schemas import (
    APIConfig,
    AppConfig,
    ContextConfig,
    EnginesConfig,
    ObservabilityConfig,
    SecurityConfig,
    StorageConfig,
    ToolsConfig,
    GreyscaleConfig,
)
from .settings import Settings


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Deep merge two dictionaries.

    Args:
        base: Base dictionary
        override: Override dictionary (takes precedence)

    Returns:
        Merged dictionary
    """
    result = base.copy()

    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value

    return result


class Config:
    """Unified configuration manager.

    Implements configuration priority: YAML > Environment Variables > Code Defaults

    Usage:
        config = Config()
        print(config.app.name)
        print(config.engines.ai.default_provider)
    """

    def __init__(self, config_dir: Path | None = None, env_file: str | None = None):
        """Initialize configuration.

        Args:
            config_dir: Directory containing YAML configuration files
            env_file: Path to .env file (defaults to .env in current directory)
        """
        # Load environment variables first
        self.settings = Settings(_env_file=env_file) if env_file else Settings()

        # Load YAML configuration
        self.yaml_loader = YAMLConfigLoader(config_dir)
        self.config_version = self.yaml_loader.get_config_version()

        # Get environment from settings
        self.environment = self.settings.app_env

        # Load and merge all configurations
        self._load_configurations()

        # Validate required secrets
        self._validate_required_secrets()

    def _load_configurations(self) -> None:
        """Load and merge all configuration namespaces."""
        # Load base YAML configurations
        yaml_configs = self.yaml_loader.load_all()

        # Load environment-specific overlays
        for namespace in yaml_configs:
            env_overlay = self.yaml_loader.load_environment_specific(namespace, self.environment)
            if env_overlay:
                yaml_configs[namespace] = deep_merge(yaml_configs[namespace], env_overlay)

        # Apply environment variable overrides and validate with Pydantic
        try:
            # App configuration
            app_data = yaml_configs.get("app", {})
            app_data["environment"] = self.settings.app_env
            app_data["debug"] = self.settings.debug
            if app_data.get("server"):
                app_data["server"]["host"] = self.settings.host
                app_data["server"]["port"] = self.settings.port
                app_data["server"]["reload"] = self.settings.reload
            if app_data.get("cors") and self.settings.allowed_origins:
                app_data["cors"]["allow_origins"] = self.settings.get_allowed_origins_list()

            self.app = AppConfig(**app_data)

            # API configuration
            self.api = APIConfig(**yaml_configs.get("api", {}))

            # Engines configuration
            engines_data = yaml_configs.get("engines", {})
            # Apply provider-specific overrides from environment
            # (In a full implementation, you'd add more granular overrides here)
            self.engines = EnginesConfig(**engines_data)

            # Context configuration
            self.context = ContextConfig(**yaml_configs.get("context", {}))

            # Tools configuration
            self.tools = ToolsConfig(**yaml_configs.get("tools", {}))

            # Storage configuration
            storage_data = yaml_configs.get("storage", {})
            if storage_data.get("database"):
                storage_data["database"]["pool_size"] = self.settings.database_pool_size
                storage_data["database"]["max_overflow"] = self.settings.database_max_overflow
            if storage_data.get("redis"):
                storage_data["redis"]["max_connections"] = self.settings.redis_max_connections

            self.storage = StorageConfig(**storage_data)

            # Observability configuration
            obs_data = yaml_configs.get("observability", {})
            if obs_data.get("logging"):
                obs_data["logging"]["level"] = self.settings.log_level
            if obs_data.get("tracing"):
                obs_data["tracing"]["enabled"] = self.settings.otel_enabled
            if obs_data.get("sentry"):
                obs_data["sentry"]["enabled"] = self.settings.sentry_enabled
                if self.settings.sentry_environment:
                    obs_data["sentry"]["environment"] = self.settings.sentry_environment

            self.observability = ObservabilityConfig(**obs_data)

            # Security configuration
            self.security = SecurityConfig(**yaml_configs.get("security", {}))

            # Greyscale configuration
            self.greyscale = GreyscaleConfig(**yaml_configs.get("greyscale", {}))

        except ValidationError as e:
            raise InvalidConfigurationError(f"Configuration validation failed: {e}") from e

    def _validate_required_secrets(self) -> None:
        """Validate that all required secrets are present."""
        missing = self.settings.validate_required_secrets(self.environment)

        if missing:
            error_msg = "Missing required secrets:\n"
            for secret in missing:
                error_msg += f"  - {secret}\n"
            error_msg += (
                f"\nPlease set the required environment variables for "
                f"environment: {self.environment}"
            )
            raise MissingRequiredSecretError("multiple", error_msg)

    def get_sanitized_config_summary(self) -> dict[str, Any]:
        """Get a sanitized summary of configuration for logging.

        Returns:
            Dictionary with sanitized configuration values (no secrets)
        """
        return {
            "config_version": self.config_version,
            "environment": self.environment,
            "app": {
                "name": self.app.name,
                "version": self.app.version,
                "debug": self.app.debug,
                "server": {
                    "host": self.app.server.host,
                    "port": self.app.server.port,
                    "workers": self.app.server.workers,
                },
                "cors_enabled": self.app.cors.enabled,
            },
            "api": {
                "openai_compatible": self.api.openai_compatible,
                "sse_enabled": self.api.sse.enabled,
            },
            "engines": {
                "ai": {
                    "default_provider": self.engines.ai.default_provider,
                    "enabled_providers": [
                        name
                        for name, cfg in self.engines.ai.providers.items()
                        if cfg.enabled
                    ],
                },
                "knowledge_enabled": self.engines.knowledge.enabled,
                "user_profile_enabled": self.engines.user_profile.enabled,
                "chat_memory_enabled": self.engines.chat_memory.enabled,
                "tools_enabled": self.engines.tools.enabled,
            },
            "context": {
                "parallel_execution_enabled": self.context.parallel_execution.enabled,
                "degradation_enabled": self.context.degradation.enabled,
            },
            "observability": {
                "log_level": self.observability.logging.level,
                "log_format": self.observability.logging.format,
                "metrics_enabled": self.observability.metrics.enabled,
                "tracing_enabled": self.observability.tracing.enabled,
                "sentry_enabled": self.observability.sentry.enabled,
            },
            "security": {
                "authentication_enabled": self.security.authentication.enabled,
                "authorization_enabled": self.security.authorization.enabled,
                "audit_enabled": self.security.audit.enabled,
            },
        }


# Global configuration instance
_config: Config | None = None


def get_config(config_dir: Path | None = None, reload: bool = False) -> Config:
    """Get or create the global configuration instance.

    Args:
        config_dir: Configuration directory (only used on first load)
        reload: Force reload of configuration

    Returns:
        Global Config instance
    """
    global _config

    if _config is None or reload:
        _config = Config(config_dir=config_dir)

    return _config
