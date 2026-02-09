"""Configuration module for CozyEngine.

This module implements a hierarchical configuration system with:
- YAML-based structured configuration
- Environment variable overrides
- Multi-environment support (dev/staging/production)
- Schema validation at startup
"""

from .exceptions import (
    ConfigurationError,
    ConfigurationVersionMismatchError,
    InvalidConfigurationError,
    MissingRequiredSecretError,
)
from .manager import Config, get_config
from .schemas import (
    APIConfig,
    AppConfig,
    ContextConfig,
    EnginesConfig,
    ObservabilityConfig,
    SecurityConfig,
    StorageConfig,
    ToolsConfig,
)
from .settings import Settings

__all__ = [
    # Main exports
    "Config",
    "get_config",
    "Settings",
    # Schemas
    "AppConfig",
    "APIConfig",
    "EnginesConfig",
    "ContextConfig",
    "ToolsConfig",
    "StorageConfig",
    "ObservabilityConfig",
    "SecurityConfig",
    # Exceptions
    "ConfigurationError",
    "MissingRequiredSecretError",
    "InvalidConfigurationError",
    "ConfigurationVersionMismatchError",
]
