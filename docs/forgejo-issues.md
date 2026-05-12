# Forgejo Issues

Project management for Exousia uses Forgejo Issues on the local Forgejo
instance at `https://forgejo.exousia.local`. This keeps issue tracking,
code hosting, and CI/CD in a single self-hosted platform with no external
dependencies.

## Access

- **Web UI:** `https://forgejo.exousia.local`
- **API:** `https://forgejo.exousia.local/api/v1`
- **API docs:** `https://forgejo.exousia.local/api/swagger`

Authentication uses a Forgejo API token. Create one at
**User Settings > Applications** with `read:issue` + `write:issue` scopes.

## Labels

Issues are classified on two axes:

### Type

| Label | Color | Description |
|-------|-------|-------------|
| `bug` | red | Something is broken |
| `feature` | green | New functionality |
| `docs` | blue | Documentation only |
| `ci` | purple | Pipeline / workflow changes |
| `refactor` | orange | Code improvement, no behavior change |
| `task` | gray | Operational / maintenance work |

### Priority

| Label | Color | Description |
|-------|-------|-------------|
| `critical` | dark red | Service down, data loss risk |
| `high` | red | Blocks other work |
| `medium` | yellow | Normal priority |
| `low` | green | Nice to have |

### Component

| Label | Description |
|-------|-------------|
| `pipeline` | CI/CD workflows (GitHub Actions, Forgejo Actions) |
| `quadlets` | Podman Quadlet services |
| `generator` | Package loader / build system |
| `image` | Container image / bootc |
| `infra` | Infrastructure (DNS, Caddy, registry) |

## Milestones

| Milestone | Scope |
|-----------|-------|
| `M.1 — Core Stabilization` | Test coverage, pipeline reliability, existing bugs |
| `M.2 — Security Hardening` | Sealed boot, CVE remediation, policy enforcement |
| `M.9 — AI Integration` | MCP server, auto-triage, agent workflows |

## Issue Templates

Templates live in `.forgejo/issue_template/` and auto-populate the new
issue form:

| Template | File | Fields |
|----------|------|--------|
| Bug Report | `bug.yml` | Steps to reproduce, expected/actual behavior, component |
| Feature Request | `feature.yml` | Motivation, proposed solution, alternatives considered |
| Task | `task.yml` | Description, acceptance criteria, component |

## Agent Integration

Coding agents (Claude, Gemini, Codex) interact with Forgejo Issues during
development sessions. The planned integration path (see `AI_INTEGRATION_PLAN.md`):

1. **MCP Server** — custom Forgejo MCP server exposes `list_issues`,
   `get_issue`, `create_issue`, `update_issue`, `add_comment`, `search_issues`
2. **Auto-Triage** — webhook-driven classification via Ollama
3. **Enrichment** — related code, similar issues, suggested fixes
4. **Autonomous Resolution** — agent-driven fix attempts for `auto-fixable` issues

## Workflow

1. **Create** — file an issue via the web UI or API with appropriate type/priority labels
2. **Triage** — assign milestone, component label, and owner
3. **Branch** — work on `uryu/<issue-slug>` branch, reference `#<id>` in commits
4. **Resolve** — PR merges close the issue via `Closes #<id>` in the commit message
5. **Verify** — CI pipeline validates the fix before merge

## API Examples

```bash
# List open issues
curl -s -H "Authorization: token $FORGEJO_TOKEN" \
  https://forgejo.exousia.local/api/v1/repos/borninthedark/exousia/issues

# Create an issue
curl -s -X POST -H "Authorization: token $FORGEJO_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"title": "Fix flaky test", "body": "Details...", "labels": [1,3]}' \
  https://forgejo.exousia.local/api/v1/repos/borninthedark/exousia/issues

# Add a comment
curl -s -X POST -H "Authorization: token $FORGEJO_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"body": "Fixed in commit abc123"}' \
  https://forgejo.exousia.local/api/v1/repos/borninthedark/exousia/issues/1/comments
```

---

**[Back to Documentation Index](README.md)** | **[Back to Main README](../README.md)**
