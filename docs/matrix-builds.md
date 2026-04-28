# Matrix Builds

Build multiple Fedora versions in parallel from a single workflow run.

## How It Works

The blueprint (`adnyeus.yml`) declares a primary Fedora version via
`image-version`. This is what every push, schedule, and PR build targets by
default. Matrix builds are opt-in through manual dispatch.

## Triggering a Matrix Build

1. Go to **Actions > Urahara - Orchestrator > Run workflow**
2. Set the `distro_versions` field:

| Value | Behavior |
|-------|----------|
| *(empty)* | Build blueprint default (`image-version`) |
| `44` | Build Fedora 44 only |
| `43` | Build Fedora 43 only (compatibility / backtest case) |
| `44,rawhide` | Build Fedora 44 and rawhide in parallel |
| `43,44,rawhide` | Build three versions in parallel |

## Default Behavior

| Trigger | Versions Built |
|---------|---------------|
| `push` to main | Blueprint `image-version` only |
| `schedule` | Blueprint `image-version` only |
| `pull_request` | Blueprint `image-version` only |
| `workflow_dispatch` (empty) | Blueprint `image-version` only |
| `workflow_dispatch` (CSV) | Each listed version in parallel |

## Primary vs Non-Primary

The blueprint `image-version` is always the **primary** build. Only the
primary build receives:

- `:latest` and `:current` tags
- Branch tag (e.g. `:main`)
- SBOM submission to GitHub Dependency Graph
- Semver release (tag + GitHub Release)

All builds (primary and non-primary) receive:

- Version-scoped tag: `:f43`, `:f44`
- Branch-version tag: `:main-f43`, `:main-f44`
- Build-specific tag: `:fedora-sway-atomic-f44-abc12345`
- Trivy scan + artifact upload
- OpenSCAP compliance scan
- Cosign signature

## Future Direction

The matrix pattern is designed to extend to additional dimensions:

- **Window manager**: `sway`, future alternatives
- **Desktop environment**: `kde`, `mate`
- **Image type**: current `fedora-sway-atomic` default plus the planned pure
  `fedora-bootc` base target

These will be additive inputs in Urahara when the blueprint supports them.

---

**[Back to Documentation Index](README.md)** | **[Back to Main README](../README.md)**
