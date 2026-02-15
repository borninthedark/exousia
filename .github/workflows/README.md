# Shinigami Pipeline

GitHub Actions CI/CD workflows named after Gotei 13 captains from BLEACH.

## Workflows

| Captain | File | Division | Role |
|---------|------|----------|------|
| **Aizen** | `aizen.yml` | -- | Orchestrator: calls Mayuri + Byakuya in parallel, then Kyoraku, then gate |
| **Mayuri** | `mayuri.yml` | 12th (R&D) | CI: Ruff, Black, isort, pytest |
| **Byakuya** | `byakuya.yml` | 6th (Law) | Security: Hadolint, Checkov, Trivy config scan, Bandit |
| **Kyoraku** | `kyoraku.yml` | Captain-Commander | Docker Buildx, Cosign, Trivy image scan, semver release |
| **Yoruichi** | `yoruichi.yml` | 2nd (Stealth) | Post-CI: generates STATUS.md, updates README badges |

## Pipeline Flow

```text
Aizen -> Mayuri + Byakuya (parallel) -> Kyoraku -> Gate
                                                    |
Yoruichi (on Aizen completion, main only) <---------+
```

## Triggers

- **Aizen**: push/PR to main, 6-hour schedule, manual dispatch
- **Yoruichi**: `workflow_run` after Aizen completes on main

## See Also

- [Espada Pipeline](../../.forgejo/workflows/) -- Forgejo mirror
