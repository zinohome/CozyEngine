"""Tests for configuration system."""

import os
from pathlib import Path

import pytest

from app.core.config import (
    Config,
    ConfigurationError,
    InvalidConfigurationError,
    MissingRequiredSecretError,
    get_config,
)


@pytest.fixture
def config_dir():
    """Provide path to test configuration directory."""
    backend_dir = Path(__file__).parent.parent.parent
    return backend_dir / "config"


@pytest.fixture
def mock_env(monkeypatch):
    """Set up minimal environment variables for testing."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")
    monkeypatch.setenv("APP_ENV", "development")


class TestConfigurationLoading:
    """Test configuration loading from YAML."""

    def test_load_config_success(self, config_dir, mock_env):
        """Test successful configuration loading."""
        config = Config(config_dir=config_dir)

        assert config is not None
        assert config.config_version == "2.0.0"
        assert config.environment == "development"
        assert config.app.name == "CozyEngine"

    def test_missing_config_directory(self, mock_env):
        """Test error when configuration directory doesn't exist."""
        with pytest.raises(ConfigurationError, match="Configuration directory not found"):
            Config(config_dir=Path("/nonexistent/path"))

    def test_config_version_loaded(self, config_dir, mock_env):
        """Test that configuration version is loaded correctly."""
        config = Config(config_dir=config_dir)
        assert config.config_version == "2.0.0"


class TestEnvironmentVariableOverrides:
    """Test environment variable overrides."""

    def test_env_overrides_yaml(self, config_dir, monkeypatch):
        """Test that environment variables override YAML configuration."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")
        monkeypatch.setenv("APP_ENV", "production")
        monkeypatch.setenv("DEBUG", "true")
        monkeypatch.setenv("PORT", "9000")
        monkeypatch.setenv("SECRET_KEY", "test-secret-key-at-least-32-chars-long")
        monkeypatch.setenv("DATABASE_URL", "postgresql://test:test@localhost/test")

        config = Config(config_dir=config_dir)

        assert config.environment == "production"
        assert config.app.debug is True
        assert config.app.server.port == 9000

    def test_cors_origins_from_env(self, config_dir, monkeypatch):
        """Test CORS origins loaded from environment variable."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")
        monkeypatch.setenv("ALLOWED_ORIGINS", "http://localhost:3000,https://example.com")

        config = Config(config_dir=config_dir)

        assert "http://localhost:3000" in config.app.cors.allow_origins
        assert "https://example.com" in config.app.cors.allow_origins


class TestSecretValidation:
    """Test secret validation."""

    def test_missing_ai_provider_development(self, config_dir, monkeypatch):
        """Test that missing AI provider raises error even in development."""
        monkeypatch.setenv("APP_ENV", "development")
        # Don't set any AI provider

        with pytest.raises(MissingRequiredSecretError, match="AI_PROVIDER"):
            Config(config_dir=config_dir)

    def test_missing_database_production(self, config_dir, monkeypatch):
        """Test that missing database URL raises error in production."""
        monkeypatch.setenv("APP_ENV", "production")
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")
        # Don't set DATABASE_URL or SECRET_KEY

        with pytest.raises(MissingRequiredSecretError):
            Config(config_dir=config_dir)

    def test_ollama_as_ai_provider(self, config_dir, monkeypatch):
        """Test that Ollama can be used as AI provider (no API key needed)."""
        monkeypatch.setenv("OLLAMA_BASE_URL", "http://localhost:11434")

        config = Config(config_dir=config_dir)
        assert config is not None


class TestConfigurationSummary:
    """Test configuration summary generation."""

    def test_sanitized_summary_no_secrets(self, config_dir, mock_env):
        """Test that sanitized summary doesn't contain secrets."""
        config = Config(config_dir=config_dir)
        summary = config.get_sanitized_config_summary()

        # Convert to string to check for any secret-like patterns
        summary_str = str(summary)

        # Should not contain common secret patterns
        assert "sk-" not in summary_str
        assert "password" not in summary_str.lower()
        assert "secret" not in summary_str.lower()

        # Should contain expected fields
        assert summary["config_version"] == "2.0.0"
        assert summary["environment"] == "development"
        assert "app" in summary
        assert "engines" in summary
        assert "observability" in summary

    def test_summary_structure(self, config_dir, mock_env):
        """Test that summary has expected structure."""
        config = Config(config_dir=config_dir)
        summary = config.get_sanitized_config_summary()

        assert "config_version" in summary
        assert "environment" in summary
        assert "app" in summary
        assert "api" in summary
        assert "engines" in summary
        assert "context" in summary
        assert "observability" in summary
        assert "security" in summary


class TestSchemaValidation:
    """Test Pydantic schema validation."""

    def test_invalid_port_number(self, config_dir, monkeypatch):
        """Test that invalid port number is caught by validation."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")
        monkeypatch.setenv("PORT", "99999")  # Invalid port

        # Settings validation happens first and raises ValidationError from pydantic
        from pydantic import ValidationError as PydanticValidationError

        with pytest.raises((InvalidConfigurationError, PydanticValidationError)):
            Config(config_dir=config_dir)

    def test_invalid_environment(self, config_dir, monkeypatch):
        """Test that invalid environment is caught by validation."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")
        monkeypatch.setenv("APP_ENV", "invalid_env")

        # Settings validation happens first and raises ValidationError from pydantic
        from pydantic import ValidationError as PydanticValidationError

        with pytest.raises((InvalidConfigurationError, PydanticValidationError)):
            Config(config_dir=config_dir)


class TestGlobalConfigInstance:
    """Test global configuration instance management."""

    def test_get_config_singleton(self, config_dir, mock_env):
        """Test that get_config returns the same instance."""
        # Clear any existing instance
        import app.core.config.manager

        app.core.config.manager._config = None

        config1 = get_config(config_dir=config_dir)
        config2 = get_config()

        assert config1 is config2

    def test_get_config_reload(self, config_dir, mock_env, monkeypatch):
        """Test that get_config can reload configuration."""
        import app.core.config.manager

        app.core.config.manager._config = None

        config1 = get_config(config_dir=config_dir)
        original_env = config1.environment

        # Change environment
        monkeypatch.setenv("APP_ENV", "production")
        monkeypatch.setenv("SECRET_KEY", "test-secret-key-at-least-32-chars")
        monkeypatch.setenv("DATABASE_URL", "postgresql://test:test@localhost/test")

        config2 = get_config(config_dir=config_dir, reload=True)

        assert config2.environment == "production"
        assert config2.environment != original_env


class TestEnginesConfiguration:
    """Test engines configuration."""

    def test_ai_engine_default_provider(self, config_dir, mock_env):
        """Test AI engine default provider configuration."""
        config = Config(config_dir=config_dir)

        assert config.engines.ai.default_provider == "openai"
        assert "openai" in config.engines.ai.providers
        assert config.engines.ai.providers["openai"].enabled is True

    def test_personalization_engines_enabled(self, config_dir, mock_env):
        """Test that personalization engines can be enabled."""
        config = Config(config_dir=config_dir)

        assert config.engines.knowledge.enabled is True
        assert config.engines.user_profile.enabled is True
        assert config.engines.chat_memory.enabled is True


class TestObservabilityConfiguration:
    """Test observability configuration."""

    def test_log_level_from_env(self, config_dir, monkeypatch):
        """Test log level loaded from environment."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")
        monkeypatch.setenv("LOG_LEVEL", "DEBUG")

        config = Config(config_dir=config_dir)

        assert config.observability.logging.level == "DEBUG"

    def test_metrics_enabled_by_default(self, config_dir, mock_env):
        """Test that metrics are enabled by default."""
        config = Config(config_dir=config_dir)

        assert config.observability.metrics.enabled is True

    def test_tracing_disabled_by_default(self, config_dir, mock_env):
        """Test that tracing is disabled by default."""
        config = Config(config_dir=config_dir)

        assert config.observability.tracing.enabled is False
