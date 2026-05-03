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

# Run CI linting checks
ci-lint:
    #!/bin/bash
    set -euo pipefail
    echo "==> Running CI linting checks..."
    uv run black --check tools/
    uv run isort --check-only tools/
    uv run ruff check tools/
    uv run pylint tools/*.py || true
    uv run mypy tools/ || true
    echo "==> CI linting complete"

# Run CI tests
ci-test:
    #!/bin/bash
    set -euo pipefail
    echo "==> Running CI tests..."
    uv run pytest tools/ -v --tb=short --cov=tools --cov-report=term
    echo "==> CI tests complete"

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
# Quadlets — infrastructure (all apps)
# ---------------------------------------------------------------------------

# Copy all quadlets to ~/.config/containers/systemd/
quadlet-install:
    #!/bin/bash
    set -euo pipefail
    mkdir -p ~/.config/containers/systemd/
    cp overlays/deploy/*.container ~/.config/containers/systemd/ 2>/dev/null || true
    cp overlays/deploy/*.volume ~/.config/containers/systemd/ 2>/dev/null || true
    cp overlays/deploy/*.network ~/.config/containers/systemd/ 2>/dev/null || true
    systemctl --user daemon-reload
    echo "Quadlets installed. Services are disabled by default."
    echo "Use app-specific targets to start (e.g. just plane-start)."

# Remove all quadlets and stop services
quadlet-uninstall:
    #!/bin/bash
    systemctl --user stop plane-proxy plane-live plane-admin plane-space plane-web \
        plane-migrator plane-beat-worker plane-worker plane-api \
        plane-minio plane-mq plane-redis plane-db 2>/dev/null || true
    systemctl --user stop temporal-ui temporal-server temporal-db 2>/dev/null || true
    systemctl --user reset-failed 2>/dev/null || true
    rm -f ~/.config/containers/systemd/plane-*.container
    rm -f ~/.config/containers/systemd/plane-*-data.volume
    rm -f ~/.config/containers/systemd/temporal-*.container
    rm -f ~/.config/containers/systemd/temporal-*-data.volume
    rm -f ~/.config/containers/systemd/freebsd.container
    rm -f ~/.config/containers/systemd/exousia.network
    systemctl --user daemon-reload
    echo "All quadlets removed."

# ---------------------------------------------------------------------------
# Plane (project management — 13 services)
# ---------------------------------------------------------------------------

plane_services_infra := "plane-db plane-redis plane-mq plane-minio"
plane_services_backend := "plane-api plane-worker plane-beat-worker plane-migrator"
plane_services_frontend := "plane-web plane-space plane-admin plane-live plane-proxy"
plane_services_all := plane_services_infra + " " + plane_services_backend + " " + plane_services_frontend
plane_env_src := "overlays/deploy/plane.env.example"
plane_env_dst := "/etc/exousia/plane/plane.env"

# Set up Plane env file and copy quadlets
plane-install: quadlet-install
    #!/bin/bash
    set -euo pipefail
    if [ ! -f "{{plane_env_dst}}" ]; then
        echo "==> Installing Plane env file..."
        sudo mkdir -p /etc/exousia/plane
        sudo cp "{{plane_env_src}}" "{{plane_env_dst}}"
        echo "Edit {{plane_env_dst}} — change SECRET_KEY and MINIO_ROOT_PASSWORD."
    else
        echo "{{plane_env_dst}} already exists, skipping."
    fi
    echo "Run 'just plane-start' when ready."

# Start Plane in dependency order
plane-start:
    systemctl --user start plane-proxy.service
    @echo "Plane started — http://localhost:8080"

# Stop Plane (reverse order)
plane-stop:
    #!/bin/bash
    systemctl --user stop {{plane_services_all}} 2>/dev/null || true
    systemctl --user reset-failed 2>/dev/null || true
    echo "Plane stopped."

# Show Plane service status
plane-status:
    #!/bin/bash
    systemctl --user status {{plane_services_all}} --no-pager 2>/dev/null || true

# Follow Plane logs
plane-logs:
    #!/bin/bash
    units=""
    for svc in {{plane_services_all}}; do
        units="$units -u $svc"
    done
    journalctl --user $units -f

# ---------------------------------------------------------------------------
# Standalone containers (just start <name>, just stop <name>, etc.)
# ---------------------------------------------------------------------------

# Enable a quadlet: copy its files, reload systemd, and start the service
engage name:
    #!/bin/bash
    set -euo pipefail
    mkdir -p ~/.config/containers/systemd/
    for ext in container volume network; do
        src="overlays/deploy/{{name}}.${ext}"
        if [ -f "$src" ]; then
            cp "$src" ~/.config/containers/systemd/
            echo "Copied ${src}"
        fi
    done
    # Also copy associated data volumes (e.g. ollama-data.volume)
    for vol in overlays/deploy/{{name}}-*.volume; do
        [ -f "$vol" ] || continue
        cp "$vol" ~/.config/containers/systemd/
        echo "Copied ${vol}"
    done
    systemctl --user daemon-reload
    systemctl --user start {{name}}.service
    echo "{{name}} engaged."

# Disable a quadlet: stop the service and remove its files
disengage name:
    #!/bin/bash
    set -euo pipefail
    systemctl --user stop {{name}}.service 2>/dev/null || true
    rm -f ~/.config/containers/systemd/{{name}}.container
    rm -f ~/.config/containers/systemd/{{name}}.volume
    rm -f ~/.config/containers/systemd/{{name}}.network
    rm -f ~/.config/containers/systemd/{{name}}-*.volume
    systemctl --user daemon-reload
    echo "{{name}} disengaged."

# Start a standalone quadlet
start name:
    systemctl --user start {{name}}.service

# Stop a standalone quadlet
stop name:
    systemctl --user stop {{name}}.service

# Show status of a standalone quadlet
status name:
    systemctl --user status {{name}}.service --no-pager

# Follow logs of a standalone quadlet
logs name:
    journalctl --user -u {{name}}.service -f

# ---------------------------------------------------------------------------
# Temporal (workflow orchestration — 3 services, opt-in via engage)
# ---------------------------------------------------------------------------

temporal_services := "temporal-db temporal-server temporal-ui"

# Engage and start the full Temporal stack
temporal-start:
    #!/bin/bash
    set -euo pipefail
    for svc in {{temporal_services}}; do
        just engage "$svc"
    done
    echo "Temporal started — UI: http://localhost:8233, gRPC: localhost:7233"

# Stop and disengage the full Temporal stack
temporal-stop:
    #!/bin/bash
    set -euo pipefail
    for svc in temporal-ui temporal-server temporal-db; do
        just disengage "$svc"
    done
    echo "Temporal stopped and disengaged."

# Show Temporal service status
temporal-status:
    #!/bin/bash
    systemctl --user status {{temporal_services}} --no-pager 2>/dev/null || true

# Follow Temporal logs
temporal-logs:
    #!/bin/bash
    units=""
    for svc in {{temporal_services}}; do
        units="$units -u $svc"
    done
    journalctl --user $units -f

# ---------------------------------------------------------------------------
# DNS + Reverse Proxy (CoreDNS + Caddy)
# ---------------------------------------------------------------------------

dns_services := "coredns caddy"

# Start CoreDNS + Caddy with config setup and systemd-resolved integration
dns-start:
    #!/bin/bash
    set -euo pipefail
    # Copy config files
    mkdir -p ~/.config/coredns ~/.config/caddy
    cp overlays/deploy/coredns/Corefile ~/.config/coredns/
    cp overlays/deploy/coredns/exousia.local.zone ~/.config/coredns/
    cp overlays/deploy/caddy/Caddyfile ~/.config/caddy/
    # Engage quadlets
    just engage coredns
    just engage caddy
    # Configure systemd-resolved for .exousia.local
    if [ ! -f /etc/systemd/resolved.conf.d/exousia-local.conf ]; then
        sudo mkdir -p /etc/systemd/resolved.conf.d
        printf '[Resolve]\nDNS=127.0.0.1:5353\nDomains=~exousia.local\n' | \
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

# Stop and disengage DNS + proxy
dns-stop:
    #!/bin/bash
    set -euo pipefail
    for svc in caddy coredns; do
        just disengage "$svc"
    done
    echo "DNS + proxy stopped."

# Show DNS + proxy status
dns-status:
    #!/bin/bash
    systemctl --user status {{dns_services}} --no-pager 2>/dev/null || true

# Follow DNS + proxy logs
dns-logs:
    #!/bin/bash
    journalctl --user -u coredns.service -u caddy.service -f

# ---------------------------------------------------------------------------
# Forgejo (git forge — 3 services)
# ---------------------------------------------------------------------------

forgejo_services_all := "forgejo-db forgejo forgejo-runner"

# Start Forgejo in dependency order
forgejo-start:
    systemctl --user start forgejo-runner.service
    @echo "Forgejo started — http://localhost:3000"

# Stop Forgejo
forgejo-stop:
    #!/bin/bash
    systemctl --user stop {{forgejo_services_all}} 2>/dev/null || true
    systemctl --user reset-failed 2>/dev/null || true
    echo "Forgejo stopped."

# Show Forgejo service status
forgejo-status:
    #!/bin/bash
    systemctl --user status {{forgejo_services_all}} --no-pager 2>/dev/null || true

# Follow Forgejo logs
forgejo-logs:
    journalctl --user -u forgejo.service -f
