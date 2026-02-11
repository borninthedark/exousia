# Exousia Development Commands

# Default recipe: show help
default:
    @just --list

# Format code with black and isort
format:
    uv run black tools/
    uv run isort tools/

# Run all linters (black, ruff, pylint, mypy)
lint:
    @echo "Running black..."
    uv run black --check tools/
    @echo "Running isort..."
    uv run isort --check-only tools/
    @echo "Running ruff..."
    uv run ruff check tools/
    @echo "Running pylint..."
    uv run pylint tools/*.py || true
    @echo "Running mypy..."
    uv run mypy tools/ || true

# Run pytest tests
test:
    uv run pytest tools/ -v --tb=short

# Run tests with coverage report
test-cov:
    uv run pytest tools/ -v --tb=short --cov=tools --cov-report=term --cov-report=html
    @echo "Coverage report: htmlcov/index.html"

# Clean generated files
clean:
    find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
    find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
    find . -type d -name .mypy_cache -exec rm -rf {} + 2>/dev/null || true
    find . -type d -name .ruff_cache -exec rm -rf {} + 2>/dev/null || true
    find . -type f -name "*.pyc" -delete
    rm -rf htmlcov/ .coverage coverage.xml
    rm -f Containerfile.*.generated

# Build atomic Containerfile from YAML
build-atomic:
    uv run python tools/yaml-to-containerfile.py \
        --config adnyeus.yml \
        --image-type fedora-sway-atomic \
        --output Containerfile.atomic.generated

# Build bootc Containerfile from YAML
build-bootc:
    uv run python tools/yaml-to-containerfile.py \
        --config adnyeus.yml \
        --image-type fedora-bootc \
        --enable-plymouth \
        --output Containerfile.bootc.generated

# Validate YAML configuration
validate:
    uv run python tools/yaml-to-containerfile.py \
        --config adnyeus.yml \
        --validate

# Run CI linting checks
ci-lint:
    @echo "==> Running CI linting checks..."
    uv run black --check tools/
    uv run isort --check-only tools/
    uv run ruff check tools/
    uv run pylint tools/*.py || true
    uv run mypy tools/ || true
    @echo "==> CI linting complete"

# Run CI tests
ci-test:
    @echo "==> Running CI tests..."
    uv run pytest tools/ -v --tb=short --cov=tools --cov-report=term
    @echo "==> CI tests complete"

# Run pre-commit hooks on all files
pre-commit:
    uv run pre-commit run --all-files

# Build bootc image with podman
build:
    podman build -t exousia:latest -f Containerfile.atomic .

# Push bootc image to DockerHub
push image="exousia:latest":
    podman push {{ image }}

# Install Quadlet definitions to systemd user directory
quadlet-install:
    mkdir -p ~/.config/containers/systemd/
    cp overlays/deploy/*.container overlays/deploy/*.volume overlays/deploy/*.network ~/.config/containers/systemd/ 2>/dev/null || true
    systemctl --user daemon-reload

# Start Quadlet services
quadlet-start:
    systemctl --user start forgejo exousia-registry

# Stop Quadlet services
quadlet-stop:
    systemctl --user stop forgejo forgejo-runner exousia-registry

# View logs for Quadlet services
quadlet-logs:
    journalctl --user -u forgejo -u forgejo-runner -u exousia-registry -f

# Show status of Quadlet services
quadlet-status:
    systemctl --user status forgejo forgejo-runner exousia-registry --no-pager

# Run ansible-lint on playbooks
ansible-lint:
    cd ansible && uv run ansible-lint site.yml

# Run Ansible playbook (dry run by default)
ansible-run *args:
    cd ansible && ansible-playbook site.yml --check {{ args }}

# Run Ansible playbook for real
ansible-apply *args:
    cd ansible && ansible-playbook site.yml {{ args }}

# Deploy local dev Quadlet services
ansible-quadlets *args:
    cd ansible && ansible-playbook site.yml --tags quadlets {{ args }}

# Run CI build pipeline locally
ansible-build *args:
    cd ansible && ansible-playbook site.yml --tags ci_build {{ args }}

# Build image locally and push to local registry
local-build tag="latest":
    @echo "==> Generating Containerfile..."
    uv run python tools/yaml-to-containerfile.py \
        --config adnyeus.yml \
        --image-type fedora-sway-atomic \
        --output Containerfile.local.generated
    @echo "==> Building image with buildah..."
    buildah bud -t localhost:5000/exousia:{{ tag }} -f Containerfile.local.generated .
    @echo "==> Pushing to local registry..."
    skopeo copy \
        containers-storage:localhost:5000/exousia:{{ tag }} \
        docker://localhost:5000/exousia:{{ tag }} \
        --dest-tls-verify=false
    @echo "==> Done. Image available at localhost:5000/exousia:{{ tag }}"

# Promote image from local registry to DockerHub
local-push tag="latest" image="1borninthedark/exousia":
    @echo "==> Copying localhost:5000/exousia:{{ tag }} -> docker.io/{{ image }}:{{ tag }}"
    skopeo copy \
        docker://localhost:5000/exousia:{{ tag }} \
        docker://docker.io/{{ image }}:{{ tag }} \
        --src-tls-verify=false
    @echo "==> Pushed to docker.io/{{ image }}:{{ tag }}"

# Run pre-build overlay tests (no image required)
overlay-test:
    @echo "==> Running overlay content tests..."
    bats custom-tests/overlay_content.bats

# Run bats tests against locally built image
local-test tag="latest":
    @echo "==> Running bats tests against localhost:5000/exousia:{{ tag }}..."
    podman run --rm localhost:5000/exousia:{{ tag }} cat /etc/os-release
    bats custom-tests/image_content.bats

# Generate README.md from template
readme:
    uv run python overlays/base/tools/generate-readme
