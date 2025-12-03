# API Endpoints Reference

Complete reference for all Exousia API endpoints.

## Base URL

```
http://localhost:8000/api
```

---

## Health Endpoints

### GET /api/health

Comprehensive health check including database and GitHub API status.

**Response:**
```json
{
  "status": "healthy",
  "version": "0.1.0",
  "database": "healthy",
  "github": "healthy",
  "timestamp": "2025-11-29T12:00:00.000000"
}
```

**Status Values:**
- `healthy` - All systems operational
- `degraded` - Partial functionality (database issues)
- `unhealthy` - Critical failure

### GET /api/ping

Simple uptime check for monitoring.

**Response:**
```json
{
  "ping": "pong",
  "timestamp": "2025-11-29T12:00:00.000000"
}
```

---

## Configuration Endpoints

### POST /api/config/validate

Validate a YAML configuration without saving.

**Request Body:**
```json
{
  "yaml_content": "name: test-config\ndescription: Test\nmodules:\n  - type: rpm-ostree\n    install:\n      - kitty"
}
```

**Response (Success):**
```json
{
  "valid": true,
  "errors": null,
  "warnings": null
}
```

**Response (Failure):**
```json
{
  "valid": false,
  "errors": ["Missing required field: modules"],
  "warnings": []
}
```

### POST /api/config/transpile

Transpile YAML configuration to Containerfile.

**Request Body:**
```json
{
  "yaml_content": "...",
  "image_type": "fedora-bootc",
  "fedora_version": "43",
  "enable_plymouth": true
}
```

**Response:**
```json
{
  "containerfile": "FROM quay.io/fedora/fedora-bootc:43\n...",
  "image_type": "fedora-bootc",
  "fedora_version": "43",
  "enable_plymouth": true
}
```

**Errors:**
- `400` - Invalid YAML or transpilation failed

### POST /api/config/

Create a new configuration.

**Request Body:**
```json
{
  "name": "my-config",
  "description": "My custom configuration",
  "yaml_content": "...",
  "image_type": "fedora-bootc",
  "fedora_version": "43",
  "enable_plymouth": true
}
```

**Response (201 Created):**
```json
{
  "id": 1,
  "name": "my-config",
  "description": "My custom configuration",
  "yaml_content": "...",
  "image_type": "fedora-bootc",
  "fedora_version": "43",
  "enable_plymouth": true,
  "created_at": "2025-11-29T12:00:00",
  "updated_at": "2025-11-29T12:00:00"
}
```

**Errors:**
- `400` - Invalid YAML configuration
- `409` - Configuration name already exists

### GET /api/config/

List all configurations with pagination.

**Query Parameters:**
- `page` (int, default: 1) - Page number
- `page_size` (int, default: 20, max: 100) - Items per page

**Response:**
```json
{
  "configs": [
    {
      "id": 1,
      "name": "my-config",
      "description": "...",
      "image_type": "fedora-bootc",
      "fedora_version": "43",
      "enable_plymouth": true,
      "created_at": "2025-11-29T12:00:00",
      "updated_at": "2025-11-29T12:00:00"
    }
  ],
  "total": 1,
  "page": 1,
  "page_size": 20
}
```

### GET /api/config/{config_id}

Get a specific configuration by ID.

**Path Parameters:**
- `config_id` (int) - Configuration ID

**Response:**
```json
{
  "id": 1,
  "name": "my-config",
  "description": "My custom configuration",
  "yaml_content": "...",
  "image_type": "fedora-bootc",
  "fedora_version": "43",
  "enable_plymouth": true,
  "created_at": "2025-11-29T12:00:00",
  "updated_at": "2025-11-29T12:00:00"
}
```

**Errors:**
- `404` - Configuration not found

### PUT /api/config/{config_id}

Update an existing configuration.

**Path Parameters:**
- `config_id` (int) - Configuration ID

**Request Body:** (same as POST /api/config/)

**Response:**
```json
{
  "id": 1,
  "name": "updated-config",
  ...
}
```

**Errors:**
- `400` - Invalid YAML configuration
- `404` - Configuration not found

### DELETE /api/config/{config_id}

Delete a configuration.

**Path Parameters:**
- `config_id` (int) - Configuration ID

**Response:** `204 No Content`

**Errors:**
- `404` - Configuration not found

### POST /api/config/upsert

Create or update a configuration (idempotent upsert).

This endpoint provides idempotent configuration management. If a configuration with the given name exists, it will be updated. If it doesn't exist, a new configuration will be created. Multiple calls with the same data will result in the same final state.

**Request Body:**
```json
{
  "name": "my-config",
  "description": "My custom configuration",
  "yaml_content": "...",
  "image_type": "fedora-bootc",
  "fedora_version": "43",
  "enable_plymouth": true
}
```

**Response (200 OK):**
```json
{
  "id": 1,
  "name": "my-config",
  "description": "My custom configuration",
  "yaml_content": "...",
  "image_type": "fedora-bootc",
  "fedora_version": "43",
  "enable_plymouth": true,
  "created_at": "2025-11-29T12:00:00",
  "updated_at": "2025-11-29T12:00:00"
}
```

**Errors:**
- `400` - Invalid YAML configuration

**Notes:**
- This operation is idempotent - calling it multiple times with the same data produces the same result
- The configuration name is used as the unique identifier for upsert operations
- If updating, the original configuration ID is preserved
- Unlike POST /api/config/, this endpoint will not return a 409 error for duplicate names

### GET /api/config/definitions/list

List YAML definition files available in the repository.

**Response:**
```json
{
  "definitions": [
    {
      "filename": "sway-bootc.yml",
      "name": "exousia-sway-bootc",
      "description": "Custom Fedora bootc image with Sway desktop environment and custom package selection",
      "image_type": "fedora-bootc",
      "path": "yaml-definitions/sway-bootc.yml"
    }
  ],
  "total": 2
}
```

The available filenames reflect the YAML files present in the `yaml-definitions/` folder.

### GET /api/config/definitions/{filename}

Fetch the raw YAML content for a specific definition file.

**Path Parameters:**
- `filename` (string) - YAML filename (e.g., `sway-bootc.yml`)

**Response:**
```json
{
  "filename": "sway-bootc.yml",
  "content": "name: exousia-sway-bootc\n...\nimage-type: fedora-bootc"
}
```

**Errors:**
- `400` - Invalid filename (e.g., path traversal)
- `404` - Definition file not found

---

## Build Endpoints

### POST /api/build/trigger

Trigger a new build via GitHub Actions.

**Request Body (with config):**
```json
{
  "config_id": 1,
  "ref": "main"
}
```

**Request Body (with definition):**
```json
{
  "definition_filename": "sway-bootc.yml",
  "ref": "main"
}
```

**Request Body (ad-hoc):**
```json
{
  "yaml_content": "...",
  "image_type": "fedora-bootc",
  "fedora_version": "43",
  "enable_plymouth": true,
  "ref": "main"
}
```

**Response (202 Accepted):**
```json
{
  "id": 1,
  "config_id": 1,
  "workflow_run_id": 12345,
  "status": "in_progress",
  "image_type": "fedora-bootc",
  "fedora_version": "43",
  "ref": "main",
  "started_at": "2025-11-29T12:00:00",
  "created_at": "2025-11-29T12:00:00"
}
```

**Errors:**
- `400` - Invalid configuration or missing parameters
- `404` - Configuration not found
- `503` - GitHub integration not configured

### GET /api/build/

List builds with pagination and filtering.

**Query Parameters:**
- `page` (int, default: 1) - Page number
- `page_size` (int, default: 20, max: 100) - Items per page
- `status` (enum, optional) - Filter by status
  - `pending`, `in_progress`, `success`, `failure`, `cancelled`
- `config_id` (int, optional) - Filter by configuration ID

**Response:**
```json
{
  "builds": [
    {
      "id": 1,
      "config_id": 1,
      "workflow_run_id": 12345,
      "status": "success",
      "image_type": "fedora-bootc",
      "fedora_version": "43",
      "ref": "main",
      "started_at": "2025-11-29T12:00:00",
      "completed_at": "2025-11-29T12:15:00",
      "created_at": "2025-11-29T12:00:00"
    }
  ],
  "total": 1,
  "page": 1,
  "page_size": 20
}
```

### GET /api/build/{build_id}/status

Get detailed build status including GitHub workflow information.

**Path Parameters:**
- `build_id` (int) - Build ID

**Response:**
```json
{
  "build": {
    "id": 1,
    "config_id": 1,
    "workflow_run_id": 12345,
    "status": "success",
    "image_type": "fedora-bootc",
    "fedora_version": "43",
    "ref": "main",
    "started_at": "2025-11-29T12:00:00",
    "completed_at": "2025-11-29T12:15:00",
    "created_at": "2025-11-29T12:00:00"
  },
  "workflow_status": "completed",
  "workflow_url": "https://github.com/owner/repo/actions/runs/12345",
  "conclusion": "success",
  "logs_url": "https://github.com/owner/repo/actions/runs/12345/checks"
}
```

**Errors:**
- `404` - Build not found

### POST /api/build/{build_id}/cancel

Cancel a running build.

**Path Parameters:**
- `build_id` (int) - Build ID

**Response:**
```json
{
  "id": 1,
  "status": "cancelled",
  "completed_at": "2025-11-29T12:10:00",
  ...
}
```

**Errors:**
- `400` - Build cannot be cancelled (already completed)
- `404` - Build not found
- `500` - Failed to cancel GitHub workflow

---

## Data Models

### ImageType Enum
- `fedora-bootc`
- `fedora-sway-atomic`
- `linux-bootc` (deprecated alias: `bootcrew`)

### BuildStatus Enum
- `pending` - Build created, not started
- `queued` - Queued in GitHub Actions
- `in_progress` - Currently building
- `success` - Build completed successfully
- `failure` - Build failed
- `cancelled` - Build was cancelled

---

## Rate Limiting

The API implements rate limiting:
- **Limit**: 100 requests per minute per IP address
- **Response Header**: `X-RateLimit-Remaining`
- **Exceeded Response**: `429 Too Many Requests`

---

## Examples

### Complete Build Workflow

```bash
# 1. Create a configuration
curl -X POST http://localhost:8000/api/config/ \
  -H "Content-Type: application/json" \
  -d '{
    "name": "my-image",
    "description": "Custom Fedora image",
    "yaml_content": "...",
    "image_type": "fedora-bootc",
    "fedora_version": "43",
    "enable_plymouth": true
  }'

# 2. Trigger a build
curl -X POST http://localhost:8000/api/build/trigger \
  -H "Content-Type: application/json" \
  -d '{
    "config_id": 1,
    "ref": "main"
  }'

# 3. Check build status
curl http://localhost:8000/api/build/1/status

# 4. List all builds
curl http://localhost:8000/api/build/?status=success
```

### Validate and Transpile

```bash
# Validate YAML
curl -X POST http://localhost:8000/api/config/validate \
  -H "Content-Type: application/json" \
  -d '{
    "yaml_content": "name: test\ndescription: Test\nmodules:\n  - type: rpm-ostree\n    install:\n      - vim"
  }'

# Transpile to Containerfile
curl -X POST http://localhost:8000/api/config/transpile \
  -H "Content-Type: application/json" \
  -d '{
    "yaml_content": "...",
    "image_type": "fedora-bootc",
    "fedora_version": "43",
    "enable_plymouth": true
  }'
```

### Idempotent Configuration Management

```bash
# Upsert a configuration (create or update)
# First call creates, subsequent calls update
curl -X POST http://localhost:8000/api/config/upsert \
  -H "Content-Type: application/json" \
  -d '{
    "name": "production-config",
    "description": "Production configuration",
    "yaml_content": "...",
    "image_type": "fedora-bootc",
    "fedora_version": "43",
    "enable_plymouth": true
  }'

# Calling again with updated description - updates existing config
curl -X POST http://localhost:8000/api/config/upsert \
  -H "Content-Type: application/json" \
  -d '{
    "name": "production-config",
    "description": "Updated production configuration",
    "yaml_content": "...",
    "image_type": "fedora-bootc",
    "fedora_version": "43",
    "enable_plymouth": true
  }'
```
