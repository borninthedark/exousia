# 12th Division Pipeline

GitHub Actions CI/CD workflows named after 12th Division captains and members from BLEACH.
The 12th Division is the Shinigami Research and Development Institute.

## Workflows

| Captain | File | Division | Role |
|---------|------|----------|------|
| **Urahara** | `urahara.yml` | 12th | Orchestrator: calls Hikifune + Uhin in parallel, then Hiyori, then gate |
| **Hikifune** | `hikifune.yml` | 12th | CI: Ruff, Black, isort, pytest |
| **Uhin** | `uhin.yml` | 12th | Security: Hadolint, Checkov, Trivy config scan, Bandit |
| **Hiyori** | `hiyori.yml` | 12th | Build, Trivy image scan artifact, SBOM submission, Cosign, semver release |
| **Kon** | `kon.yml` | 12th | Advanced CodeQL analysis for Python and GitHub Actions |
| **Nemu** | `nemu.yml` | 12th | Post-CI: generates STATUS.md |
| **Mayuri** | `mayuri.yml` | 12th | Dotfiles watcher: polls `borninthedark/dotfiles`, triggers Urahara on change |

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

## Forked PR Policy

Hiyori is skipped on pull requests from forks.

That is intentional: the build path may need repository secrets such as
`GHCR_PAT` to pull private or restricted RPM override artifacts from GHCR.
Forked pull requests do not receive repository secrets, so Urahara runs the
CI and security workflows but leaves the image build/release workflow out of
that path.

## Trivy Reporting

Hiyori currently does three things with image-scan results on non-PR runs:

1. saves `trivy-results.txt` as a workflow artifact
2. publishes the full report in the workflow summary when present
3. submits an SBOM to GitHub Dependency Graph on `main` and uploads it as an artifact

GitHub's native notification email covers workflow status only. The full scan
content lives in the workflow summary and the uploaded artifacts.

## CodeQL

Advanced CodeQL is configured in:

- workflow: `.github/workflows/kon.yml`
- config file: `.github/codeql/codeql-config.yml`

Current setup:

- languages: `python`, `actions`
- build mode: `none`
- query suites: `security-extended`, `security-and-quality`
- scoped paths:
  - `tools/`
  - `.github/workflows/`
  - `.github/actions/`
  - `overlays/base/tools/`
