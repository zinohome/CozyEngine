"""Configuration schemas using Pydantic models."""

from typing import Literal

from pydantic import BaseModel, Field, field_validator


# ============================================================================
# App Configuration
# ============================================================================


class ServerConfig(BaseModel):
    """Server configuration."""

    host: str = "0.0.0.0"
    port: int = Field(default=8000, ge=1, le=65535)
    reload: bool = False
    workers: int = Field(default=1, ge=1, le=32)


class CorsConfig(BaseModel):
    """CORS configuration."""

    enabled: bool = True
    allow_origins: list[str] = Field(default_factory=list)
    allow_credentials: bool = True
    allow_methods: list[str] = Field(default_factory=lambda: ["*"])
    allow_headers: list[str] = Field(default_factory=lambda: ["*"])


class AppConfig(BaseModel):
    """Application configuration."""

    name: str = "CozyEngine"
    version: str = "0.1.0"
    description: str = "Modern AI Agent Orchestration Framework"
    environment: Literal["development", "staging", "production"] = "development"
    debug: bool = False
    server: ServerConfig = Field(default_factory=ServerConfig)
    cors: CorsConfig = Field(default_factory=CorsConfig)


# ============================================================================
# API Configuration
# ============================================================================


class SSEConfig(BaseModel):
    """Server-Sent Events configuration."""

    enabled: bool = True
    heartbeat_interval: int = Field(default=15, ge=1, le=300)
    max_timeout: int = Field(default=300, ge=10, le=3600)


class APILimitsConfig(BaseModel):
    """API limits configuration."""

    max_request_size: int = Field(default=10485760, ge=1024)  # 10MB
    max_response_tokens: int = Field(default=4096, ge=1, le=128000)
    rate_limit_per_minute: int = Field(default=60, ge=1, le=10000)


class APIResponseConfig(BaseModel):
    """API response configuration."""

    include_usage: bool = True
    include_timing: bool = False


class APIConfig(BaseModel):
    """API configuration."""

    v1_prefix: str = "/v1"
    openai_compatible: bool = True
    sse: SSEConfig = Field(default_factory=SSEConfig)
    limits: APILimitsConfig = Field(default_factory=APILimitsConfig)
    response: APIResponseConfig = Field(default_factory=APIResponseConfig)


# ============================================================================
# Engines Configuration
# ============================================================================


class AIProviderConfig(BaseModel):
    """AI provider configuration."""

    enabled: bool = True
    model: str
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=4096, ge=1, le=128000)


class AIEngineConfig(BaseModel):
    """AI engine configuration."""

    default_provider: str = "openai"
    providers: dict[str, AIProviderConfig] = Field(default_factory=dict)

    @field_validator("providers")
    @classmethod
    def validate_default_provider(cls, v: dict, info) -> dict:
        """Validate that default_provider exists in providers."""
        if hasattr(info, "data") and "default_provider" in info.data:
            default = info.data["default_provider"]
            if default not in v:
                raise ValueError(f"Default provider '{default}' not found in providers")
        return v


class KnowledgeProviderConfig(BaseModel):
    """Knowledge provider configuration."""

    enabled: bool = True
    timeout: float = Field(default=5.0, ge=0.1, le=60.0)


class KnowledgeEngineConfig(BaseModel):
    """Knowledge engine configuration."""

    default_provider: str = "cognee"
    enabled: bool = True
    providers: dict[str, KnowledgeProviderConfig] = Field(default_factory=dict)


class UserProfileEngineConfig(BaseModel):
    """User profile engine configuration."""

    default_provider: str = "local"
    enabled: bool = True
    timeout: float = Field(default=3.0, ge=0.1, le=60.0)


class ChatMemoryProviderConfig(BaseModel):
    """Chat memory provider configuration."""

    enabled: bool = True
    timeout: float = Field(default=5.0, ge=0.1, le=60.0)


class ChatMemoryEngineConfig(BaseModel):
    """Chat memory engine configuration."""

    default_provider: str = "mem0"
    enabled: bool = True
    providers: dict[str, ChatMemoryProviderConfig] = Field(default_factory=dict)


class ToolsEngineConfig(BaseModel):
    """Tools engine configuration."""

    enabled: bool = True
    timeout: float = Field(default=30.0, ge=1.0, le=300.0)
    max_iterations: int = Field(default=5, ge=1, le=20)


class EnginesConfig(BaseModel):
    """Engines configuration."""

    ai: AIEngineConfig = Field(default_factory=AIEngineConfig)
    knowledge: KnowledgeEngineConfig = Field(default_factory=KnowledgeEngineConfig)
    user_profile: UserProfileEngineConfig = Field(default_factory=UserProfileEngineConfig)
    chat_memory: ChatMemoryEngineConfig = Field(default_factory=ChatMemoryEngineConfig)
    tools: ToolsEngineConfig = Field(default_factory=ToolsEngineConfig)


# ============================================================================
# Context Configuration
# ============================================================================


class TokenBudgetConfig(BaseModel):
    """Token budget configuration."""

    max_context_tokens: int = Field(default=100000, ge=1000, le=1000000)
    reserve_for_completion: int = Field(default=4096, ge=100, le=128000)
    personalization_budget: int = Field(default=10000, ge=100, le=100000)


class ParallelExecutionConfig(BaseModel):
    """Parallel execution configuration."""

    enabled: bool = True
    max_workers: int = Field(default=3, ge=1, le=10)
    timeout: float = Field(default=10.0, ge=1.0, le=60.0)


class DegradationConfig(BaseModel):
    """Degradation strategy configuration."""

    enabled: bool = True
    allow_partial_failure: bool = True
    min_required_engines: int = Field(default=0, ge=0, le=3)


class ContextAssemblyConfig(BaseModel):
    """Context assembly configuration."""

    include_system_prompt: bool = True
    include_knowledge: bool = True
    include_user_profile: bool = True
    include_chat_memory: bool = True
    include_tool_definitions: bool = True


class ContextConfig(BaseModel):
    """Context management configuration."""

    token_budget: TokenBudgetConfig = Field(default_factory=TokenBudgetConfig)
    parallel_execution: ParallelExecutionConfig = Field(default_factory=ParallelExecutionConfig)
    degradation: DegradationConfig = Field(default_factory=DegradationConfig)
    assembly: ContextAssemblyConfig = Field(default_factory=ContextAssemblyConfig)


# ============================================================================
# Tools Configuration
# ============================================================================


class ToolsWhitelistConfig(BaseModel):
    """Tools whitelist configuration."""

    enabled: bool = True
    mode: Literal["strict", "permissive"] = "strict"
    allowed_tools: list[str] = Field(default_factory=list)


class ToolsPermissionsConfig(BaseModel):
    """Tools permissions configuration."""

    enabled: bool = True
    require_user_consent: bool = True


class ToolsAuditConfig(BaseModel):
    """Tools audit configuration."""

    enabled: bool = True
    log_all_calls: bool = True
    log_arguments: bool = True
    log_results: bool = False


class MCPConfig(BaseModel):
    """MCP (Model Context Protocol) configuration."""

    enabled: bool = False
    discovery_url: str = ""
    timeout: float = Field(default=5.0, ge=0.1, le=60.0)


class ToolsLimitsConfig(BaseModel):
    """Tools execution limits configuration."""

    max_concurrent_calls: int = Field(default=5, ge=1, le=50)
    max_retry_attempts: int = Field(default=2, ge=0, le=5)
    timeout_per_call: float = Field(default=30.0, ge=1.0, le=300.0)
    max_calls_per_minute: int = Field(default=10, ge=1, le=1000)


class ToolsConfig(BaseModel):
    """Tools configuration."""

    whitelist: ToolsWhitelistConfig = Field(default_factory=ToolsWhitelistConfig)
    permissions: ToolsPermissionsConfig = Field(default_factory=ToolsPermissionsConfig)
    audit: ToolsAuditConfig = Field(default_factory=ToolsAuditConfig)
    mcp: MCPConfig = Field(default_factory=MCPConfig)
    limits: ToolsLimitsConfig = Field(default_factory=ToolsLimitsConfig)


# ============================================================================
# Storage Configuration
# ============================================================================


class DatabaseConfig(BaseModel):
    """Database configuration."""

    pool_size: int = Field(default=10, ge=1, le=100)
    max_overflow: int = Field(default=20, ge=0, le=100)
    pool_timeout: float = Field(default=30.0, ge=1.0, le=300.0)
    pool_recycle: int = Field(default=3600, ge=300, le=86400)
    echo: bool = False


class RedisCacheConfig(BaseModel):
    """Redis cache configuration."""

    enabled: bool = True
    default_ttl: int = Field(default=3600, ge=1, le=604800)
    key_prefix: str = "cozyengine:"


class RedisQueueConfig(BaseModel):
    """Redis queue configuration."""

    enabled: bool = False
    default_queue: str = "default"


class RedisConfig(BaseModel):
    """Redis configuration."""

    enabled: bool = True
    max_connections: int = Field(default=50, ge=1, le=1000)
    socket_timeout: float = Field(default=5.0, ge=0.1, le=60.0)
    socket_connect_timeout: float = Field(default=5.0, ge=0.1, le=60.0)
    retry_on_timeout: bool = True
    cache: RedisCacheConfig = Field(default_factory=RedisCacheConfig)
    queue: RedisQueueConfig = Field(default_factory=RedisQueueConfig)


class StorageConfig(BaseModel):
    """Storage configuration."""

    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    redis: RedisConfig = Field(default_factory=RedisConfig)


# ============================================================================
# Observability Configuration
# ============================================================================


class LoggingIncludeFieldsConfig(BaseModel):
    """Logging include fields configuration."""

    request_id: bool = True
    user_id: bool = True
    session_id: bool = True
    personality_id: bool = True
    timestamp: bool = True


class LoggingSanitizeConfig(BaseModel):
    """Logging sanitization configuration."""

    enabled: bool = True
    redact_patterns: list[str] = Field(
        default_factory=lambda: ["api_key", "secret", "password", "token"]
    )


class LoggingConfig(BaseModel):
    """Logging configuration."""

    level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    format: Literal["json", "text"] = "json"
    include_fields: LoggingIncludeFieldsConfig = Field(
        default_factory=LoggingIncludeFieldsConfig
    )
    sanitize: LoggingSanitizeConfig = Field(default_factory=LoggingSanitizeConfig)


class MetricsCollectConfig(BaseModel):
    """Metrics collection configuration."""

    request_count: bool = True
    request_duration: bool = True
    token_usage: bool = True
    engine_performance: bool = True
    error_rate: bool = True


class MetricsConfig(BaseModel):
    """Metrics configuration."""

    enabled: bool = True
    export_interval: int = Field(default=60, ge=1, le=3600)
    collect: MetricsCollectConfig = Field(default_factory=MetricsCollectConfig)


class TracingConfig(BaseModel):
    """Tracing configuration."""

    enabled: bool = False
    sample_rate: float = Field(default=0.1, ge=0.0, le=1.0)
    export_protocol: Literal["otlp", "jaeger", "zipkin"] = "otlp"


class SentryConfig(BaseModel):
    """Sentry configuration."""

    enabled: bool = False
    traces_sample_rate: float = Field(default=0.1, ge=0.0, le=1.0)
    profiles_sample_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    environment: str = "development"


class ObservabilityConfig(BaseModel):
    """Observability configuration."""

    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    metrics: MetricsConfig = Field(default_factory=MetricsConfig)
    tracing: TracingConfig = Field(default_factory=TracingConfig)
    sentry: SentryConfig = Field(default_factory=SentryConfig)


# ============================================================================
# Security Configuration
# ============================================================================


class JWTConfig(BaseModel):
    """JWT configuration."""

    algorithm: str = "HS256"
    access_token_expire_minutes: int = Field(default=30, ge=1, le=1440)
    refresh_token_expire_days: int = Field(default=7, ge=1, le=90)


class AuthenticationConfig(BaseModel):
    """Authentication configuration."""

    enabled: bool = False
    jwt: JWTConfig = Field(default_factory=JWTConfig)


class AuthorizationConfig(BaseModel):
    """Authorization configuration."""

    enabled: bool = False
    default_role: str = "user"


class SecurityAuditConfig(BaseModel):
    """Security audit configuration."""

    enabled: bool = True
    log_all_requests: bool = False
    log_mutations: bool = True
    log_tool_calls: bool = True
    log_failed_auth: bool = True


class RateLimitingConfig(BaseModel):
    """Rate limiting configuration."""

    enabled: bool = False
    strategy: Literal["sliding_window", "fixed_window", "token_bucket"] = "sliding_window"
    requests_per_minute: int = Field(default=60, ge=1, le=10000)


class APIKeysConfig(BaseModel):
    """API keys configuration."""

    enabled: bool = False
    header_name: str = "X-API-Key"


class SecurityConfig(BaseModel):
    """Security configuration."""

    authentication: AuthenticationConfig = Field(default_factory=AuthenticationConfig)
    authorization: AuthorizationConfig = Field(default_factory=AuthorizationConfig)
    audit: SecurityAuditConfig = Field(default_factory=SecurityAuditConfig)
    rate_limiting: RateLimitingConfig = Field(default_factory=RateLimitingConfig)
    api_keys: APIKeysConfig = Field(default_factory=APIKeysConfig)
