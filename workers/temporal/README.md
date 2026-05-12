# Exousia Temporal Worker

Temporal worker for homelab automation. Runs as a Podman quadlet alongside the
Temporal server, connecting to all services on `exousia.network`.

## Workflows

### BackupWorkflow

Snapshots all Podman volumes to compressed tarballs, prunes old backups.

- Schedule: daily at 3 AM (`0 3 * * *`)
- Retention: 7 backups per volume (configurable)
- Storage: `exousia-backups` volume mounted at `/backups`

### DocSyncWorkflow

Scans multiple workspace directories, detects new documents, uploads to
Paperless-ngx with appropriate tags.

- Sources: `docs/` (exousia), `witness/`, `sap-c02/`, `scs-c03/`, `ccsp/`
- Deduplication: skips documents already in Paperless (by title)
- Tag mapping: auto-fetches tags from Paperless API

### HealthCheckWorkflow

Deep HTTP health checks for all services with response validation and
Ollama model verification.

- Schedule: every 5 minutes (`*/5 * * * *`)
- Checks: HTTP status, response time, expected body content
- Alerts: SMTP notifications for unhealthy services (via Proton Mail)

### LLMPipelineWorkflow

Multi-agent LLM orchestration across Claude, Codex, Gemini, and local Ollama.

**Strategies:**

| Strategy | Description |
|----------|-------------|
| `single` | Dispatch to one agent |
| `fan_out` | All agents answer in parallel, Claude synthesizes |
| `chain` | Each agent builds on the previous one's output |
| `debate` | Agents critique each other over multiple rounds |

**Agent routing:**

| Agent | API | Strengths |
|-------|-----|-----------|
| Claude | Anthropic | Architecture, reasoning, code review, synthesis |
| Codex | OpenAI | Code generation, implementation, refactoring |
| Gemini | Google AI | Documentation, research, analysis |
| Ollama | Local | Fast inference, privacy-sensitive tasks, drafts |

## Setup

### Build the worker image

```bash
podman build -t localhost/exousia-worker:latest workers/temporal/
```

### Configure secrets

Edit `~/.config/exousia-worker/env`:

```bash
PAPERLESS_TOKEN=<your-token>
ANTHROPIC_API_KEY=<your-key>    # for Claude
OPENAI_API_KEY=<your-key>       # for Codex
GOOGLE_API_KEY=<your-key>       # for Gemini
OLLAMA_MODEL=llama3.2:1b        # default local model
```

### Deploy

```bash
just engage temporal  # starts db, server, ui, and worker
```

### Trigger a workflow manually

```python
from temporalio.client import Client

async def main():
    client = await Client.connect("localhost:7233")

    # Run a health check
    result = await client.execute_workflow(
        "HealthCheckWorkflow",
        id="health-check-manual",
        task_queue="exousia",
    )

    # Run multi-agent pipeline
    from src.workflows.llm_pipeline import PipelineRequest, Strategy
    from src.activities.llm import Agent

    result = await client.execute_workflow(
        "LLMPipelineWorkflow",
        PipelineRequest(
            prompt="Review the exousia Caddyfile for security issues",
            strategy=Strategy.FAN_OUT,
            agents=[Agent.CLAUDE, Agent.CODEX, Agent.GEMINI],
        ),
        id="llm-review-caddyfile",
        task_queue="exousia",
    )
```

## Architecture

```text
temporal-server:7233
       |
  exousia-worker (task_queue="exousia")
       |
       +-- BackupWorkflow      -> podman volume export + zstd
       +-- DocSyncWorkflow     -> Paperless API (http://paperless:8000)
       +-- HealthCheckWorkflow -> HTTP checks to all services
       +-- LLMPipelineWorkflow -> Anthropic / OpenAI / Google / Ollama APIs
```
