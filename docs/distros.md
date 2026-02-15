# Supported Distributions

Exousia focuses exclusively on Fedora bootc images with Sway as the window manager.

## Fedora Atomic Variants

| Image Type | Desktop Environment | Base Image |
|------------|---------------------|------------|
| `fedora-bootc` | None (minimal) | `quay.io/fedora/fedora-bootc` |
| `fedora-sway-atomic` | Sway (Wayland) | `quay.io/fedora/fedora-sway-atomic` |

## Building Images

### Using Workflow Dispatch (GitHub Actions)

1. Go to **Actions** → **Bootc DevSecOps Pipeline**
2. Click **Run workflow**
3. Select your desired **image type** (e.g., `fedora-bootc` or `fedora-sway-atomic`)
4. Select the Fedora version
5. Click **Run workflow**

Images are tagged with:

- OS family and version (e.g., `fedora-43`)
- Image type (e.g., `fedora-sway-atomic`)
- Git commit SHA
- Branch name

### Using YAML Configs Locally

Example: build a Fedora Sway Atomic image locally

```bash
uv run python tools/yaml-to-containerfile.py \
  --config yaml-definitions/sway-atomic.yml \
  --image-type fedora-sway-atomic \
  --fedora-version 43 \
  --output Containerfile.sway

buildah build -f Containerfile.sway -t localhost/fedora-sway-atomic:43 .
```

### Image Tags

Built images use the following patterns:

- **OS-Version**: `fedora-{version}` (e.g., `fedora-43`)
- **Image Type**: `{image-type}` (e.g., `fedora-sway-atomic`)
- **Main**: `main` (for main branch builds)
- **SHA**: `sha-{git-commit-sha}`
- **Branch**: `{branch-name}` (for branch builds)
- **Rolling**: `rolling-YYYYMMDD-HHMM` (time-stamped snapshot from scheduled builds)
- **Current**: `current` (rolling tag, always points to the latest scheduled build)

## Creating Custom Configs

Create a new YAML file for your custom Fedora image:

```yaml
name: my-custom-fedora
description: Custom Fedora bootc image
image-type: fedora-bootc
base-image: quay.io/fedora/fedora-bootc:43

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
uv run python tools/yaml-to-containerfile.py \
  --config my-custom-fedora.yml \
  --image-type fedora-bootc \
  --output Containerfile.custom

buildah build -f Containerfile.custom -t my-fedora:latest .
```
