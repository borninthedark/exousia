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

- **YAML Configuration Management**: Store, validate, and manage BlueBuild-compatible YAML configurations
- **Containerfile Transpilation**: Convert YAML configs to Containerfiles dynamically
- **Build Orchestration**: Trigger and monitor GitHub Actions builds
- **Health Monitoring**: Comprehensive health checks for database and external services
- **Async Operations**: Full async/await support with FastAPI and SQLAlchemy 2.0

## Technology Stack

- **Framework**: FastAPI 0.109.0
- **Database ORM**: SQLAlchemy 2.0 (async)
- **Database**: PostgreSQL (prod) / SQLite (dev)
- **Testing**: pytest + pytest-asyncio + pytest-cov
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

### Configuration Endpoints
- `POST /api/config/validate` - Validate YAML configuration
- `POST /api/config/transpile` - Transpile YAML to Containerfile
- `POST /api/config/` - Create new configuration
- `GET /api/config/` - List configurations (paginated)
- `GET /api/config/{id}` - Get specific configuration
- `PUT /api/config/{id}` - Update configuration
- `DELETE /api/config/{id}` - Delete configuration

### Build Endpoints
- `POST /api/build/trigger` - Trigger new build
- `GET /api/build/` - List builds (paginated, filterable)
- `GET /api/build/{id}/status` - Get build status with GitHub workflow info
- `POST /api/build/{id}/cancel` - Cancel running build

## Configuration

Environment variables (`.env` file):

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
GITHUB_WORKFLOW_FILE=build.yaml

# Transpiler
TRANSPILER_SCRIPT=tools/yaml-to-containerfile.py
```

## Middleware Stack

The API includes the following middleware (applied in order):

1. **GZip Compression** - Response compression for bandwidth optimization
2. **Security Headers** - X-Content-Type-Options, X-Frame-Options, etc.
3. **Correlation ID** - Request tracing across distributed systems
4. **Request Logging** - Structured JSON logs with correlation IDs
5. **Rate Limiting** - Protect against abuse (100 req/min per IP)
6. **CORS** - Cross-origin resource sharing configuration

## Database Models

### ConfigModel
Stores YAML configurations for container images.

**Fields:**
- `id` - Primary key
- `name` - Unique configuration name
- `description` - Optional description
- `yaml_content` - BlueBuild YAML configuration
- `image_type` - Base image type (fedora-bootc, fedora-sway-atomic)
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

1. **Authentication**: Currently not implemented - add OAuth2/JWT for production
2. **Rate Limiting**: Basic IP-based rate limiting included
3. **Input Validation**: Pydantic models validate all inputs
4. **SQL Injection**: Protected by SQLAlchemy ORM
5. **CORS**: Configure allowed origins in production
6. **Secrets**: Never commit tokens - use environment variables

## Further Documentation

- [API Endpoints Reference](endpoints.md) - Detailed endpoint documentation
- [Development Guide](development.md) - Contributing and development workflow
- [Testing Guide](../testing/README.md) - Test suite documentation
- [OpenAPI Docs](http://localhost:8000/docs) - Interactive API documentation (when running)

## Support

For issues, questions, or contributions:
- GitHub Issues: https://github.com/borninthedark/exousia/issues
- Main Documentation: [README.md](../../README.md)
