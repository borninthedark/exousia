# Exousia API

FastAPI backend for declarative bootc image configuration management with GitHub Actions integration.

## Features

- **YAML Configuration Management** - Validate, transpile, and manage bootc configurations
- **GitHub Actions Integration** - Trigger and monitor image builds
- **Build Tracking** - Track build status and history
- **REST API** - Clean, well-documented RESTful endpoints
- **Async/Await** - High-performance async operations throughout
- **PostgreSQL Storage** - Robust data persistence with SQLAlchemy
- **Security** - Rate limiting, CORS, security headers, correlation IDs
- **Observability** - Structured logging, health checks, metrics-ready

## Tech Stack

- **FastAPI** 0.109.0 - Modern async web framework
- **Python** 3.12+ - Latest Python with async/await
- **SQLAlchemy** 2.0 - Async ORM with type safety
- **PostgreSQL** 16 - Primary database (SQLite fallback)
- **Pydantic** 2.5 - Data validation and settings
- **PyGithub** - GitHub API integration
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
   ```

4. **Run API:**
   ```bash
   python3 -m api.main
   # or
   uvicorn api.main:app --reload
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

## Environment Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `DATABASE_URL` | Database connection string | `sqlite+aiosqlite:///./exousia.db` | No |
| `GITHUB_TOKEN` | GitHub personal access token | - | Yes* |
| `GITHUB_REPO` | Repository (owner/repo) | `borninthedark/exousia` | No |
| `GITHUB_WORKFLOW_FILE` | Workflow file name | `build.yaml` | No |
| `API_HOST` | API host | `0.0.0.0` | No |
| `API_PORT` | API port | `8000` | No |
| `API_RELOAD` | Auto-reload on changes | `true` | No |
| `LOG_LEVEL` | Logging level | `INFO` | No |
| `CORS_ORIGINS` | Allowed CORS origins | `[...]` | No |
| `SECRET_KEY` | JWT secret key | - | No** |

\* Required for GitHub integration
\** Required for authentication features (future)

## Project Structure

```
api/
├── __init__.py           # Package init
├── main.py               # FastAPI application
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
├── requirements.txt      # Python dependencies
├── Containerfile         # Podman/Docker image
└── README.md            # This file
```

## Architecture

### Middleware Stack (Outer → Inner)

1. **GZipMiddleware** - Response compression
2. **SecurityHeadersMiddleware** - Security headers (CSP, X-Frame-Options, etc.)
3. **CorrelationIDMiddleware** - Request correlation IDs for tracing
4. **RequestLoggingMiddleware** - Structured request/response logging
5. **Rate Limiting** - Per-IP rate limits (200/minute default)
6. **CORS** - Cross-origin resource sharing

### Service Layer

- **TranspilerService** - Handles YAML validation and Containerfile generation
- **GitHubService** - Manages GitHub API operations (async wrapper)

### Database Layer

- **Async SQLAlchemy** - Fully async database operations
- **Models**: ConfigModel, BuildModel
- **Migrations**: Alembic (planned)

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

- **Rate Limiting** - 200 requests/minute per IP
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
- [GitHub Actions Workflow](../.github/workflows/build.yaml)
- [Witness Repository](https://github.com/borninthedark/witness) - Architectural inspiration
