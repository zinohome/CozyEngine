# CozyEngine Configuration System

## Overview

CozyEngine uses a hierarchical configuration system with three layers:

**Priority Order: YAML > Environment Variables > Code Defaults**

- **YAML Files**: Structured configuration for defaults and policies
- **Environment Variables**: Secrets, deployment-specific values, and overrides  
- **Code Defaults**: Fallback values in Pydantic models

## Directory Structure

```
backend/
├── config/                    # YAML configuration files
│   ├── app.yaml              # Application settings
│   ├── api.yaml              # API configuration
│   ├── engines.yaml          # Engine configurations
│   ├── context.yaml          # Context management
│   ├── tools.yaml            # Tools configuration
│   ├── storage.yaml          # Database & Redis
│   ├── observability.yaml    # Logging, metrics, tracing
│   └── security.yaml         # Auth, audit, rate limiting
├── app/
│   └── core/
│       └── config/           # Configuration module
│           ├── __init__.py
│           ├── exceptions.py # Custom exceptions
│           ├── loader.py     # YAML loader
│           ├── manager.py    # Configuration manager
│           ├── schemas.py    # Pydantic models
│           └── settings.py   # Environment settings
└── .env.example              # Environment variable template
```

## Quick Start

### 1. Copy Environment Template

```bash
cp .env.example .env
```

### 2. Set Required Variables

**Minimum for Development:**
```bash
# At least one AI provider is required
OPENAI_API_KEY=sk-your-key-here
# OR
ANTHROPIC_API_KEY=sk-ant-your-key-here
# OR
OLLAMA_BASE_URL=http://localhost:11434
```

**Additional for Production:**
```bash
APP_ENV=production
SECRET_KEY=your-secure-secret-key-minimum-32-characters
DATABASE_URL=postgresql://user:pass@host:5432/dbname
```

### 3. Start the Application

```bash
cd backend
python3 -m uvicorn app.main:app --reload
```

## Configuration Files

### app.yaml

Application-level settings:
- Name, version, description
- Environment (development/staging/production)
- Debug mode
- Server settings (host, port, workers)
- CORS configuration

### api.yaml

API behavior:
- Route prefixes
- OpenAI compatibility
- SSE (Server-Sent Events) parameters
- Request/response limits

### engines.yaml

AI and personalization engines:
- **AI Engine**: LLM providers (OpenAI, Anthropic, Ollama)
- **Knowledge Engine**: Knowledge retrieval (Cognee, Memobase)
- **User Profile Engine**: User preferences
- **Chat Memory Engine**: Conversation memory (Mem0, local)
- **Tools Engine**: Function calling and MCP

### context.yaml

Context assembly and management:
- Token budget allocation
- Parallel engine execution
- Degradation strategies
- Context assembly rules

### tools.yaml

Tool execution configuration:
- Whitelist management
- Permission checks
- Audit logging
- MCP service discovery
- Execution limits

### storage.yaml

Data persistence:
- PostgreSQL connection pooling
- Redis caching and queueing
- Connection timeouts

### observability.yaml

Monitoring and logging:
- Log level, format, and sanitization
- Metrics collection
- OpenTelemetry tracing
- Sentry error tracking

### security.yaml

Security features:
- Authentication (JWT)
- Authorization (RBAC)
- Audit logging
- Rate limiting
- API key validation

## Environment Variables

### Application

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `APP_NAME` | No | CozyEngine | Application name |
| `APP_ENV` | No | development | Environment: development/staging/production |
| `DEBUG` | No | false | Debug mode |
| `LOG_LEVEL` | No | INFO | Logging level |
| `HOST` | No | 0.0.0.0 | Server host |
| `PORT` | No | 8000 | Server port |
| `ALLOWED_ORIGINS` | No | "" | CORS allowed origins (comma-separated) |

### Security

| Variable | Required | Description |
|----------|----------|-------------|
| `SECRET_KEY` | Prod only | Application secret key (min 32 chars) |
| `JWT_SECRET_KEY` | No | JWT signing key |

### Database

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | Staging/Prod | PostgreSQL connection URL |
| `DATABASE_POOL_SIZE` | No | Connection pool size (default: 10) |
| `REDIS_URL` | No | Redis connection URL |

### AI Providers

**At least ONE AI provider is required:**

| Variable | Description |
|----------|-------------|
| `OPENAI_API_KEY` | OpenAI API key |
| `OPENAI_ORG_ID` | OpenAI organization ID (optional) |
| `ANTHROPIC_API_KEY` | Anthropic API key |
| `OLLAMA_BASE_URL` | Ollama server URL (for local models) |

### Personalization Engines (Optional)

| Variable | Description |
|----------|-------------|
| `COGNEE_API_URL` | Cognee API endpoint |
| `COGNEE_API_TOKEN` | Cognee API token |
| `MEMOBASE_PROJECT_URL` | Memobase project URL |
| `MEMOBASE_API_KEY` | Memobase API key |
| `MEM0_API_URL` | Mem0 API endpoint |
| `MEM0_API_KEY` | Mem0 API key |

### Observability (Optional)

| Variable | Description |
|----------|-------------|
| `OTEL_ENABLED` | Enable OpenTelemetry tracing |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | OTLP endpoint |
| `SENTRY_DSN` | Sentry DSN for error tracking |
| `SENTRY_ENABLED` | Enable Sentry |

## Environment Layering

Configuration can be layered by environment:

1. **Base configuration**: `config/app.yaml`
2. **Environment overlay**: `config/app.development.yaml` (if exists)
3. **Environment variables**: Override specific values

Example for staging:
```yaml
# config/app.staging.yaml
app:
  debug: false
  server:
    workers: 4
```

## Configuration Validation

### Startup Checks

On startup, the configuration system:

1. ✅ Loads and merges all YAML files
2. ✅ Applies environment variable overrides
3. ✅ Validates all values with Pydantic schemas
4. ✅ Checks for required secrets based on environment
5. ✅ Outputs sanitized configuration summary
6. ❌ **Fails fast** with clear error messages if validation fails

### Example Error Messages

**Missing AI Provider:**
```
❌ Configuration Error: Missing required secret: AI_PROVIDER
At least one of: OPENAI_API_KEY, ANTHROPIC_API_KEY, or OLLAMA_BASE_URL
```

**Invalid Port:**
```
❌ Configuration Error: Configuration validation failed
PORT: Input should be less than or equal to 65535
```

**Missing Production Secrets:**
```
❌ Configuration Error: Missing required secrets:
  - SECRET_KEY
  - DATABASE_URL
Please set the required environment variables for environment: production
```

## Accessing Configuration

### In Application Code

```python
from app.core.config import get_config

# Get global configuration instance
config = get_config()

# Access configuration values
print(config.app.name)
print(config.engines.ai.default_provider)
print(config.context.parallel_execution.enabled)
```

### Configuration Summary

Get a sanitized summary (no secrets) for logging:

```python
summary = config.get_sanitized_config_summary()
# Returns dict with all non-sensitive configuration
```

## Testing

Run configuration tests:

```bash
cd backend
python3 -m pytest tests/core/test_config.py -v -o addopts=""
```

Test coverage includes:
- ✅ YAML loading and parsing
- ✅ Environment variable overrides
- ✅ Multi-environment support
- ✅ Schema validation
- ✅ Required secret checking
- ✅ Configuration sanitization

## Troubleshooting

### Configuration not loading

1. Check that `backend/config/` directory exists
2. Verify YAML files are valid (use `yamllint`)
3. Check file permissions

### Missing required secrets

1. Review error message for specific missing variables
2. Check `.env` file exists and is readable
3. Verify environment variables are set: `env | grep OPENAI`

### Invalid configuration values

1. Check Pydantic validation errors in output
2. Verify value types and ranges match schemas
3. Review `app/core/config/schemas.py` for constraints

### Environment not detected

1. Set `APP_ENV` explicitly: `export APP_ENV=production`
2. Check `.env` file has correct values
3. Verify no typos in environment variable names

## Best Practices

1. **Never commit secrets**: Use `.env` for local development, environment variables for production
2. **Use environment overlays**: Create `config/*.production.yaml` for environment-specific defaults
3. **Validate early**: Configuration validation happens at startup to fail fast
4. **Log sanitized config**: Startup logs show configuration with secrets redacted
5. **Version your config**: Each YAML file includes `config_version` for tracking changes

## Security Notes

- Secrets are never logged (automatic redaction)
- Configuration summary excludes sensitive values
- Production requires explicit `SECRET_KEY` and `DATABASE_URL`
- Use `SecretStr` type for any secret values in code
- Rotate secrets regularly and update environment variables

## Version

Configuration System Version: **2.0.0**  
Last Updated: **2026-02-09**
