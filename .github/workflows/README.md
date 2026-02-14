# Shinigami Pipeline

GitHub Actions CI/CD workflows named after Gotei 13 captains from BLEACH.

## Workflows

| Captain | File | Division | Role |
|---------|------|----------|------|
| **Aizen** | `aizen.yml` | -- | Orchestrator: calls Mayuri + Byakuya in parallel, then Kyoraku, then gate |
| **Mayuri** | `mayuri.yml` | 12th (R&D) | CI: Ruff, Black, isort, pytest |
| **Byakuya** | `byakuya.yml` | 6th (Law) | Security: Hadolint, Checkov, Trivy config scan, Bandit |
| **Kyoraku** | `kyoraku.yml` | Captain-Commander | Build, Cosign, Trivy image scan, semver release |
| **Unohana** | `unohana.yml` | 4th (Relief) | Weekly ZFS build: mirrors Aizen with `enable_zfs: true` |
| **Yoruichi** | `yoruichi.yml` | 2nd (Stealth) | Post-CI: generates STATUS.md, updates README badges |

## Pipeline Flow

```text
Aizen -> Mayuri + Byakuya (parallel) -> Kyoraku -> Gate
                                                    |
Yoruichi (on Aizen completion, main only) <---------+

Unohana (weekly) -> Mayuri + Byakuya (parallel) -> Kyoraku (ZFS) -> Gate
```

## Triggers

- **Aizen**: push/PR to main, 8-hour schedule, manual dispatch
- **Unohana**: weekly schedule (Sunday 04:10 UTC), manual dispatch
- **Yoruichi**: `workflow_run` after Aizen completes on main

## See Also

- [Espada Pipeline](../../.forgejo/workflows/) -- Forgejo mirror
