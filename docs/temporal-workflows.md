# Temporal Workflows

Automated operational workflows running on the `exousia` task queue.

## Active Schedules

| Schedule ID | Cron | Workflow | Description |
|---|---|---|---|
| `health-check` | `*/5 * * * *` | HealthCheckWorkflow | Deep HTTP health verification |
| `anomaly-detection` | `*/15 * * * *` | AnomalyDetectionWorkflow | Error spike detection → auto-incident |
| `ticket-sync` | `*/15 * * * *` | TicketSyncWorkflow | Paperless "actionable" → Forgejo issue |
| `pr-review` | `*/30 * * * *` | PRReviewWorkflow | Auto-review open Forgejo PRs via LLM |
| `base-image-mirror` | `0 2 * * *` | BaseImageMirrorWorkflow | Nightly Fedora base image pull |
| `daily-backup` | `0 3 * * *` | BackupWorkflow | Volume snapshots with retention pruning |
| `miniflux-digest` | `0 7 * * *` | MinifluxDigestWorkflow | Daily RSS summary via llama |
| `cve-check` | `0 8 * * *` | CVECheckWorkflow | CVE allowlist review vs upstream/Fedora |
| `container-lifecycle` | `30 9 * * *` | ContainerLifecycleWorkflow | Image updates + rolling restart + prune |
| `health-report` | `0 8 * * 0` (Sun) | HealthReportWorkflow | Weekly comprehensive health email |
| `deps-update` | `0 9 * * 3` (Wed) | DepsUpdateWorkflow | Weekly dependency update check |
| `security-scan` | `0 6 * * 1` (Mon) | SecurityScanWorkflow | Weekly Trivy scan of running images |
| `journal-knowledge` | `0 23 * * *` | JournalKnowledgeWorkflow | Daily ops insights from logs |
| `resource-audit` | `0 9 1 * *` (1st) | ResourceAuditWorkflow | Monthly resource/cost audit |
| `dr-drill` | `0 2 15 * *` (15th) | DRDrillWorkflow | Monthly DR drill (backup + verify) |

## On-Demand Workflows

| Workflow | Trigger | Description |
|---|---|---|
| IncidentResponseWorkflow | Manual / webhook | Diagnose container issue via logs + LLM |
| ChangelogWorkflow | Manual / on release | Generate release notes from commits |
| DocSyncWorkflow | Manual | Sync docs directory to Paperless |
| LLMPipelineWorkflow | Manual | Multi-agent LLM orchestration |

## Architecture

```text
┌──────────────┐     ┌─────────────────┐     ┌──────────────────┐
│  Temporal    │     │  exousia-worker │     │  Services        │
│  Server     │────►│  (Python 3.12)  │────►│                  │
│  15 schedules│     │  Task Queue:    │     │  Podman (socket) │
│  20 workflows│     │  "exousia"      │     │  Forgejo (API)   │
└──────────────┘     └─────────────────┘     │  Paperless (API) │
                                             │  Ollama (API)    │
                                             │  OpenObserve API │
                                             │  Miniflux (API)  │
                                             │  CrowdSec (API)  │
                                             └──────────────────┘
```

### Client Architecture

The worker uses HTTP API clients instead of subprocess calls:

| Client | Talks to | Via |
|---|---|---|
| `PodmanClient` | Podman REST API | Unix socket (`/var/run/podman/podman.sock`) |
| `ForgejoClient` | Forgejo REST API | HTTP (`http://forgejo:3000/api/v1`) |
| `SystemdClient` | Podman container restart API | Unix socket (same as Podman) |

Source: `workers/temporal/src/clients/`

## Registering Schedules

```bash
cd workers/temporal
source .venv/bin/activate
TEMPORAL_HOST=localhost:7233 python -m src.register_schedules
```

Idempotent — skips schedules that already exist.

## Triggering Workflows Manually

```bash
# Incident response
temporal workflow start \
  --type IncidentResponseWorkflow \
  --task-queue exousia \
  --input '{"container":"immich","trigger":"unhealthy"}'

# Changelog
temporal workflow start \
  --type ChangelogWorkflow \
  --task-queue exousia

# DR drill (on-demand)
temporal workflow start \
  --type DRDrillWorkflow \
  --task-queue exousia
```

## Workflow Details

### ContainerLifecycleWorkflow (daily 9:30 AM)

1. Check for available image updates via Podman API
2. Pull new images
3. Rolling restart in dependency order (DBs → Redis → Core → Apps → Runners)
4. Verify healthcheck after each restart
5. Rollback if unhealthy
6. Prune unused images

### CVECheckWorkflow (daily 8 AM)

1. Query GitHub releases for grpc-go fix (v1.79.3+)
2. Query Fedora Bodhi for updated podman/buildah packages
3. If fixed in Fedora: create Forgejo issue to remove allowlist
4. Delegate image scanning to CI pipeline (Lille/Hiyori)

### IncidentResponseWorkflow (on-demand)

1. Query OpenObserve for last 5 min of container logs
2. Send logs to Qwen3 (Ollama) for diagnosis
3. Parse recommended action: restart / investigate / ignore
4. Execute: restart container via Podman API, or create Forgejo issue

### AnomalyDetectionWorkflow (every 15 min)

1. Query OpenObserve for error counts per container (last 15 min)
2. Identify containers above threshold (>50 errors)
3. For each anomaly: gather logs, diagnose with LLM
4. Auto-restart or create Forgejo issue based on diagnosis

### MinifluxDigestWorkflow (daily 7 AM)

1. Fetch unread RSS entries from Miniflux API
2. Summarize with llama3.2 via Ollama
3. Mark entries as read

### PRReviewWorkflow (every 30 min)

1. Get open PRs from Forgejo API
2. Fetch diff for each PR
3. Review with llama3.2 via Ollama
4. Post review comment on PR

### SecurityScanWorkflow (weekly Monday 6 AM)

1. List all running container images via Podman API
2. Create Forgejo issue if critical findings
3. Send email alert for critical CVEs

### DepsUpdateWorkflow (weekly Wednesday 9 AM)

1. Run `pip list --outdated` inside the worker container
2. Create Forgejo issue with update table

### ChangelogWorkflow (on-demand)

1. Get latest tag via Forgejo API
2. Get commits since tag via Forgejo API
3. Generate changelog with llama3.2 via Ollama

### JournalKnowledgeWorkflow (daily 11 PM)

1. Query OpenObserve for today's important logs (priority ≤ 4)
2. Extract key events, patterns, and action items with LLM
3. Generate daily ops report

### HealthReportWorkflow (weekly Sunday 8 AM)

1. Run health checks on all services
2. Get 7-day error rates from OpenObserve
3. Get container inventory
4. Send email + create Forgejo issue

### ResourceAuditWorkflow (monthly 1st 9 AM)

1. Get container inventory and pending updates
2. Get 30-day error volumes
3. Identify quiet containers (decommission candidates)
4. Identify noisy containers (investigation candidates)
5. Send email + create Forgejo issue with recommendations

### DRDrillWorkflow (monthly 15th 2 AM)

1. Pre-drill health check
2. Backup all volumes (zstd compressed via Python zstandard)
3. Verify backup integrity (non-zero size)
4. Post-drill health check (verify nothing degraded)
5. Prune old backups (keep 7)
6. Send email + create Forgejo issue

### BackupWorkflow (daily 3 AM)

1. List all podman volumes via API
2. Export each to compressed tarball (zstandard)
3. Store in `/backups/` with timestamp
4. Prune backups older than retention count (default: 7)

### TicketSyncWorkflow (every 15 min)

1. Fetch Paperless docs tagged "actionable"
2. Create Forgejo issue for each (with doc link)
3. Re-tag doc as "in-progress"
4. Check for closed Forgejo issues referencing Paperless docs
5. Re-tag completed docs from "in-progress" to "completed"

### BaseImageMirrorWorkflow (daily 2 AM)

1. Pull latest `fedora-sway-atomic:44` via Podman API
2. Tag and push to local registry (`localhost:5000`)

## Configuration

### Worker env vars (`~/.config/exousia-worker/env`)

| Variable | Default | Used by |
|---|---|---|
| `TEMPORAL_HOST` | `temporal-server:7233` | Worker connection |
| `OLLAMA_URL` | `http://ollama:11434` | Incident, Digest, PR Review, Changelog, Journal |
| `OLLAMA_MODEL` | `llama3.2:1b` | Default model for LLM calls |
| `ZO_ROOT_USER_EMAIL` | — | OpenObserve queries |
| `ZO_ROOT_USER_PASSWORD` | — | OpenObserve queries |
| `PAPERLESS_API_URL` | `http://paperless:8000/api` | TicketSync, DocSync |
| `PAPERLESS_TOKEN` | — | TicketSync, DocSync |
| `MINIFLUX_API_KEY` | — | MinifluxDigest |
| `SMTP_PASSWORD` | — | Email alerts |
| `GOOGLE_API_KEY` | — | Gemini LLM dispatch |
| `ANTHROPIC_API_KEY` | — | Claude LLM dispatch |
| `OPENAI_API_KEY` | — | Codex/GPT LLM dispatch |
| `FORGEJO_TOKEN` | — | Forgejo API (issues, PRs, commits) |

### Available LLM models

| Model | Location | Best for |
|---|---|---|
| `llama3.2:1b` | Ollama (local) | Fast tasks: digests, quick reviews |
| `qwen3:8b` | Ollama (local) | Reasoning: diagnosis, planning |
| `qwen2.5-coder:1.5b` | Ollama (local) | Code generation/review |
| Claude | Anthropic API | Complex reasoning |
| Gemini | Google AI API | Research, analysis |
| GPT-4o | OpenAI API | Code generation |

## Tests

```bash
cd workers/temporal
source .venv/bin/activate
python -m pytest tests/ -v
```

73 tests covering clients, activities, and workflow definitions.

## Monitoring

View schedules and workflow history at:
`https://temporal.exousia.local` → Schedules tab
