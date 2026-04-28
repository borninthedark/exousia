# Supported Distributions

Exousia currently supports Fedora-based image generation for both
`fedora-bootc` and `fedora-sway-atomic`. The active root blueprint presently
defaults to a `fedora-sway-atomic` base image, even when other image types are
still supported by the toolchain and tests.

That statement covers build-tool support, not identical operational maturity.
Today:

- the root blueprint default is `fedora-sway-atomic`
- the toolchain can generate both `fedora-sway-atomic` and `fedora-bootc`
- the pure `fedora-bootc` base remains an explicit migration target rather
  than the established default desktop base
- the rebase compatibility goal is same-version Fedora Atomic -> Exousia ->
  Fedora Atomic, not arbitrary cross-family or cross-major rebases

## Fedora Atomic Variants

| Image Type | Desktop Environment | Base Image |
|------------|---------------------|------------|
| `fedora-bootc` | None (minimal) | `quay.io/fedora/fedora-bootc` |
| `fedora-sway-atomic` | Sway (Wayland) | `quay.io/fedora/fedora-sway-atomic` |

## Building Images

### Using Workflow Dispatch (GitHub Actions)

1. Go to **Actions** → **Urahara - Orchestrator**
2. Click **Run workflow**
3. Select your desired **image type** (e.g., `fedora-bootc` or `fedora-sway-atomic`)
4. Select the Fedora version (`44`, `rawhide`, or another explicitly supplied version)
5. Click **Run workflow**

Images are tagged with:

- `{build-type}-{short-sha}` (for example `fedora-sway-atomic-deadbeef`)
- `{branch-name}`
- `latest`
- `rolling-YYYYMMDD-HHMM` on scheduled runs
- `current` on scheduled runs

### Using YAML Configs Locally

Example: build a Fedora Sway Atomic image locally

```bash
uv run python -m generator \
  --config adnyeus.yml \
  --image-type fedora-sway-atomic \
  --output Containerfile.sway

buildah build -f Containerfile.sway -t localhost/fedora-sway-atomic .

```

The default root blueprint now targets Fedora `44`.

### Image Tags

Built images use the following patterns:

- **Primary build tag**: `{image-type}-{short-sha}`
- **Branch**: `{branch-name}`
- **Latest**: `latest`
- **Rolling**: `rolling-YYYYMMDD-HHMM` (time-stamped snapshot from scheduled builds)
- **Current**: `current` (rolling tag, always points to the latest scheduled build)

## Creating Custom Configs

Create a new YAML file for your custom Fedora image:

```yaml
name: my-custom-fedora
description: Custom Fedora bootc image
image-type: fedora-bootc
base-image: quay.io/fedora/fedora-bootc

labels:
  org.opencontainers.image.title: "My Custom Fedora"
  org.opencontainers.image.description: "Custom Fedora bootc"

modules:
  - type: rpm-ostree
    install:
      - neovim
      - htop
    remove:
      - firefox-langpacks
```

Then build it:

```bash
uv run python -m generator \
  --config my-custom-fedora.yml \
  --image-type fedora-bootc \
  --output Containerfile.custom

buildah build -f Containerfile.custom -t my-fedora:latest .
```
