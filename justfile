# Exousia Development Commands

# Variables
tag := env("TAG", "latest")
image := env("IMAGE", "ghcr.io/borninthedark/exousia")

# ---------------------------------------------------------------------------
# Development
# ---------------------------------------------------------------------------

# Format code (black + isort)
format:
    uv run black tools/
    uv run isort tools/

# Run all linters
lint:
    #!/bin/bash
    set -euo pipefail
    echo "Running black..."
    uv run black --check tools/
    echo "Running isort..."
    uv run isort --check-only tools/
    echo "Running ruff..."
    uv run ruff check tools/
    echo "Running pylint..."
    uv run pylint tools/*.py || true
    echo "Running mypy..."
    uv run mypy tools/ || true

# Run pytest
test:
    uv run pytest tools/ -v --tb=short

# Run pytest with coverage (95% floor)
test-cov:
    #!/bin/bash
    set -euo pipefail
    uv run pytest tools/ -v --tb=short --cov=tools --cov-report=term --cov-report=html
    echo "Coverage report: htmlcov/index.html"
    uv run python -c "
    import sys, subprocess
    output = subprocess.check_output(
        ['uv', 'run', 'coverage', 'report', '--format=total'], text=True
    ).strip()
    total = float(output)
    print(f'Total coverage: {total}%')
    sys.exit(0 if total >= 95.0 else 1)
    "

# Clean generated files
clean:
    #!/bin/bash
    find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
    find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
    find . -type d -name .mypy_cache -exec rm -rf {} + 2>/dev/null || true
    find . -type d -name .ruff_cache -exec rm -rf {} + 2>/dev/null || true
    find . -type f -name "*.pyc" -delete
    rm -rf htmlcov/ .coverage coverage.xml
    rm -f Dockerfile.*.generated Dockerfile.generated
    rm -rf build/resolved-*.json build/resolved-*.yml

# Validate YAML blueprint
validate:
    uv run python -m generator --config adnyeus.yml --validate

# Run pre-commit hooks
pre-commit:
    uv run pre-commit run --all-files

# Regenerate README.md
readme:
    uv run python tools/generate-readme.py

# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------

# Generate atomic Containerfile
build-atomic:
    #!/bin/bash
    set -euo pipefail
    mkdir -p build
    uv run python -m generator \
        --config adnyeus.yml \
        --image-type fedora-sway-atomic \
        --resolved-package-plan build/resolved-build-plan.atomic.json \
        --output Dockerfile.atomic.generated

# Generate bootc Containerfile
build-bootc:
    #!/bin/bash
    set -euo pipefail
    mkdir -p build
    uv run python -m generator \
        --config adnyeus.yml \
        --image-type fedora-bootc \
        --enable-plymouth \
        --resolved-package-plan build/resolved-build-plan.bootc.json \
        --output Dockerfile.bootc.generated

# Build image with podman
build:
    podman build -t exousia:latest -f Containerfile.atomic .

# Push image to GHCR
push:
    podman push {{image}}:{{tag}}

# Build and push to local registry
local-build:
    #!/bin/bash
    set -euo pipefail
    echo "==> Verifying build environment..."
    BUILDAH_VERSION=$(buildah --version | awk '{print $3}')
    REQUIRED_VERSION="1.14.5"
    if [ "$(printf '%s\n' "$REQUIRED_VERSION" "$BUILDAH_VERSION" | sort -V | head -n1)" != "$REQUIRED_VERSION" ]; then
        echo "ERROR: buildah version $BUILDAH_VERSION is below the required $REQUIRED_VERSION"
        exit 1
    fi
    echo "==> Generating Containerfile..."
    mkdir -p build
    uv run python -m generator \
        --config adnyeus.yml \
        --image-type fedora-sway-atomic \
        --resolved-package-plan build/resolved-build-plan.local.json \
        --output Dockerfile.local.generated
    echo "==> Building image with buildah..."
    buildah bud -t "localhost:5000/exousia:{{tag}}" -f Dockerfile.local.generated .
    echo "==> Pushing to local registry..."
    skopeo copy \
        "containers-storage:localhost:5000/exousia:{{tag}}" \
        "docker://localhost:5000/exousia:{{tag}}" \
        --dest-tls-verify=false
    echo "==> Done. Image available at localhost:5000/exousia:{{tag}}"

# Promote local image to GHCR
local-push:
    #!/bin/bash
    set -euo pipefail
    echo "==> Copying localhost:5000/exousia:{{tag}} -> {{image}}:{{tag}}"
    skopeo copy \
        "docker://localhost:5000/exousia:{{tag}}" \
        "docker://{{image}}:{{tag}}" \
        --src-tls-verify=false
    echo "==> Pushed to {{image}}:{{tag}}"

# Mirror GHCR image to local registry
local-mirror:
    #!/bin/bash
    set -euo pipefail
    echo "==> Copying {{image}}:{{tag}} -> localhost:5000/exousia:{{tag}}"
    skopeo copy \
        "docker://{{image}}:{{tag}}" \
        "docker://localhost:5000/exousia:{{tag}}" \
        --dest-tls-verify=false
    echo "==> Mirrored to localhost:5000/exousia:{{tag}}"

# ---------------------------------------------------------------------------
# Test
# ---------------------------------------------------------------------------

# Run pre-build overlay tests
overlay-test:
    #!/bin/bash
    set -euo pipefail
    echo "==> Running overlay content tests..."
    bats tests/overlay_content.bats

# Run bats tests against local image
local-test:
    #!/bin/bash
    set -euo pipefail
    echo "==> Running bats tests against localhost:5000/exousia:{{tag}}..."
    podman run --rm "localhost:5000/exousia:{{tag}}" cat /etc/os-release
    TEST_IMAGE_TAG="localhost:5000/exousia:{{tag}}" buildah unshare -- bats tests/image_content.bats

# ---------------------------------------------------------------------------
# Quadlet Lifecycle
# ---------------------------------------------------------------------------

# Shared helpers: _expand_group outputs service list, _deploy_dir finds source
# These are shell functions inlined in recipes since just doesn't support
# cross-recipe return values.

# Install a quadlet: copy files for reboot persistence without starting
install name:
    #!/bin/bash
    set -euo pipefail
    _expand_group() {
        case "$1" in
            forgejo)   echo "forgejo-db forgejo forgejo-runner" ;;
            temporal)  echo "temporal-db temporal-server temporal-ui" ;;
            bookstack) echo "bookstack-db bookstack" ;;
            ai)        echo "ollama open-webui" ;;
            paperless) echo "paperless-db paperless-redis paperless" ;;
            immich)    echo "immich-db immich-redis immich-ml immich" ;;
            dns)       echo "coredns caddy" ;;
            *)         echo "$1" ;;
        esac
    }
    services=$(_expand_group "{{name}}")
    if [ -d "overlays/deploy" ]; then
        deploy_dir="overlays/deploy"
    elif [ -d "/usr/share/exousia/quadlets" ]; then
        deploy_dir="/usr/share/exousia/quadlets"
    else
        echo "ERROR: no deploy overlay found" >&2; exit 1
    fi
    mkdir -p ~/.config/containers/systemd/
    for svc in $services; do
        for ext in container volume network; do
            src="${deploy_dir}/${svc}.${ext}"
            [ -f "$src" ] && cp "$src" ~/.config/containers/systemd/ && echo "Installed ${src}"
        done
        for vol in "${deploy_dir}/${svc}"-*.volume; do
            [ -f "$vol" ] || continue
            cp "$vol" ~/.config/containers/systemd/
            echo "Installed ${vol}"
        done
    done
    systemctl --user daemon-reload
    echo "{{name}} installed (starts on next boot)."

# Engage a quadlet: install + start now
engage name:
    #!/bin/bash
    set -euo pipefail
    _expand_group() {
        case "$1" in
            forgejo)   echo "forgejo-db forgejo forgejo-runner" ;;
            temporal)  echo "temporal-db temporal-server temporal-ui" ;;
            bookstack) echo "bookstack-db bookstack" ;;
            ai)        echo "ollama open-webui" ;;
            paperless) echo "paperless-db paperless-redis paperless" ;;
            immich)    echo "immich-db immich-redis immich-ml immich" ;;
            dns)       echo "coredns caddy" ;;
            *)         echo "$1" ;;
        esac
    }
    services=$(_expand_group "{{name}}")
    just install "{{name}}"
    # Start the last service (systemd dependencies pull in the rest)
    last_svc="${services##* }"
    systemctl --user start "${last_svc}.service"
    echo "{{name}} engaged."

# Disengage a quadlet: stop service but keep files (restarts on reboot)
disengage name:
    #!/bin/bash
    set -euo pipefail
    _expand_group_reverse() {
        case "$1" in
            forgejo)   echo "forgejo-runner forgejo forgejo-db" ;;
            temporal)  echo "temporal-ui temporal-server temporal-db" ;;
            bookstack) echo "bookstack bookstack-db" ;;
            ai)        echo "open-webui ollama" ;;
            paperless) echo "paperless paperless-redis paperless-db" ;;
            immich)    echo "immich immich-ml immich-redis immich-db" ;;
            dns)       echo "caddy coredns" ;;
            *)         echo "$1" ;;
        esac
    }
    services=$(_expand_group_reverse "{{name}}")
    for svc in $services; do
        systemctl --user stop "${svc}.service" 2>/dev/null || true
    done
    echo "{{name}} disengaged (will restart on reboot)."

# Remove a quadlet: stop + delete files (opposite of install/engage)
remove name:
    #!/bin/bash
    set -euo pipefail
    _expand_group_reverse() {
        case "$1" in
            forgejo)   echo "forgejo-runner forgejo forgejo-db" ;;
            temporal)  echo "temporal-ui temporal-server temporal-db" ;;
            bookstack) echo "bookstack bookstack-db" ;;
            ai)        echo "open-webui ollama" ;;
            paperless) echo "paperless paperless-redis paperless-db" ;;
            immich)    echo "immich immich-ml immich-redis immich-db" ;;
            dns)       echo "caddy coredns" ;;
            *)         echo "$1" ;;
        esac
    }
    services=$(_expand_group_reverse "{{name}}")
    for svc in $services; do
        systemctl --user stop "${svc}.service" 2>/dev/null || true
        rm -f ~/.config/containers/systemd/${svc}.container
        rm -f ~/.config/containers/systemd/${svc}.volume
        rm -f ~/.config/containers/systemd/${svc}.network
        rm -f ~/.config/containers/systemd/${svc}-*.volume
    done
    systemctl --user daemon-reload
    echo "{{name}} removed (won't start on reboot)."

# Show status of a quadlet (group-aware)
report name:
    #!/bin/bash
    _expand_group() {
        case "$1" in
            forgejo)   echo "forgejo-db forgejo forgejo-runner" ;;
            temporal)  echo "temporal-db temporal-server temporal-ui" ;;
            bookstack) echo "bookstack-db bookstack" ;;
            ai)        echo "ollama open-webui" ;;
            paperless) echo "paperless-db paperless-redis paperless" ;;
            immich)    echo "immich-db immich-redis immich-ml immich" ;;
            dns)       echo "coredns caddy" ;;
            *)         echo "$1" ;;
        esac
    }
    services=$(_expand_group "{{name}}")
    for svc in $services; do
        systemctl --user status "${svc}.service" --no-pager 2>/dev/null || true
        echo ""
    done

# Follow logs of a quadlet (group-aware)
logs name:
    #!/bin/bash
    _expand_group() {
        case "$1" in
            forgejo)   echo "forgejo-db forgejo forgejo-runner" ;;
            temporal)  echo "temporal-db temporal-server temporal-ui" ;;
            bookstack) echo "bookstack-db bookstack" ;;
            ai)        echo "ollama open-webui" ;;
            paperless) echo "paperless-db paperless-redis paperless" ;;
            immich)    echo "immich-db immich-redis immich-ml immich" ;;
            dns)       echo "coredns caddy" ;;
            *)         echo "$1" ;;
        esac
    }
    services=$(_expand_group "{{name}}")
    units=""
    for svc in $services; do
        units="$units -u ${svc}.service"
    done
    journalctl --user $units -f

# ---------------------------------------------------------------------------
# DNS + Reverse Proxy (CoreDNS + Caddy)
# ---------------------------------------------------------------------------

# Start CoreDNS + Caddy with config setup and systemd-resolved integration
dns-setup:
    #!/bin/bash
    set -euo pipefail
    # Copy config files (remove first — :z relabel changes ownership)
    podman unshare rm -rf ~/.config/coredns 2>/dev/null || true
    rm -rf ~/.config/caddy/Caddyfile 2>/dev/null || true
    mkdir -p ~/.config/coredns ~/.config/caddy
    cp overlays/deploy/coredns/Corefile ~/.config/coredns/
    cp overlays/deploy/coredns/exousia.local.zone ~/.config/coredns/
    cp overlays/deploy/caddy/Caddyfile ~/.config/caddy/
    # Engage quadlets
    just engage dns
    # Configure systemd-resolved for .exousia.local
    if [ ! -f /etc/systemd/resolved.conf.d/exousia-local.conf ]; then
        sudo mkdir -p /etc/systemd/resolved.conf.d
        printf '[Resolve]\nDNS=127.0.0.1:5354\nDomains=~exousia.local\n' | \
            sudo tee /etc/systemd/resolved.conf.d/exousia-local.conf >/dev/null
        sudo systemctl restart systemd-resolved
        echo "Configured systemd-resolved for exousia.local"
    fi
    echo "DNS + proxy started — https://forgejo.exousia.local"

# Trust Caddy's internal CA (run once after first start)
dns-trust-ca:
    #!/bin/bash
    set -euo pipefail
    echo "Waiting for Caddy to generate its root CA..."
    podman exec caddy sh -c 'while [ ! -f /data/caddy/pki/authorities/local/root.crt ]; do sleep 1; done'
    podman exec caddy cat /data/caddy/pki/authorities/local/root.crt | \
        sudo tee /etc/pki/ca-trust/source/anchors/caddy-local.crt >/dev/null
    sudo update-ca-trust
    echo "Caddy root CA trusted."
