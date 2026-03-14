# 12th Division Pipeline

GitHub Actions CI/CD workflows named after 12th Division captains and members from BLEACH.
The 12th Division is the Shinigami Research and Development Institute — Calendula (Despair in Your Heart).

## Workflows

| Captain | File | Division | Role |
|---------|------|----------|------|
| **Urahara** | `urahara.yml` | 12th (Despair in Your Heart) | Orchestrator: calls Hikifune + Uhin in parallel, then Hiyori, then gate |
| **Hikifune** | `hikifune.yml` | 12th (Despair in Your Heart) | CI: Ruff, Black, isort, pytest |
| **Uhin** | `uhin.yml` | 12th (Despair in Your Heart) | Security: Hadolint, Checkov, Trivy config scan, Bandit |
| **Hiyori** | `hiyori.yml` | 12th (Despair in Your Heart) | Build, Cosign, Trivy image scan, semver release |
| **Nemu** | `nemu.yml` | 12th (Despair in Your Heart) | Post-CI: generates STATUS.md |
| **Mayuri** | `mayuri.yml` | 12th (Despair in Your Heart) | Dotfiles watcher: polls `borninthedark/dotfiles`, triggers Urahara on change |

## Captains

| Captain | Tenure | Notes |
|---------|--------|-------|
| Uhin Zenjoji | 1002 A.D. - ? | Deceased — founding captain |
| Kirio Hikifune | ? - 1891 A.D. | Promoted to Royal Guard (Squad Zero) |
| Kisuke Urahara | 1891 A.D. - ? | Founder of the SRDI; exile |
| Mayuri Kurotsuchi | current | Current captain |

## Pipeline Flow

```text
Urahara -> Hikifune + Uhin (parallel) -> Hiyori -> Gate
                                                    |
Nemu (on Urahara completion, main only) <-----------+

Mayuri (scheduled, independent) -> triggers Urahara if dotfiles changed
```

## Triggers

- **Urahara**: push/PR to main, scheduled at 00:10 / 08:10 / 16:10 UTC, manual dispatch
- **Mayuri**: scheduled at 04:10 / 12:10 / 20:10 UTC (midpoint between Urahara runs), manual dispatch
- **Nemu**: `workflow_run` after Urahara completes on main
