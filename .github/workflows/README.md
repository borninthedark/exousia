# CI/CD Pipelines

Two parallel CI/CD pipelines named after BLEACH factions:

- **GitHub Actions** (`.github/workflows/`) — 12th Division (Shinigami SRDI) — production builds pushed to GHCR
- **Forgejo Actions** (`.forgejo/workflows/`) — Vandenreich (Quincy Sternritter) — local dev builds pushed to `localhost:5000`

## GitHub Actions — 12th Division Pipeline

| Captain | File | Role |
|---------|------|------|
| **Urahara** | `urahara.yml` | Orchestrator: calls Muramasa, Hikifune + Uhin in parallel, then Hiyori, then Cirucci |
| **Muramasa** | (inline job) | Defaults resolver: reads blueprint, builds version/type matrix |
| **Hikifune** | `hikifune.yml` | CI: Ruff, Black, isort, pytest |
| **Uhin** | `uhin.yml` | Security: file-structure gate, overlay Bats, Hadolint, Checkov, Trivy config scan, Bandit, OSV-Scanner |
| **Hiyori** | `hiyori.yml` | Build, Trivy image scan, SBOM, OpenSCAP, Cosign, semver release |
| **Kon** | `kon.yml` | Advanced CodeQL analysis for Python and GitHub Actions |
| **Nemu** | `nemu.yml` | Post-CI: commits refreshed `STATUS.md` with the latest orchestration result |
| **Mayuri** | `mayuri.yml` | Dotfiles watcher: polls `borninthedark/dotfiles`, triggers Urahara on change |
| **Ulquiorra** | `ulquiorra.yml` | Sealed boot: wraps base image with signed systemd-boot, UKI, and composefs |
| **Cirucci** | (inline in `urahara.yml`) | Gate: pipeline summary, promotion PRs for feature branches |
| **Yoruichi** | `yoruichi.yml` | Base image mirror: weekly sync of upstream Fedora images to GHCR |

### Image Tags (GitHub / GHCR)

| Tag | When Applied |
|-----|-------------|
| `prod` | Primary build on main (latest stable) |
| `latest` | Primary build on main |
| `f<version>` | Every build (e.g. `f44`) |
| `<type>-f<ver>-<sha>` | Every build (unique identifier) |
| `rolling-f<ver>-<date>` | Scheduled builds |
| `current` | Primary scheduled build |

### Pipeline Flow

```text
Urahara -> Muramasa (defaults) -> Hikifune + Uhin (parallel) -> Hiyori -> Ulquiorra (optional) -> Cirucci (gate)
                                                                                                       |
Nemu (on Urahara completion, main only) <--------------------------------------------------------------+

Mayuri (scheduled, independent) -> triggers Urahara if dotfiles changed
```

### Pipeline Flow (GitHub)

```text
Feature branch (uryu/*):
  Urahara -> Muramasa -> Hikifune + Uhin (parallel) -> Hiyori (skipped on forks)
    -> Cirucci creates promotion PR to main

Main branch:
  Urahara -> Muramasa -> Hikifune + Uhin (parallel) -> Hiyori (:prod on GHCR)
    -> Ulquiorra (optional) -> Cirucci (gate)
```

On successful feature branch pushes, Cirucci auto-creates a PR to
merge the branch into `main`. If a PR already exists, it skips creation.

### Triggers

- **Urahara**: push to `main` or `uryu/*`, PR to main, scheduled at 00:10 / 12:10 UTC, manual dispatch
- **Mayuri**: scheduled at 04:10 / 12:10 / 20:10 UTC, manual dispatch
- **Nemu**: `workflow_run` after Urahara completes on main

## Forgejo Actions — Vandenreich Pipeline

| Sternritter | Schrift | Role |
|-------------|---------|------|
| **Pernida** | The Compulsory (C) | Orchestrator (`pernida.yml`) — all jobs inlined |
| **Bambietta** | The Explode (E) | CI: Ruff, Black, isort, pytest |
| **Askin** | The Deathdealing (D) | Security: file-structure, overlay Bats, Hadolint, Checkov, Trivy, Bandit, OSV-Scanner |
| **Gremmy** | The Visionary (V) | Build with buildah, push to local registry (`localhost:5000`) |
| **Lille** | The X-Axis (X) | Integration test + policy gate (CVE threshold, image metadata) |
| **Jugram** | The Balance (B) | Summary + promotion to GitHub/Codeberg, Paperless doc sync |

All Vandenreich jobs are inlined into `pernida.yml` (not separate
`workflow_call` files) to avoid a Forgejo label dispatch bug where called
workflow jobs receive empty runner labels and never get picked up.

### Image Tags (Forgejo / Local Registry)

| Tag | When Applied |
|-----|-------------|
| `dev` | Every build (local development) |
| `latest` | Every build |
| `f<version>` | Every build (e.g. `f44`) |
| `<type>-f<ver>-<sha>` | Every build (unique identifier) |

### Pipeline Flow

```text
Feature branch (uryu/*):
  Pernida -> Bambietta + Askin (parallel) -> Gremmy (:dev to local registry)
    -> Lille (verify) -> Jugram (gate) pushes to GitHub/Codeberg

Main branch:
  Pernida -> Bambietta + Askin (parallel) -> Gremmy (:dev to local registry)
    -> Lille (verify) -> Jugram (gate) pushes to GitHub main
    -> triggers Urahara -> Hiyori (:prod on GHCR)
```

### Promotion Strategy

The Vandenreich pipeline implements a two-stage promotion model:

1. **Feature → Forgejo main**: On successful feature branch builds, Jugram
   creates a pull request in Forgejo to merge the feature branch into
   `main`. This gives the developer a chance to review and merge. If a PR
   already exists for the branch, it is not duplicated.

2. **Forgejo main → GitHub main**: On successful `main` builds, Jugram
   pushes Forgejo's `main` to GitHub via `git push --force-with-lease`.
   This triggers the GitHub-side Urahara pipeline, which builds the `:prod`
   image on GHCR.

This keeps Forgejo and GitHub main in sync: feature work goes through
Forgejo PRs, and successful main builds automatically promote to GitHub.

### Triggers

- **Pernida**: push to `main` or `uryu/*` branches, PR to main

### Required Secrets (Forgejo)

| Name | Purpose |
|------|---------|
| `FORGEJO_TOKEN` | Forgejo access token for creating promotion PRs via API |
| `GHCR_PAT` | GitHub PAT for pushing main to GitHub (repo scope) |

Configure in Forgejo: **Repository Settings → Actions → Secrets**.

### Key Differences from GitHub Actions

| Feature | GitHub (12th Division) | Forgejo (Vandenreich) |
|---------|----------------------|----------------------|
| Registry | GHCR (`ghcr.io`) | Local (`localhost:5000`) |
| Image signing | Cosign (OIDC keyless) | Not applicable |
| SBOM | Submitted to GitHub Dependency Graph | CycloneDX via Trivy (local) |
| CodeQL | Yes (Kon) | Not available |
| Status report | Nemu commits STATUS.md | Not applicable |
| Marketplace actions | SHA-pinned | Replaced with binary installs |
| Tag prefix | `prod` | `dev` |

## Captains (12th Division)

| Captain | Tenure | Notes |
|---------|--------|-------|
| Uhin Zenjoji | 1002 A.D. - ? | Deceased — founding captain |
| Kirio Hikifune | ? - 1891 A.D. | Promoted to Royal Guard (Squad Zero) |
| Kisuke Urahara | 1891 A.D. - ? | Founder of the SRDI; exile |
| Mayuri Kurotsuchi | current | Current captain |

## Forked PR Policy

Hiyori is skipped on pull requests from forks. The build path may need
repository secrets such as `GHCR_PAT` to pull private RPM overrides from GHCR.

## Trivy Reporting

Hiyori saves `trivy-results.txt` as a workflow artifact, publishes the report
in the workflow summary, and submits an SBOM to GitHub Dependency Graph on
`main`.

## CodeQL

Advanced CodeQL is configured in:

- workflow: `.github/workflows/kon.yml`
- config file: `.github/codeql/codeql-config.yml`

Languages: `python`, `actions`. Query suites: `security-extended`,
`security-and-quality`.
