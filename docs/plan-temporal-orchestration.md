# Temporal Agent Orchestration Plan

## Goal

Use [Temporal](https://temporal.io) as the durable workflow engine to coordinate
four LLM agents (Claude, Gemini, Codex, Qwen3) for automated software engineering
tasks. Plane remains the human-facing project management layer; Temporal handles
machine-to-machine execution.

## Architecture

```text
┌─────────────────────────────────────────────────────────┐
│                    exousia.network                       │
│                                                         │
│  ┌──────────┐  ┌──────────────┐  ┌───────────────────┐  │
│  │ Plane    │  │ Temporal     │  │ Temporal UI       │  │
│  │ :8080    │  │ Server :7233 │  │ :8233             │  │
│  └────┬─────┘  └──────┬───────┘  └───────────────────┘  │
│       │               │                                  │
│       │         ┌─────┴──────┐                           │
│       │         │ temporal-db│                           │
│       │         │ (postgres) │                           │
│       │         └────────────┘                           │
│       │                                                  │
│  ┌────┴─────┐  ┌─────────────┐  ┌──────────────────┐   │
│  │ Forgejo  │  │ Ollama      │  │ Registry         │   │
│  │ :3000    │  │ :11434      │  │ :5000            │   │
│  └──────────┘  └─────────────┘  └──────────────────┘   │
└─────────────────────────────────────────────────────────┘

        ┌──────────────────────────────┐
        │      Temporal Workers        │
        │  (Python, host-level)        │
        │                              │
        │  ┌────────┐ ┌────────────┐   │
        │  │Activity│ │Activity    │   │
        │  │Qwen3   │ │Claude CLI  │   │
        │  │(HTTP)  │ │(subprocess)│   │
        │  └────────┘ └────────────┘   │
        │  ┌────────┐ ┌────────────┐   │
        │  │Activity│ │Activity    │   │
        │  │Gemini  │ │Codex CLI   │   │
        │  │(API)   │ │(subprocess)│   │
        │  └────────┘ └────────────┘   │
        │  ┌─────────────────────┐     │
        │  │Activity: Forgejo API│     │
        │  │Activity: Plane API  │     │
        │  └─────────────────────┘     │
        └──────────────────────────────┘
```

## Components

### Infrastructure (Quadlets)

| Service | Image | Port | Purpose |
|---------|-------|------|---------|
| `temporal-db` | `postgres:15-alpine` | internal | Temporal persistence (workflow history, visibility) |
| `temporal-server` | `temporalio/auto-setup:latest` | 7233 | Workflow engine with automatic DB schema setup |
| `temporal-ui` | `temporalio/ui:latest` | 8233 | Web dashboard for workflow visibility |

All three join `exousia.network`. The auto-setup image handles schema creation
and migrations on first boot — no manual DB init required.

### Workers (Host-level Python)

Workers are long-running Python processes that poll Temporal for tasks. They run
on the host (not in containers) because they need access to:

- Claude Code CLI (`claude`)
- Gemini CLI (`gemini`)
- Codex CLI (`codex`)
- Ollama API (`http://localhost:11434`)
- Forgejo API (`http://localhost:3000`)
- Plane API (`http://localhost:8080`)
- Git repos on the filesystem

Workers use `temporalio` Python SDK (`uv add temporalio`).

### Workflow Design

#### 1. Code Review Workflow

Triggered by: Forgejo webhook on PR creation, or Plane task assignment.

```text
PR opened
  └─> Qwen3 triage (fast, local)
        ├─ trivial → auto-approve comment
        └─ non-trivial → Claude deep review
              └─> post review to Forgejo
```

#### 2. Task Execution Workflow

Triggered by: Plane task moved to "In Progress", or manual signal.

```text
Task claimed
  └─> Parse task requirements (Qwen3)
        └─> Route to best agent:
              ├─ Generator internals → Claude
              ├─ YAML / workflow files → Gemini
              ├─ Docs / blueprints → Codex
              └─> Agent executes, commits, opens PR
                    └─> Cross-review by a different agent
                          └─> Update Plane task status
```

#### 3. Build Validation Workflow

Triggered by: Push to any feature branch.

```text
Push event
  └─> Parallel:
        ├─ Qwen3: lint check (fast)
        ├─ Qwen3: test relevance triage
        └─> If tests needed:
              └─> Claude: run full test suite, analyze failures
                    └─> If failures: create fix PR
                    └─> If pass: comment on original PR
```

#### 4. Continuous Improvement Workflow (child workflows)

Scheduled: daily or on-demand.

```text
Scan codebase
  └─> Qwen3: identify stale TODOs, dead code, missing tests
        └─> For each finding, spawn child workflow:
              └─> Appropriate agent creates fix PR
                    └─> Another agent reviews
```

## Agent Activity Contracts

Each agent is wrapped as a Temporal activity with consistent interfaces:

```python
@activity.defn
async def qwen3_activity(prompt: str, context: dict) -> AgentResult:
    """Local inference via Ollama HTTP API. Fast, no rate limits."""

@activity.defn
async def claude_activity(prompt: str, context: dict) -> AgentResult:
    """Claude Code CLI invocation. Deep reasoning, code generation."""

@activity.defn
async def gemini_activity(prompt: str, context: dict) -> AgentResult:
    """Gemini CLI invocation. YAML, config, workflow tasks."""

@activity.defn
async def codex_activity(prompt: str, context: dict) -> AgentResult:
    """Codex CLI invocation. Docs, blueprints, package mappings."""

@activity.defn
async def forgejo_activity(action: str, params: dict) -> dict:
    """Forgejo REST API calls (create PR, comment, merge)."""

@activity.defn
async def plane_activity(action: str, params: dict) -> dict:
    """Plane REST API calls (update task status, create issue)."""
```

## Integration Points

### Forgejo -> Temporal

Forgejo webhooks POST to a lightweight receiver (FastAPI or Flask) running on the
host. The receiver starts Temporal workflows based on event type:

| Forgejo Event | Temporal Workflow |
|---------------|-------------------|
| `pull_request.opened` | Code Review |
| `push` (feature branch) | Build Validation |
| `issue.labeled` (`agent-task`) | Task Execution |

### Plane -> Temporal

Plane webhook (or polling) triggers Task Execution workflows when tasks move to
"In Progress" with an agent label.

### Temporal -> Forgejo/Plane

Activities post results back:

- Forgejo: PR comments, reviews, new PRs
- Plane: task status updates, time tracking

## Phased Rollout

### Phase T.0: Infrastructure (current)

Deploy Temporal server, DB, and UI as quadlets on `exousia.network`.

### Phase T.1: Worker Skeleton

- Python project under `tools/temporal/`
- Temporal SDK dependency (`temporalio`)
- Basic worker that connects to Temporal server
- Agent activity stubs (Qwen3 only — simplest to test locally)

### Phase T.2: First Workflow

- Code Review workflow with Qwen3 triage
- Manual trigger via Temporal UI or `tctl`
- Validate end-to-end: trigger -> Qwen3 inference -> Forgejo comment

### Phase T.3: Multi-Agent Routing

- Add Claude, Gemini, Codex activities
- Task routing logic based on task type/labels
- Cross-agent review (agent A writes, agent B reviews)

### Phase T.4: Webhook Integration

- FastAPI webhook receiver for Forgejo events
- Plane polling or webhook receiver
- Automatic workflow triggering on PR/push/task events

### Phase T.5: Scheduled Workflows

- Daily codebase scan (stale TODOs, dead code, missing tests)
- Automated fix PRs with cross-agent review

## Container Image Policy

The local machine's `/etc/containers/policy.json` must allow `docker.io/temporalio`.
The build image's policy (`overlays/base/configs/containers/policy.json`) already
allows all of `docker.io` — no change needed there.

## Ports Summary

| Service | Host Port | Network Alias |
|---------|-----------|---------------|
| Temporal Server (gRPC) | 7233 | `temporal:7233` |
| Temporal UI | 8233 | `temporal-ui:8233` |
| Temporal DB | internal only | `temporal-db:5432` |
