# Vikunja Project Management

Task and project management integrated with Temporal workflows.

## Architecture

```text
┌──────────────────┐     ┌─────────────────┐     ┌──────────────┐
│  Temporal        │     │  Vikunja        │     │  User        │
│  Workflows       │────►│  REST API       │────►│  Kanban UI   │
│                  │     │  :3456          │     │  tasks.*     │
│  Incident ──────►│     └─────────────────┘     └──────────────┘
│  CVE Check ────►│
│  Deps Update ──►│
│  Security Scan ─►│
└──────────────────┘
```

## Projects

| ID | Project | Purpose |
|---|---|---|
| 2 | Exousia Next Phase | Roadmap — manually prioritized tasks |
| 3 | Exousia Operations | Auto-populated by Temporal workflows |

## Access

- URL: `https://tasks.exousia.local`
- Auth: Authelia (forward-auth)
- User: `uryu`

## Quadlet Files

- `overlays/deploy/vikunja.container` — Vikunja app
- `overlays/deploy/vikunja-db.container` — PostgreSQL 15-alpine

## Secrets

```text
~/.config/vikunja/vikunja.env      (mode 600) — DB connection, public URL
~/.config/vikunja/vikunja-db.env   (mode 600) — Postgres credentials
~/.config/exousia-worker/env      — VIKUNJA_API_URL, VIKUNJA_API_TOKEN
```

## Temporal Integration

### Client

`src/clients/vikunja.py` — full REST API client:
- `create_project(title)` / `list_projects()`
- `create_task(project_id, title, description, priority)`
- `update_task(task_id, **kwargs)` / `complete_task(task_id)`
- `add_comment(task_id, comment)`
- `search_tasks(query)` — deduplication before creating

### Activities

`src/activities/vikunja.py` — Temporal activity wrappers:
- `create_task` — create in any project
- `create_ops_task` — create in Operations project (with deduplication)
- `complete_task` — mark done
- `add_task_comment` — append workflow results
- `update_task_status` — change priority, description, done state
- `list_project_tasks` / `search_tasks`

### Workflows That Create Vikunja Tasks

| Workflow | When | Priority |
|---|---|---|
| IncidentResponseWorkflow | Restart failed or investigation needed | 4 (high) |
| CVECheckWorkflow | Allowlisted CVEs are removable | 4 (high) |
| DepsUpdateWorkflow | Outdated dependencies found | 2 (low) |

All tasks are created in the **Exousia Operations** project (ID 3).
Deduplication: if an open task with the same title exists, it's skipped.

### Environment Variables

| Variable | Value | Used by |
|---|---|---|
| `VIKUNJA_API_URL` | `http://vikunja:3456` | VikunjaClient |
| `VIKUNJA_API_TOKEN` | API token (from Settings) | VikunjaClient |

### Project Constants

Defined in `src/activities/vikunja.py`:

```python
OPS_PROJECT_ID = 3      # Auto-generated ops tasks
ROADMAP_PROJECT_ID = 2  # Manual roadmap tasks
```

## API Examples

```bash
# List projects
curl -s -H "Authorization: Bearer $VIKUNJA_TOKEN" \
  http://localhost:3456/api/v1/projects

# List tasks in a project
curl -s -H "Authorization: Bearer $VIKUNJA_TOKEN" \
  http://localhost:3456/api/v1/projects/3/tasks

# Create a task
curl -s -X PUT -H "Authorization: Bearer $VIKUNJA_TOKEN" \
  -H "Content-Type: application/json" \
  http://localhost:3456/api/v1/projects/3/tasks \
  -d '{"title":"Fix the thing","priority":3}'

# Complete a task
curl -s -X POST -H "Authorization: Bearer $VIKUNJA_TOKEN" \
  -H "Content-Type: application/json" \
  http://localhost:3456/api/v1/tasks/42 \
  -d '{"done":true}'
```

## Caddy Route

```caddyfile
tasks.exousia.local {
    tls internal
    import authelia
    reverse_proxy vikunja:3456
}
```
