# API Development Guide

Guide for contributing to the Exousia API backend.

## Development Setup

### Prerequisites

- Python 3.11 or 3.12
- PostgreSQL (for production-like development) or SQLite (default)
- Podman and podman-compose (optional, for containerized development)

### Installation

```bash
# Clone the repository
git clone https://github.com/borninthedark/exousia.git
cd exousia

# Install development dependencies
pip install -r api/requirements.txt

# Install pre-commit hooks
pre-commit install
```

### Environment Configuration

Create a `.env` file in the project root:

```bash
# Development settings
API_HOST=0.0.0.0
API_PORT=8000
DATABASE_URL=sqlite+aiosqlite:///./exousia.db

# GitHub integration (optional for local dev)
GITHUB_TOKEN=your_token_here
GITHUB_REPO=borninthedark/exousia
GITHUB_WORKFLOW_FILE=build.yaml

# Transpiler
TRANSPILER_SCRIPT=tools/yaml-to-containerfile.py
```

## Running Locally

### Option 1: Direct Python

```bash
cd api
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Access:
- API: http://localhost:8000
- Interactive docs: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

### Option 2: Podman Compose

```bash
# Start all services
podman-compose up

# Rebuild after code changes
podman-compose up --build

# View logs
podman-compose logs -f api

# Stop services
podman-compose down
```

## Code Quality Tools

### Formatting

```bash
# Format code with black
black api/ tools/

# Sort imports with isort
isort api/ tools/

# Both at once
make format
```

### Linting

```bash
# Run ruff (fast linter)
ruff check api/ tools/

# Run pylint (comprehensive)
pylint api/**/*.py tools/*.py

# Run mypy (type checking)
mypy api/

# All linters
make lint
```

### Pre-commit Hooks

Hooks run automatically on `git commit`:

```bash
# Run hooks manually
pre-commit run --all-files

# Update hooks
pre-commit autoupdate
```

## Testing

### Running Tests

```bash
# All tests
pytest api/tests/ -v

# With coverage
pytest api/tests/ --cov=api --cov-branch --cov-report=html

# Specific markers
pytest api/tests/ -v -m unit
pytest api/tests/ -v -m integration
pytest api/tests/ -v -m "not slow"

# Specific file
pytest api/tests/test_config.py -v

# Using make
make test
make test-cov
```

### Test Structure

```
api/tests/
├── __init__.py
├── conftest.py           # Shared fixtures
├── test_health.py        # Health endpoint tests
├── test_config.py        # Configuration CRUD tests
└── test_build.py         # Build management tests
```

### Writing Tests

#### Unit Tests

Mark with `@pytest.mark.unit`:

```python
import pytest
from httpx import AsyncClient

@pytest.mark.unit
class TestConfigValidation:
    async def test_validate_valid_config(self, client: AsyncClient, sample_yaml_config: str):
        response = await client.post(
            "/api/config/validate",
            json={"yaml_content": sample_yaml_config}
        )
        assert response.status_code == 200
        assert response.json()["valid"] is True
```

#### Integration Tests

Mark with `@pytest.mark.integration`:

```python
@pytest.mark.integration
class TestConfigCRUD:
    async def test_create_config(self, client: AsyncClient, sample_yaml_config: str):
        response = await client.post(
            "/api/config/",
            json={
                "name": "test-config",
                "description": "Test",
                "yaml_content": sample_yaml_config,
                "image_type": "fedora-bootc",
                "fedora_version": "43",
                "enable_plymouth": True
            }
        )
        assert response.status_code == 201
```

### Test Fixtures

Available in `conftest.py`:

- `test_db` - Async database session (in-memory SQLite)
- `client` - Async HTTP client for API testing
- `sample_yaml_config` - Valid YAML configuration string
- `invalid_yaml_config` - Invalid YAML for error testing
- `sample_config` - Saved configuration in database
- `sample_build` - Saved build record in database

## Project Structure

```
api/
├── main.py                    # FastAPI application
├── config.py                  # Settings and configuration
├── database.py                # SQLAlchemy models and database setup
├── models.py                  # Pydantic models for request/response
├── middleware.py              # Custom middleware stack
├── routers/
│   ├── __init__.py
│   ├── health.py             # Health check endpoints
│   ├── config.py             # Configuration management
│   └── build.py              # Build orchestration
├── services/
│   ├── __init__.py
│   ├── transpiler_service.py # YAML transpilation
│   └── github_service.py     # GitHub API integration
├── tests/
│   ├── __init__.py
│   ├── conftest.py           # Test fixtures
│   ├── test_health.py
│   ├── test_config.py
│   └── test_build.py
├── requirements.txt          # Python dependencies
└── Containerfile            # Container image definition
```

## Adding New Endpoints

### 1. Define Pydantic Models

In `api/models.py`:

```python
class MyRequest(BaseModel):
    field: str = Field(..., min_length=1)

class MyResponse(BaseModel):
    result: str
```

### 2. Create Router

In `api/routers/myrouter.py`:

```python
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models import MyRequest, MyResponse

router = APIRouter()

@router.post("/", response_model=MyResponse)
async def my_endpoint(
    request: MyRequest,
    db: AsyncSession = Depends(get_db)
):
    # Implementation
    return MyResponse(result="success")
```

### 3. Register Router

In `api/main.py`:

```python
from .routers import myrouter

app.include_router(myrouter.router, prefix="/api/myrouter", tags=["MyRouter"])
```

### 4. Write Tests

In `api/tests/test_myrouter.py`:

```python
import pytest
from httpx import AsyncClient

@pytest.mark.unit
class TestMyRouter:
    async def test_my_endpoint(self, client: AsyncClient):
        response = await client.post(
            "/api/myrouter/",
            json={"field": "value"}
        )
        assert response.status_code == 200
```

## Database Migrations

Currently using SQLAlchemy with `create_all()` for simplicity. For production, consider adding Alembic:

```bash
# Install Alembic
pip install alembic

# Initialize
alembic init alembic

# Create migration
alembic revision --autogenerate -m "Add new table"

# Apply migration
alembic upgrade head
```

## API Versioning

Currently using `/api` prefix. For versioning:

```python
# v1 routes
app.include_router(config_router, prefix="/api/v1/config", tags=["Config v1"])

# v2 routes (when needed)
app.include_router(config_v2_router, prefix="/api/v2/config", tags=["Config v2"])
```

## Error Handling Best Practices

```python
from fastapi import HTTPException

# Bad - generic error
raise HTTPException(status_code=500, detail="Error")

# Good - specific error with context
raise HTTPException(
    status_code=400,
    detail=f"Invalid configuration: {', '.join(validation_errors)}"
)

# Good - exception chaining
except ValueError as e:
    raise HTTPException(
        status_code=400,
        detail=f"Invalid input: {str(e)}"
    ) from e
```

## Logging

```python
from api.main import logger

# In route handlers
logger.info(f"Processing config: {config_id}")
logger.warning(f"Slow query detected: {query_time}ms")
logger.error(f"Failed to connect to GitHub: {str(e)}")

# With correlation ID (automatic in middleware)
# Logs will include correlation_id field
```

## Performance Considerations

### Database Queries

```python
# Bad - N+1 query
configs = await db.execute(select(ConfigModel))
for config in configs.scalars():
    builds = await db.execute(
        select(BuildModel).where(BuildModel.config_id == config.id)
    )

# Good - use joins
result = await db.execute(
    select(ConfigModel)
    .options(selectinload(ConfigModel.builds))
)
```

### Async Best Practices

```python
# Bad - blocking call
result = requests.get("https://api.github.com")

# Good - async call
async with httpx.AsyncClient() as client:
    result = await client.get("https://api.github.com")

# Good - use run_in_executor for sync libraries
loop = asyncio.get_event_loop()
result = await loop.run_in_executor(None, sync_function)
```

## Debugging

### Interactive Debugging

```python
# Add breakpoint
import pdb; pdb.set_trace()

# Or use ipdb (install: pip install ipdb)
import ipdb; ipdb.set_trace()
```

### Logging

```python
# Enable debug logging
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Database Inspection

```python
# In uvicorn shell
from api.database import engine
from sqlalchemy import inspect

inspector = inspect(engine)
print(inspector.get_table_names())
```

## CI/CD Integration

Tests run automatically in GitHub Actions:

- **Linting**: black, isort, ruff, pylint, mypy
- **Testing**: pytest with coverage
- **Coverage**: Uploaded to Codecov

See `.github/workflows/build.yaml` for configuration.

## Common Issues

### Import Errors

```bash
# Ensure you're in the project root
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
```

### Database Connection

```bash
# Check DATABASE_URL format
# SQLite: sqlite+aiosqlite:///./exousia.db
# PostgreSQL: postgresql+asyncpg://user:pass@host:5432/db
```

### Async Tests Failing

```python
# Ensure asyncio_mode is set in pyproject.toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
```

## Resources

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [SQLAlchemy 2.0](https://docs.sqlalchemy.org/en/20/)
- [Pydantic v2](https://docs.pydantic.dev/2.0/)
- [pytest Documentation](https://docs.pytest.org/)
- [Exousia API Reference](endpoints.md)
