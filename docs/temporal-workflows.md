# Temporal Workflows

Automated operational workflows running on the `exousia` task queue.

## Active Schedules

| Schedule ID | Cron | Workflow | Description |
|---|---|---|---|
| `container-lifecycle` | `30 9 * * *` (Daily 9:30 AM) | ContainerLifecycleWorkflow | Image updates + rolling restart with rollback |
| `cve-check` | `0 8 * * *` (Daily 8 AM) | CVECheckWorkflow | Check if allowlisted CVEs are fixed upstream |
| `ticket-sync` | `*/15 * * * *` | TicketSyncWorkflow | Paperless "actionable" → Forgejo issue sync |
| `health-check` | `*/5 * * * *` | HealthCheckWorkflow | Deep HTTP health verification of all services |
| `daily-backup` | `0 3 * * *` (Daily 3 AM) | BackupWorkflow | Volume snapshots with retention pruning |

## On-Demand Workflows

| Workflow | Trigger | Description |
|---|---|---|
| IncidentResponseWorkflow | Manual / webhook | Diagnose container issue via logs + LLM |
| DocSyncWorkflow | Manual | Sync docs directory to Paperless |
| LLMPipelineWorkflow | Manual | Run LLM tasks via Ollama |

## Architecture

```text
┌──────────────┐     ┌─────────────────┐     ┌──────────────┐
│  Temporal    │     │  exousia-worker │     │  Services    │
│  Server     │────►│  (Python)       │────►│              │
│  Schedules  │     │  Task Queue:    │     │  - Podman    │
│  History    │     │  "exousia"      │     │  - Forgejo   │
└──────────────┘     └─────────────────┘     │  - Paperless │
                                             │  - Ollama    │
                                             │  - OpenObserve│
                                             └──────────────┘
```

## Registering Schedules

```bash
cd workers/temporal
source .venv/bin/activate
TEMPORAL_HOST=localhost:7233 python -m src.register_schedules
```

Idempotent — skips schedules that already exist.

## Triggering Incident Response Manually

```bash
temporal workflow start \
  --type IncidentResponseWorkflow \
  --task-queue exousia \
  --input '{"container":"immich","trigger":"unhealthy"}'
```

## Workflow Details

### ContainerLifecycleWorkflow

1. `podman auto-update --dry-run` to find available updates
1. Pull new images
1. Rolling restart in dependency order (DBs → Redis → Core → Apps → Runners)
1. Verify healthcheck after each restart
1. Rollback if unhealthy

### CVECheckWorkflow

1. Query GitHub releases for grpc-go fix (v1.79.3+)
1. Query Fedora Bodhi for updated podman/buildah packages
1. If fixed in Fedora: create Forgejo issue to remove allowlist
1. Run Trivy scan for new critical CVEs not in allowlist

### IncidentResponseWorkflow

1. Query OpenObserve for last 5 min of container logs
1. Send logs to Qwen3 (Ollama) for diagnosis
1. Parse recommended action: restart / investigate / ignore
1. Execute: restart service, or create Forgejo issue for investigation

### TicketSyncWorkflow

1. Fetch Paperless docs tagged "actionable"
1. Create Forgejo issue for each (with doc link)
1. Re-tag doc as "in-progress"
1. Check for closed Forgejo issues referencing Paperless docs
1. Re-tag completed docs from "in-progress" to "completed"

### BackupWorkflow

1. List all podman volumes
1. Export each to compressed tarball (zstd)
1. Store in `/backups/` with timestamp
1. Prune backups older than retention count (default: 7)

## Configuration

Worker env vars (set in exousia-worker container):

| Variable | Default | Used by |
|---|---|---|
| `TEMPORAL_HOST` | `temporal-server:7233` | Worker connection |
| `OLLAMA_URL` | `http://ollama:11434` | IncidentResponse, LLMPipeline |
| `OLLAMA_MODEL` | `qwen3:8b` | IncidentResponse |
| `ZO_ROOT_USER_EMAIL` | — | IncidentResponse (OpenObserve) |
| `ZO_ROOT_USER_PASSWORD` | — | IncidentResponse (OpenObserve) |
| `PAPERLESS_API_URL` | `http://paperless:8000/api` | TicketSync, DocSync |
| `PAPERLESS_TOKEN` | — | TicketSync, DocSync |

## Monitoring

View schedules and workflow history at:
`https://temporal.exousia.local` → Schedules tab
