"""YAML configuration loader."""

import os
from pathlib import Path
from typing import Any

import yaml

from .exceptions import ConfigurationError


class YAMLConfigLoader:
    """Load and merge YAML configuration files."""

    def __init__(self, config_dir: Path | None = None):
        """Initialize the loader.

        Args:
            config_dir: Directory containing configuration files.
                       Defaults to backend/config relative to project root.
        """
        if config_dir is None:
            # Default to backend/config relative to the project root
            project_root = Path(__file__).parent.parent.parent.parent
            config_dir = project_root / "config"

        self.config_dir = Path(config_dir)
        if not self.config_dir.exists():
            raise ConfigurationError(f"Configuration directory not found: {self.config_dir}")

    def load_namespace(self, namespace: str) -> dict[str, Any]:
        """Load a configuration namespace from YAML file.

        Args:
            namespace: Name of the configuration namespace (e.g., 'app', 'api')

        Returns:
            Configuration dictionary for the namespace

        Raises:
            ConfigurationError: If the configuration file cannot be loaded
        """
        config_file = self.config_dir / f"{namespace}.yaml"

        if not config_file.exists():
            raise ConfigurationError(f"Configuration file not found: {config_file}")

        try:
            with config_file.open("r") as f:
                config_data = yaml.safe_load(f)

            if not config_data:
                raise ConfigurationError(f"Empty configuration file: {config_file}")

            # Extract the namespace data
            if namespace not in config_data:
                raise ConfigurationError(
                    f"Namespace '{namespace}' not found in {config_file}. "
                    f"Found keys: {list(config_data.keys())}"
                )

            return config_data[namespace]

        except yaml.YAMLError as e:
            raise ConfigurationError(f"Failed to parse YAML file {config_file}: {e}") from e
        except OSError as e:
            raise ConfigurationError(f"Failed to read configuration file {config_file}: {e}") from e

    def load_all(self) -> dict[str, dict[str, Any]]:
        """Load all configuration namespaces.

        Returns:
            Dictionary mapping namespace names to their configuration
        """
        namespaces = [
            "app",
            "api",
            "engines",
            "context",
            "tools",
            "storage",
            "observability",
            "security",
        ]

        config = {}
        for namespace in namespaces:
            try:
                config[namespace] = self.load_namespace(namespace)
            except ConfigurationError:
                # If namespace file doesn't exist, use empty dict
                config[namespace] = {}

        return config

    def get_config_version(self) -> str:
        """Get the configuration version from app.yaml.

        Returns:
            Configuration version string
        """
        config_file = self.config_dir / "app.yaml"
        try:
            with config_file.open("r") as f:
                config_data = yaml.safe_load(f)
            return config_data.get("config_version", "unknown")
        except Exception:
            return "unknown"

    def load_environment_specific(self, namespace: str, environment: str) -> dict[str, Any]:
        """Load environment-specific configuration overlay.

        Args:
            namespace: Configuration namespace
            environment: Environment name (development, staging, production)

        Returns:
            Environment-specific configuration overlay, or empty dict if not found
        """
        env_file = self.config_dir / f"{namespace}.{environment}.yaml"

        if not env_file.exists():
            return {}

        try:
            with env_file.open("r") as f:
                config_data = yaml.safe_load(f)

            if not config_data or namespace not in config_data:
                return {}

            return config_data[namespace]

        except (yaml.YAMLError, OSError):
            # Environment-specific configs are optional, so we don't raise errors
            return {}
