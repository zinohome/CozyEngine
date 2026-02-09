"""Configuration exceptions."""


class ConfigurationError(Exception):
    """Base exception for configuration errors."""

    pass


class MissingRequiredSecretError(ConfigurationError):
    """Raised when a required secret is missing."""

    def __init__(self, secret_name: str, env_var: str):
        self.secret_name = secret_name
        self.env_var = env_var
        super().__init__(
            f"Missing required secret: {secret_name}. "
            f"Please set the environment variable: {env_var}"
        )


class InvalidConfigurationError(ConfigurationError):
    """Raised when configuration validation fails."""

    pass


class ConfigurationVersionMismatchError(ConfigurationError):
    """Raised when configuration version is incompatible."""

    pass
