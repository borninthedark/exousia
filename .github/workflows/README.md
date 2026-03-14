# Shinigami Pipeline

GitHub Actions CI/CD workflows named after Gotei 13 captains from BLEACH.

## Workflows

| Captain | File | Division | Role |
|---------|------|----------|------|
| **Aizen** | `aizen.yml` | 5th (Sacrifice) | Orchestrator: calls Kaname + Gin in parallel, then Kyoraku, then gate |
| **Kaname** | `kaname.yml` | 9th (Oblivion) | CI: Ruff, Black, isort, pytest |
| **Gin** | `gin.yml` | 3rd (Despair) | Security: Hadolint, Checkov, Trivy config scan, Bandit |
| **Kyoraku** | `kyoraku.yml` | 1st (Truth and Innocence) | Buildah, Cosign, Trivy image scan, semver release |
| **Yoruichi** | `yoruichi.yml` | 2nd (Seek Nothing) | Post-CI: generates STATUS.md, updates README badges |
| **Mayuri** | `mayuri.yml` | 12th (R&D) | Dotfiles watcher: polls `borninthedark/dotfiles`, triggers Aizen on change |

## Pipeline Flow

```text
Aizen -> Kaname + Gin (parallel) -> Kyoraku -> Gate
                                                |
Yoruichi (on Aizen completion, main only) <-----+

Mayuri (scheduled, independent) -> triggers Aizen if dotfiles changed
```

## Triggers

- **Aizen**: push/PR to main, scheduled at 00:10 / 08:10 / 16:10 UTC, manual dispatch
- **Mayuri**: scheduled at 04:10 / 12:10 / 20:10 UTC (midpoint between Aizen runs), manual dispatch
- **Yoruichi**: `workflow_run` after Aizen completes on main
