# Shinigami Pipeline

GitHub Actions CI/CD workflows named after Gotei 13 captains from BLEACH.

## Workflows

| Captain | File | Division | Role |
|---------|------|----------|------|
| **Aizen** | `aizen.yml` | 5th (Sacrifice) | Orchestrator: calls Kaname + Gin in parallel, then Kyoraku, then gate |
| **Kaname** | `kaname.yml` | 9th (Oblivion) | CI: Ruff, Black, isort, pytest |
| **Gin** | `gin.yml` | 3rd (Despair) | Security: Hadolint, Checkov, Trivy config scan, Bandit |
| **Kyoraku** | `kyoraku.yml` | 1st (Truth and Innocence) | Docker Buildx, Cosign, Trivy image scan, semver release |
| **Yoruichi** | `yoruichi.yml` | 2nd (Seek Nothing) | Post-CI: generates STATUS.md, updates README badges |

## Pipeline Flow

```text
Aizen -> Kaname + Gin (parallel) -> Kyoraku -> Gate
                                                |
Yoruichi (on Aizen completion, main only) <-----+
```

## Triggers

- **Aizen**: push/PR to main, 8-hour schedule, manual dispatch
- **Yoruichi**: `workflow_run` after Aizen completes on main
