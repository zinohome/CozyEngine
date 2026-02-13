# CozyEngine Backend

Modern AI Agent Orchestration Framework - Backend API

## 🏗️ Project Structure

```
backend/
├── app/
│   ├── api/              # API endpoints & routers
│   ├── core/             # Core business logic & domain models
│   ├── orchestration/    # Agent orchestration engine
│   ├── context/          # Context management & state
│   ├── engines/          # AI engine adapters (OpenAI, Anthropic, etc.)
│   ├── storage/          # Data persistence & caching
│   ├── middleware/       # HTTP middleware
│   ├── observability/    # Logging, metrics, tracing
│   └── utils/            # Shared utilities
├── tests/                # Test suite
├── pyproject.toml        # Project dependencies & configuration
└── README.md             # This file
```

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- pip

### Installation

#### One-command setup (recommended)

Creates `backend/venv` (if missing) and installs dependencies.

```bash
cd backend
./scripts/setup_venv.sh
```

Runtime-only install (no dev tools like pytest/ruff/pyright):

```bash
cd backend
./scripts/setup_venv.sh --prod
```

#### Manual (pip)

```bash
cd backend
python3 -m venv venv
./venv/bin/python -m pip install --upgrade pip setuptools wheel
./venv/bin/python -m pip install -e ".[dev]"
```

### Configuration

```bash
# Copy example environment file
cp .env.example .env

# Edit .env with your settings
vim .env
```

### Running the Application

```bash
# Development server with auto-reload
./venv/bin/python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at:
- **API**: http://localhost:8000
- **Docs**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## 🧪 Testing

```bash
# Run all tests
./venv/bin/python -m pytest

# Run with coverage
./venv/bin/python -m pytest --cov=app --cov-report=html

# Run specific test file
./venv/bin/python -m pytest tests/test_example.py

# Run with verbose output
./venv/bin/python -m pytest -v
```

## 🔍 Code Quality

### Linting & Formatting

```bash
# Check code style
./venv/bin/python -m ruff check .

# Auto-fix issues
./venv/bin/python -m ruff check --fix .

# Format code
./venv/bin/python -m ruff format .
```

### Type Checking

```bash
# Run type checker
./venv/bin/python -m pyright
```

### All Checks

```bash
# Run all quality checks
./venv/bin/python -m ruff check . && ./venv/bin/python -m ruff format --check . && ./venv/bin/python -m pyright && ./venv/bin/python -m pytest -q
```

## 📦 Dependencies

### Core Dependencies

- **FastAPI** - Modern web framework
- **Pydantic** - Data validation
- **SQLAlchemy** - Database ORM
- **Redis** - Caching & pub/sub
- **Structlog** - Structured logging
- **OpenTelemetry** - Observability

### Development Dependencies

- **pytest** - Testing framework
- **ruff** - Linting & formatting
- **pyright** - Static type checker

## 🏃 Development Workflow

1. **Create feature branch**
   ```bash
   git checkout -b feature/your-feature
   ```

2. **Make changes & test**
   ```bash
   pytest
   ruff check --fix .
   pyright
   ```

3. **Commit & push**
   ```bash
   git add .
   git commit -m "feat: your feature description"
   git push origin feature/your-feature
   ```

## 📝 Environment Variables

See `.env.example` for all available configuration options.

Key variables:
- `APP_ENV` - Environment (development/staging/production)
- `DATABASE_URL` - PostgreSQL connection string
- `REDIS_URL` - Redis connection string
- `OPENAI_API_KEY` - OpenAI API key
- `ANTHROPIC_API_KEY` - Anthropic API key

## 🔐 Security

- Never commit `.env` file
- Use strong `SECRET_KEY` in production
- Keep API keys secure
- Review `ALLOWED_ORIGINS` for CORS

## 📚 Documentation

- [Architecture Guide](../docs/architecture/)
- [API Documentation](http://localhost:8000/docs) (when running)
- [Development Standards](../docs/standards/)

## 🤝 Contributing

1. Follow the code style (enforced by ruff)
2. Write tests for new features
3. Update documentation
4. Ensure all checks pass

## 📄 License

See LICENSE file in project root.
