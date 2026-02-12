# Exousia Development Commands
.PHONY: help format lint test test-cov clean build-atomic build-bootc validate \
	ci-lint ci-test pre-commit build push \
	quadlet-install quadlet-enable quadlet-disable quadlet-start quadlet-stop \
	quadlet-logs quadlet-status \
	local-build local-push overlay-test local-test readme

# Default target: show help
help:
	@echo "Available targets:"
	@echo "  format          Format code with black and isort"
	@echo "  lint            Run all linters (black, ruff, pylint, mypy)"
	@echo "  test            Run pytest tests"
	@echo "  test-cov        Run tests with coverage report"
	@echo "  clean           Clean generated files"
	@echo "  build-atomic    Build atomic Dockerfile from YAML"
	@echo "  build-bootc     Build bootc Dockerfile from YAML"
	@echo "  validate        Validate YAML configuration"
	@echo "  ci-lint         Run CI linting checks"
	@echo "  ci-test         Run CI tests"
	@echo "  pre-commit      Run pre-commit hooks on all files"
	@echo "  build           Build bootc image with podman"
	@echo "  push            Push bootc image to DockerHub"
	@echo "  quadlet-install Install Quadlet definitions to systemd"
	@echo "  quadlet-enable  Enable Quadlet services at boot"
	@echo "  quadlet-disable Disable Quadlet services at boot"
	@echo "  quadlet-start   Start Quadlet services"
	@echo "  quadlet-stop    Stop Quadlet services"
	@echo "  quadlet-logs    View Quadlet service logs"
	@echo "  quadlet-status  Show Quadlet service status"
	@echo "  local-build     Build image and push to local registry"
	@echo "  local-push      Promote image from local registry to DockerHub"
	@echo "  overlay-test    Run pre-build overlay tests"
	@echo "  local-test      Run bats tests against locally built image"
	@echo "  readme          Generate README.md from template"

# Variables with defaults
TAG ?= latest
IMAGE ?= 1borninthedark/exousia

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
	rm -f Dockerfile.*.generated Dockerfile.generated

# Build atomic Dockerfile from YAML
build-atomic:
	uv run python tools/yaml-to-containerfile.py \
		--config adnyeus.yml \
		--image-type fedora-sway-atomic \
		--output Dockerfile.atomic.generated

# Build bootc Dockerfile from YAML
build-bootc:
	uv run python tools/yaml-to-containerfile.py \
		--config adnyeus.yml \
		--image-type fedora-bootc \
		--enable-plymouth \
		--output Dockerfile.bootc.generated

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
push:
	podman push $(IMAGE):$(TAG)

# Install Quadlet definitions to systemd user directory (does not enable)
quadlet-install:
	mkdir -p ~/.config/containers/systemd/
	cp overlays/deploy/*.container overlays/deploy/*.volume overlays/deploy/*.network ~/.config/containers/systemd/ 2>/dev/null || true
	systemctl --user daemon-reload
	@echo "Quadlets installed. Run 'make quadlet-enable' to enable at boot."

# Enable Quadlet services to start at boot
quadlet-enable:
	systemctl --user enable forgejo exousia-registry forgejo-runner

# Disable Quadlet services from starting at boot
quadlet-disable:
	systemctl --user disable forgejo exousia-registry forgejo-runner

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

# Build image locally and push to local registry
local-build:
	@echo "==> Generating Containerfile..."
	uv run python tools/yaml-to-containerfile.py \
		--config adnyeus.yml \
		--image-type fedora-sway-atomic \
		--output Dockerfile.local.generated
	@echo "==> Building image with buildah..."
	buildah bud -t localhost:5000/exousia:$(TAG) -f Dockerfile.local.generated .
	@echo "==> Pushing to local registry..."
	skopeo copy \
		containers-storage:localhost:5000/exousia:$(TAG) \
		docker://localhost:5000/exousia:$(TAG) \
		--dest-tls-verify=false
	@echo "==> Done. Image available at localhost:5000/exousia:$(TAG)"

# Promote image from local registry to DockerHub
local-push:
	@echo "==> Copying localhost:5000/exousia:$(TAG) -> docker.io/$(IMAGE):$(TAG)"
	skopeo copy \
		docker://localhost:5000/exousia:$(TAG) \
		docker://docker.io/$(IMAGE):$(TAG) \
		--src-tls-verify=false
	@echo "==> Pushed to docker.io/$(IMAGE):$(TAG)"

# Run pre-build overlay tests (no image required)
overlay-test:
	@echo "==> Running overlay content tests..."
	bats custom-tests/overlay_content.bats

# Run bats tests against locally built image
local-test:
	@echo "==> Running bats tests against localhost:5000/exousia:$(TAG)..."
	podman run --rm localhost:5000/exousia:$(TAG) cat /etc/os-release
	bats custom-tests/image_content.bats

# Generate README.md from template
readme:
	uv run python overlays/base/tools/generate-readme
