# Exousia API

FastAPI backend for declarative bootc image configuration management with GitHub Actions integration.

## Features

- **Authentication & Users** - JWT auth via fastapi-users with registration and user management routes
- **YAML Configuration Management** - Validate, transpile, and manage bootc configurations
- **GitHub Actions Integration** - Trigger and monitor image builds
- **Build Tracking** - Track build status and history
- **REST API** - Clean, well-documented RESTful endpoints
- **Async/Await** - High-performance async operations throughout
- **PostgreSQL Storage** - Robust data persistence with SQLAlchemy and Alembic migrations
- **Security** - Protected build/config routes with JWT, CORS support
- **Observability** - Prometheus `/metrics` endpoint plus optional OpenTelemetry tracing

## Architecture

**Direct GitHub Integration** - The API uses direct GitHub API calls for triggering builds, eliminating the need for message queue infrastructure. When you trigger a build via `/api/build/trigger`, the API:

1. Validates YAML configuration
2. Creates a build record in the database
3. Triggers GitHub Actions workflow directly via GitHub API
4. Launches a background task to poll workflow status every 30 seconds
5. Automatically updates build status when workflow completes

This simple, efficient approach is ideal for bootc image builds (low-frequency operations) and leverages GitHub's built-in rate limiting, retry semantics, and job queuing.

**Note:** The codebase includes BlazingMQ queue infrastructure (`api/queue.py`, `api/workers/`) for future scalability, but it's **not required** and **not used** by default. The direct integration works out-of-the-box with just a GitHub token.

## Tech Stack

- **FastAPI** 0.109.0 - Modern async web framework
- **fastapi-users** 12.1 - Authentication and user management
- **Python** 3.12+ - Latest Python with async/await
- **SQLAlchemy** 2.0 - Async ORM with type safety
- **Alembic** 1.13 - Database migrations
- **PostgreSQL** 16 - Primary database (SQLite fallback)
- **Pydantic** 2.5 - Data validation and settings
- **PyGithub** - GitHub API integration
- **Prometheus FastAPI Instrumentator** - Metrics endpoint
- **OpenTelemetry** - Optional OTLP tracing export
- **Podman** - Containerization (rootless, daemonless)

## Quick Start

### Local Development with Podman Compose

1. **Set environment variables:**
   ```bash
   export GITHUB_TOKEN="your_github_pat"
   ```

2. **Start services:**
   ```bash
   podman-compose up -d
   ```

3. **Access API:**
   - API: http://localhost:8000
   - Docs: http://localhost:8000/api/docs
   - Health: http://localhost:8000/api/health

4. **View logs:**
   ```bash
   podman-compose logs -f api
   ```

5. **Stop services:**
   ```bash
   podman-compose down
   ```

### Manual Setup

1. **Create virtual environment:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

2. **Install dependencies:**
   ```bash
   pip install -r api/requirements.txt
   ```

3. **Set environment variables:**
   ```bash
   export DATABASE_URL="sqlite+aiosqlite:///./exousia.db"
   export GITHUB_TOKEN="your_github_pat"
   export GITHUB_REPO="borninthedark/exousia"
   export SECRET_KEY="change-me"  # Used for JWT signing
   ```

4. **Run API:**
   ```bash
   python3 -m api.main
   # or
   uvicorn api.main:app --reload
   ```

5. **Run database migrations:**
   ```bash
   alembic -c api/alembic.ini upgrade head
   ```

6. **Create a user:**
   ```bash
   curl -X POST http://localhost:8000/api/auth/register \
     -H "Content-Type: application/json" \
     -d '{"email": "you@example.com", "password": "ChangeMe123"}'
   ```

## API Endpoints

### Health & Status

#### `GET /api/health`
Health check with service status.

**Response:**
```json
{
  "status": "healthy",
  "version": "0.1.0",
  "database": "healthy",
  "github": "healthy",
  "timestamp": "2025-11-29T12:00:00"
}
```

#### `GET /api/ping`
Simple ping for uptime monitoring.

**Response:**
```json
{
  "ping": "pong",
  "timestamp": "2025-11-29T12:00:00"
}
```

### Authentication & Users

- `POST /api/auth/register` — Register a new user
- `POST /api/auth/jwt/login` — Obtain a JWT access token
- `GET /api/users/me` — Retrieve the authenticated user profile
- `PATCH /api/users/me` — Update the authenticated user profile
- `GET /api/users/` — List users (requires appropriate privileges)

### Configuration Management

#### `POST /api/config/validate`
Validate YAML configuration.

**Request:**
```json
{
  "yaml_content": "name: exousia\n..."
}
```

**Response:**
```json
{
  "valid": true,
  "errors": null,
  "warnings": null
}
```

#### `POST /api/config/transpile`
Transpile YAML to Containerfile.

**Request:**
```json
{
  "yaml_content": "name: exousia\n...",
  "image_type": "fedora-sway-atomic",
  "fedora_version": "43",
  "enable_plymouth": true
}
```

**Response:**
```json
{
  "containerfile": "FROM quay.io/fedora/...",
  "image_type": "fedora-sway-atomic",
  "fedora_version": "43",
  "enable_plymouth": true
}
```

#### `POST /api/config/`
Create a saved configuration.

**Request:**
```json
{
  "name": "my-config",
  "description": "Production config",
  "yaml_content": "name: exousia\n...",
  "image_type": "fedora-sway-atomic",
  "fedora_version": "43",
  "enable_plymouth": true
}
```

**Response:**
```json
{
  "id": 1,
  "name": "my-config",
  "description": "Production config",
  "yaml_content": "...",
  "image_type": "fedora-sway-atomic",
  "fedora_version": "43",
  "enable_plymouth": true,
  "created_at": "2025-11-29T12:00:00",
  "updated_at": "2025-11-29T12:00:00"
}
```

#### `GET /api/config/`
List all configurations with pagination.

**Query Parameters:**
- `page`: Page number (default: 1)
- `page_size`: Items per page (default: 20, max: 100)

**Response:**
```json
{
  "configs": [...],
  "total": 5,
  "page": 1,
  "page_size": 20
}
```

#### `GET /api/config/{config_id}`
Get specific configuration.

#### `PUT /api/config/{config_id}`
Update configuration.

#### `DELETE /api/config/{config_id}`
Delete configuration.

### Build Management

#### `POST /api/build/trigger`
Trigger a new build via GitHub Actions.

**Request:**
```json
{
  "config_id": 1,
  "ref": "main"
}
```

**Or with inline YAML:**
```json
{
  "yaml_content": "name: exousia\n...",
  "image_type": "fedora-sway-atomic",
  "fedora_version": "43",
  "enable_plymouth": true,
  "ref": "main"
}
```

**Response:**
```json
{
  "id": 1,
  "config_id": 1,
  "workflow_run_id": 12345,
  "status": "in_progress",
  "image_type": "fedora-sway-atomic",
  "fedora_version": "43",
  "ref": "main",
  "started_at": "2025-11-29T12:00:00",
  "completed_at": null,
  "created_at": "2025-11-29T12:00:00"
}
```

#### `GET /api/build/{build_id}/status`
Get detailed build status with GitHub workflow info.

**Response:**
```json
{
  "build": {...},
  "workflow_status": "in_progress",
  "workflow_url": "https://github.com/.../actions/runs/12345",
  "conclusion": null,
  "logs_url": "https://github.com/.../actions/runs/12345/checks"
}
```

#### `GET /api/build/`
List builds with filtering.

**Query Parameters:**
- `page`: Page number
- `page_size`: Items per page
- `status`: Filter by status (pending, queued, in_progress, success, failure, cancelled)
- `config_id`: Filter by config ID

#### `POST /api/build/{build_id}/cancel`
Cancel a running build.

### Observability

- `GET /metrics` - Prometheus metrics endpoint (not included in OpenAPI schema)
- OpenTelemetry tracing can be enabled by setting `ENABLE_TRACING=true` and configuring `OTEL_EXPORTER_OTLP_ENDPOINT`

## Environment Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `DATABASE_URL` | Database connection string | `sqlite+aiosqlite:///./exousia.db` | No |
| `GITHUB_TOKEN` | GitHub personal access token | - | Yes* |
| `GITHUB_REPO` | Repository (owner/repo) | `borninthedark/exousia` | No |
| `GITHUB_WORKFLOW_FILE` | Workflow file name | `build.yml` | No |
| `API_HOST` | API host | `0.0.0.0` | No |
| `API_PORT` | API port | `8000` | No |
| `API_RELOAD` | Auto-reload on changes | `true` | No |
| `LOG_LEVEL` | Logging level | `INFO` | No |
| `CORS_ORIGINS` | Allowed CORS origins | `[...]` | No |
| `SECRET_KEY` | JWT signing key | - | Yes (for auth) |
| `ENABLE_TRACING` | Toggle OpenTelemetry tracing | `False` | No |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | OTLP exporter endpoint | `None` | When tracing enabled |
| `OTEL_EXPORTER_OTLP_HEADERS` | OTLP headers (comma-separated `key=value`) | `None` | When tracing enabled |

\* Required for GitHub integration

## Project Structure

```
api/
├── __init__.py           # Package init
├── main.py               # FastAPI application
├── auth.py               # fastapi-users setup and dependencies
├── config.py             # Settings & configuration
├── models.py             # Pydantic models
├── database.py           # SQLAlchemy models & DB setup
├── middleware.py         # Custom middleware
├── routers/              # API route handlers
│   ├── __init__.py
│   ├── health.py         # Health endpoints
│   ├── config.py         # Config management
│   └── build.py          # Build management
├── services/             # Business logic layer
│   ├── __init__.py
│   ├── transpiler_service.py  # YAML transpilation
│   └── github_service.py      # GitHub API client
├── migrations/           # Alembic migrations and env.py
├── requirements.txt      # Python dependencies
├── Containerfile         # Podman/Docker image
└── README.md            # This file
```

## Architecture

### Middleware & Observability

- **CORS** - Configured via `settings.CORS_ORIGINS`
- **Prometheus metrics** - `/metrics` endpoint via `prometheus-fastapi-instrumentator`
- **OpenTelemetry** - Optional tracing when `ENABLE_TRACING=true` with OTLP exporter

### Service Layer

- **TranspilerService** - Handles YAML validation and Containerfile generation
- **GitHubService** - Manages GitHub API operations (async wrapper)

### Database Layer

- **Async SQLAlchemy** - Fully async database operations
- **Models**: ConfigModel, BuildModel, BuildEventModel, User
- **Migrations**: Alembic with runtime `upgrade head` during startup

## Development

### Running Tests

```bash
pytest api/tests/ -v --cov=api
```

### Code Quality

```bash
# Format code
black api/

# Lint code
ruff check api/

# Type checking
mypy api/
```

### Database Migrations

```bash
# Create migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Rollback
alembic downgrade -1
```

## Deployment

### Build Image

```bash
podman build -t exousia-api:latest -f api/Containerfile .
```

### Run Container

```bash
podman run -d \
  -p 8000:8000 \
  -e DATABASE_URL="postgresql://..." \
  -e GITHUB_TOKEN="..." \
  --name exousia-api \
  exousia-api:latest
```

### Kubernetes

See `deploy/kubernetes/` for manifests (planned).

## Security

- **JWT Authentication** - Protected routes require a valid bearer token from `/api/auth/jwt/login`
- **CORS Configuration** - Allowed origins defined in `settings.CORS_ORIGINS`
- **CORS** - Configured allowed origins
- **Security Headers** - CSP, X-Frame-Options, X-Content-Type-Options
- **Input Validation** - Pydantic models validate all inputs
- **SQL Injection** - Prevented by SQLAlchemy ORM
- **Token Storage** - GitHub tokens in environment variables only
- **Non-root** - Container runs as unprivileged user

## Observability

### Logging

Structured JSON logs with correlation IDs:

```json
{
  "timestamp": "2025-11-29T12:00:00",
  "level": "INFO",
  "correlation_id": "abc-123",
  "method": "POST",
  "path": "/api/config/validate",
  "status_code": 200,
  "duration_ms": 45.2
}
```

### Metrics

Prometheus-compatible metrics endpoint (planned):
- Request counts and durations
- Build success/failure rates
- GitHub API call latency
- Database connection pool stats

### Health Checks

- `/api/health` - Detailed status check
- `/api/ping` - Simple uptime probe
- Container healthcheck - Built into Containerfile

## Future Enhancements

- [ ] Alembic database migrations
- [ ] Prometheus metrics endpoint
- [ ] OpenTelemetry tracing
- [ ] Authentication (fastapi-users)
- [ ] WebSocket support for real-time build updates
- [ ] Webhook receiver for GitHub Actions
- [ ] Config versioning and rollback
- [ ] Multi-tenancy support
- [ ] CLI client
- [ ] Batch operations

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests and linting
5. Submit a pull request

## License

MIT License - see LICENSE file for details

## See Also

- [Main Documentation](../README.md)
- [YAML Transpiler](../tools/README.md)
- [GitHub Actions Workflow](../.github/workflows/build.yml)
- [Witness Repository](https://github.com/borninthedark/witness) - Architectural inspiration
