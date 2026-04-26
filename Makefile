# Exousia Development Commands
.PHONY: help format lint test test-cov clean build-atomic build-bootc validate \
	ci-lint ci-test pre-commit build push \
	quadlet-install quadlet-enable quadlet-disable quadlet-start quadlet-stop \
	quadlet-logs quadlet-status \
	plane-env-init plane-quadlet-enable plane-quadlet-disable \
	plane-quadlet-start plane-quadlet-stop plane-quadlet-logs plane-quadlet-status \
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
	@echo "  push            Push bootc image to GHCR"
	@echo "  quadlet-install Install Quadlet definitions to systemd"
	@echo "  quadlet-enable  Enable the local registry at boot"
	@echo "  quadlet-disable Disable the local registry at boot"
	@echo "  quadlet-start   Start the local registry"
	@echo "  quadlet-stop    Stop the local registry"
	@echo "  quadlet-logs    View local registry logs"
	@echo "  quadlet-status  Show local registry status"
	@echo "  plane-env-init  Install Plane env template to ~/.config/exousia/plane"
	@echo "  plane-quadlet-enable  Enable Plane Quadlet services at boot"
	@echo "  plane-quadlet-disable Disable Plane Quadlet services at boot"
	@echo "  plane-quadlet-start   Start Plane Quadlet services in dependency order"
	@echo "  plane-quadlet-stop    Stop Plane Quadlet services"
	@echo "  plane-quadlet-logs    View Plane Quadlet logs"
	@echo "  plane-quadlet-status  Show Plane Quadlet service status"
	@echo "  local-build     Build image and push to local registry"
	@echo "  local-push      Promote image from local registry to GHCR"
	@echo "  local-mirror    Mirror image from GHCR to the local registry"
	@echo "  overlay-test    Run pre-build overlay tests"
	@echo "  local-test      Run bats tests against locally built image"
	@echo "  readme          Generate README.md from template"

# Variables with defaults
TAG ?= latest
IMAGE ?= ghcr.io/borninthedark/exousia

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
	uv run python -c "import sys; import subprocess; \
		output = subprocess.check_output(['uv', 'run', 'coverage', 'report', '--format=total'], text=True).strip(); \
		total = float(output); \
		print(f'Total coverage: {total}%'); \
		sys.exit(0 if total >= 85.0 else 1)"

# Clean generated files
clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .mypy_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .ruff_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	rm -rf htmlcov/ .coverage coverage.xml
	rm -f Dockerfile.*.generated Dockerfile.generated
	rm -rf build/resolved-*.json build/resolved-*.yml

# Build atomic Dockerfile from YAML
build-atomic:
	mkdir -p build
	uv run python -m generator \
		--config adnyeus.yml \
		--image-type fedora-sway-atomic \
		--resolved-package-plan build/resolved-build-plan.atomic.json \
		--output Dockerfile.atomic.generated

# Build bootc Dockerfile from YAML
build-bootc:
	mkdir -p build
	uv run python -m generator \
		--config adnyeus.yml \
		--image-type fedora-bootc \
		--enable-plymouth \
		--resolved-package-plan build/resolved-build-plan.bootc.json \
		--output Dockerfile.bootc.generated

# Validate YAML configuration
validate:
	uv run python -m generator \
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

# Push bootc image to GHCR
push:
	podman push $(IMAGE):$(TAG)

# Install Quadlet definitions to systemd user directory (does not enable)
quadlet-install:
	mkdir -p ~/.config/containers/systemd/
	cp overlays/deploy/*.container overlays/deploy/*.volume overlays/deploy/*.network ~/.config/containers/systemd/ 2>/dev/null || true
	systemctl --user daemon-reload
	@echo "Quadlets installed. Run 'make quadlet-enable' to enable at boot."

# Enable local registry service to start at boot
quadlet-enable:
	systemctl --user enable exousia-registry

# Disable local registry service from starting at boot
quadlet-disable:
	systemctl --user disable exousia-registry

# Start local registry service
quadlet-start:
	systemctl --user start exousia-registry

# Stop local registry service
quadlet-stop:
	systemctl --user stop exousia-registry

# View logs for local registry service
quadlet-logs:
	journalctl --user -u exousia-registry -f

# Show status of local registry service
quadlet-status:
	systemctl --user status exousia-registry --no-pager

# Initialize Plane environment file
plane-env-init:
	mkdir -p ~/.config/exousia/plane
	cp -n overlays/deploy/plane.env.example ~/.config/exousia/plane/plane.env
	@echo "Plane env file ready at ~/.config/exousia/plane/plane.env"
	@echo "Note: Quadlets now use /etc/exousia/plane/plane.env by default."
	@echo "The image build process provides a default there."


# Enable Plane Quadlet services to start at boot
plane-quadlet-enable:
	systemctl --user enable plane-db plane-redis plane-mq plane-minio plane-api plane-worker plane-beat-worker plane-migrator plane-web plane-space plane-admin plane-live plane-proxy

# Disable Plane Quadlet services from starting at boot
plane-quadlet-disable:
	systemctl --user disable plane-db plane-redis plane-mq plane-minio plane-api plane-worker plane-beat-worker plane-migrator plane-web plane-space plane-admin plane-live plane-proxy

# Start Plane Quadlet services in the documented order
plane-quadlet-start:
	systemctl --user start exousia-network.service
	systemctl --user start plane-db plane-redis plane-mq plane-minio
	systemctl --user start plane-api plane-worker plane-beat-worker plane-migrator
	systemctl --user start plane-web plane-space plane-admin plane-live plane-proxy

# Stop Plane Quadlet services
plane-quadlet-stop:
	systemctl --user stop plane-proxy plane-live plane-admin plane-space plane-web plane-migrator plane-beat-worker plane-worker plane-api plane-minio plane-mq plane-redis plane-db

# View logs for Plane Quadlet services
plane-quadlet-logs:
	journalctl --user -u plane-db -u plane-redis -u plane-mq -u plane-minio -u plane-api -u plane-worker -u plane-beat-worker -u plane-migrator -u plane-web -u plane-space -u plane-admin -u plane-live -u plane-proxy -f

# Show status for Plane Quadlet services
plane-quadlet-status:
	systemctl --user status plane-db plane-redis plane-mq plane-minio plane-api plane-worker plane-beat-worker plane-migrator plane-web plane-space plane-admin plane-live plane-proxy --no-pager

# Build image locally and push to local registry
local-build:
	@echo "==> Verifying build environment..."
	@BUILDAH_VERSION=$$(buildah --version | awk '{print $$3}'); \
	REQUIRED_VERSION="1.14.5"; \
	if [ "$$(printf '%s\n' "$$REQUIRED_VERSION" "$$BUILDAH_VERSION" | sort -V | head -n1)" != "$$REQUIRED_VERSION" ]; then \
		echo "ERROR: buildah version $$BUILDAH_VERSION is below the required $$REQUIRED_VERSION"; \
		exit 1; \
	fi
	@echo "==> Generating Containerfile..."
	mkdir -p build
	uv run python -m generator \
		--config adnyeus.yml \
		--image-type fedora-sway-atomic \
		--resolved-package-plan build/resolved-build-plan.local.json \
		--output Dockerfile.local.generated
	@echo "==> Building image with buildah..."
	buildah bud -t localhost:5000/exousia:$(TAG) -f Dockerfile.local.generated .
	@echo "==> Pushing to local registry..."
	skopeo copy \
		containers-storage:localhost:5000/exousia:$(TAG) \
		docker://localhost:5000/exousia:$(TAG) \
		--dest-tls-verify=false
	@echo "==> Done. Image available at localhost:5000/exousia:$(TAG)"

# Mirror image from GHCR to the local registry for bootc consumption
local-mirror:
	@echo "==> Copying $(IMAGE):$(TAG) -> localhost:5000/exousia:$(TAG)"
	skopeo copy \
		docker://$(IMAGE):$(TAG) \
		docker://localhost:5000/exousia:$(TAG) \
		--dest-tls-verify=false
	@echo "==> Mirrored to localhost:5000/exousia:$(TAG)"

# Promote image from local registry to GHCR
local-push:
	@echo "==> Copying localhost:5000/exousia:$(TAG) -> $(IMAGE):$(TAG)"
	skopeo copy \
		docker://localhost:5000/exousia:$(TAG) \
		docker://$(IMAGE):$(TAG) \
		--src-tls-verify=false
	@echo "==> Pushed to $(IMAGE):$(TAG)"

# Run pre-build overlay tests (no image required)
overlay-test:
	@echo "==> Running overlay content tests..."
	bats tests/overlay_content.bats

# Run bats tests against locally built image
local-test:
	@echo "==> Running bats tests against localhost:5000/exousia:$(TAG)..."
	podman run --rm localhost:5000/exousia:$(TAG) cat /etc/os-release
	bats tests/image_content.bats

# Generate README.md from template
readme:
	uv run python tools/generate-readme.py
