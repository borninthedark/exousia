# Exousia API Documentation

## Overview

The Exousia API is a FastAPI-based backend service that provides YAML configuration management and Containerfile transpilation capabilities. It enables declarative container image configuration through a RESTful API interface.

## Architecture

```
┌─────────────────────────────────────────────────┐
│                  FastAPI App                     │
├─────────────────────────────────────────────────┤
│  Routers:                                        │
│  • /api/health    - Health checks               │
│  • /api/config    - YAML configuration CRUD     │
│  • /api/build     - Build management            │
├─────────────────────────────────────────────────┤
│  Services:                                       │
│  • TranspilerService   - YAML → Containerfile   │
│  • GitHubService       - GitHub Actions API     │
├─────────────────────────────────────────────────┤
│  Database:                                       │
│  • PostgreSQL (production)                      │
│  • SQLite (development)                         │
└─────────────────────────────────────────────────┘
```

## Key Features

- **Authentication & Users**: JWT auth and user management powered by fastapi-users
- **YAML Configuration Management**: Store, validate, and manage BlueBuild-compatible YAML configurations
- **Containerfile Transpilation**: Convert YAML configs to Containerfiles dynamically
- **Build Orchestration**: Trigger and monitor GitHub Actions builds
- **Health Monitoring**: Comprehensive health checks for database and external services
- **Observability**: Prometheus metrics endpoint and optional OpenTelemetry tracing
- **Async Operations**: Full async/await support with FastAPI and SQLAlchemy 2.0
- **Starter Definitions**: Browse built-in BlueBuild YAML definitions directly from the API

## Technology Stack

- **Framework**: FastAPI 0.109.0 + fastapi-users for auth
- **Database ORM**: SQLAlchemy 2.0 (async)
- **Database**: PostgreSQL (prod) / SQLite (dev)
- **Migrations**: Alembic
- **Testing**: pytest + pytest-asyncio + pytest-cov
- **Observability**: Prometheus instrumentator + OpenTelemetry (optional)
- **Code Quality**: black, ruff, isort, mypy, pylint
- **Documentation**: OpenAPI/Swagger (auto-generated)

## Quick Start

### Local Development

```bash
# Install dependencies
pip install -r api/requirements.txt

# Run with uvicorn
cd api
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Apply database migrations
cd ..
alembic -c api/alembic.ini upgrade head
```

### Using Podman Compose

```bash
# Start all services (API + PostgreSQL)
podman-compose up

# Access API at http://localhost:8000
# OpenAPI docs at http://localhost:8000/docs
```

### Running Tests

```bash
# Run all tests
pytest api/tests/ -v

# Run with coverage
pytest api/tests/ --cov=api --cov-branch --cov-report=html

# Run specific test markers
pytest api/tests/ -v -m unit
pytest api/tests/ -v -m integration
```

## API Endpoints

### Health Endpoints
- `GET /api/health` - Comprehensive health check with service status
- `GET /api/ping` - Simple uptime check

### Authentication Endpoints
- `POST /api/auth/register` - Register a new user
- `POST /api/auth/jwt/login` - Obtain JWT access token
- `GET /api/users/me` - Get the authenticated user's profile
- `PATCH /api/users/me` - Update profile details
- `GET /api/users/` - List users (privileged)

### Configuration Endpoints
- `POST /api/config/validate` - Validate YAML configuration
- `POST /api/config/transpile` - Transpile YAML to Containerfile
- `POST /api/config/` - Create new configuration
- `GET /api/config/` - List configurations (paginated)
- `GET /api/config/{id}` - Get specific configuration
- `PUT /api/config/{id}` - Update configuration
- `DELETE /api/config/{id}` - Delete configuration
- `GET /api/config/definitions/list` - List available BlueBuild YAML definitions
- `GET /api/config/definitions/{filename}` - Fetch raw YAML content for a definition

### Build Endpoints
- `POST /api/build/trigger` - Trigger new build from a saved config, starter definition, or ad-hoc YAML
- `GET /api/build/` - List builds (paginated, filterable)
- `GET /api/build/{id}/status` - Get build status with GitHub workflow info
- `POST /api/build/{id}/cancel` - Cancel running build

### Observability
- `GET /metrics` - Prometheus metrics (not included in OpenAPI docs)
- OpenTelemetry tracing can be enabled with `ENABLE_TRACING=true` and OTLP exporter variables

## Configuration

Environment variables (`.env` file):

> Tip: `.env` is gitignored and loaded automatically, so you can store `GITHUB_TOKEN` and other secrets locally without exporting
> them into every shell session.

```bash
# API Settings
API_HOST=0.0.0.0
API_PORT=8000

# Database
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/exousia
# Or for development:
DATABASE_URL=sqlite+aiosqlite:///./exousia.db

# GitHub Integration
GITHUB_TOKEN=ghp_xxxxxxxxxxxxx
GITHUB_REPO=owner/repo
GITHUB_WORKFLOW_FILE=build.yml

# Transpiler
TRANSPILER_SCRIPT=tools/yaml-to-containerfile.py

# Authentication
SECRET_KEY=change-me

# Observability
ENABLE_TRACING=false
OTEL_EXPORTER_OTLP_ENDPOINT=
OTEL_EXPORTER_OTLP_HEADERS=
```

### Build defaults and overrides

- CI uses `tools/resolve_build_config.py` to read `.fedora-version` when dispatch inputs
  request the `current` value, while explicit workflow or API dispatch inputs take
  precedence over the file contents.
- `fedora-bootc` builds accept either `window_manager` **or** `desktop_environment`
  overrides in build trigger requests; the selected value rewrites the YAML configuration
  before validation to keep the generated Containerfile aligned with the requested desktop.

## Middleware & Observability

- **CORS** - Cross-origin resource sharing configuration
- **Prometheus metrics** - `/metrics` endpoint for scraping
- **OpenTelemetry tracing** - Optional OTLP exporter controlled via environment variables

## Database Models

### ConfigModel
Stores YAML configurations for container images.

**Fields:**
- `id` - Primary key
- `name` - Unique configuration name
- `description` - Optional description
- `yaml_content` - BlueBuild YAML configuration
- `image_type` - Base image type (fedora-bootc, fedora-sway-atomic, bootcrew)
- `fedora_version` - Fedora version number
- `enable_plymouth` - Plymouth boot splash enablement
- `created_at` - Timestamp
- `updated_at` - Timestamp

### BuildModel
Tracks build jobs and GitHub Actions workflow runs.

**Fields:**
- `id` - Primary key
- `config_id` - Foreign key to ConfigModel (optional)
- `workflow_run_id` - GitHub Actions run ID
- `status` - Build status (pending, in_progress, success, failure, cancelled)
- `image_type` - Image type for this build
- `fedora_version` - Fedora version for this build
- `ref` - Git ref (branch/tag)
- `started_at` - Build start timestamp
- `completed_at` - Build completion timestamp
- `created_at` - Record creation timestamp

### BuildEventModel
Immutable event log for build state transitions.

**Fields:**
- `id` - Primary key
- `build_id` - Foreign key to BuildModel
- `event_type` - Event type (status changes, workflow triggers)
- `from_status` / `to_status` - Previous and new statuses
- `event_data` - JSON metadata for the event
- `timestamp` - Event timestamp

### User
Authentication model managed by fastapi-users.

**Fields:**
- `id` - UUID primary key
- `email` - Unique user email
- `hashed_password` - Password hash
- `is_active`, `is_superuser`, `is_verified` - User flags

## Error Handling

The API uses standard HTTP status codes:

- `200` - Success
- `201` - Created
- `204` - No Content (successful deletion)
- `400` - Bad Request (validation errors)
- `404` - Not Found
- `409` - Conflict (duplicate resource)
- `500` - Internal Server Error
- `503` - Service Unavailable (external dependency failure)

All error responses follow this format:

```json
{
  "error": "Detailed error message"
}
```

## Security Considerations

1. **Authentication**: JWT auth via fastapi-users protects configuration and build routes
2. **Input Validation**: Pydantic models validate all inputs
3. **SQL Injection**: Protected by SQLAlchemy ORM
4. **CORS**: Configure allowed origins in production
5. **Secrets**: Never commit tokens - use environment variables (e.g., `SECRET_KEY`, `GITHUB_TOKEN`)

## Further Documentation

- [API Endpoints Reference](endpoints.md) - Detailed endpoint documentation
- [Development Guide](development.md) - Contributing and development workflow
- [Testing Guide](../testing/README.md) - Test suite documentation
- [OpenAPI Docs](http://localhost:8000/docs) - Interactive API documentation (when running)

## Support

For issues, questions, or contributions:
- GitHub Issues: https://github.com/borninthedark/exousia/issues
- Main Documentation: [README.md](../../README.md)
