# Exousia Development Commands

.PHONY: help format lint test test-cov clean validate ci-lint ci-test pre-commit \
	build push build-atomic build-bootc readme \
	quadlet-install quadlet-uninstall \
	local-build local-push local-mirror overlay-test local-test \
	plane-install plane-start plane-stop plane-status plane-logs \
	forgejo-start forgejo-stop forgejo-status forgejo-logs
# Variables
TAG ?= latest
IMAGE ?= ghcr.io/borninthedark/exousia

# ===========================================================================
# Help
# ===========================================================================

help:
	@echo "Development"
	@echo "  format          Format code (black + isort)"
	@echo "  lint            Run all linters"
	@echo "  test            Run pytest"
	@echo "  test-cov        Run pytest with coverage"
	@echo "  clean           Clean generated files"
	@echo "  validate        Validate YAML blueprint"
	@echo "  pre-commit      Run pre-commit hooks"
	@echo "  readme          Regenerate README.md"
	@echo ""
	@echo "Build"
	@echo "  build-atomic    Generate atomic Containerfile"
	@echo "  build-bootc     Generate bootc Containerfile"
	@echo "  build           Build image with podman"
	@echo "  push            Push image to GHCR"
	@echo "  local-build     Build and push to local registry"
	@echo "  local-push      Promote local image to GHCR"
	@echo "  local-mirror    Mirror GHCR image to local registry"
	@echo ""
	@echo "Test"
	@echo "  overlay-test    Run pre-build overlay tests"
	@echo "  local-test      Run bats tests against local image"
	@echo ""
	@echo "Quadlets (all apps)"
	@echo "  quadlet-install   Copy all quadlets to ~/.config/containers/systemd/"
	@echo "  quadlet-uninstall Remove all quadlets and stop services"
	@echo ""
	@echo "Plane (project management — 13 services)"
	@echo "  plane-install   Set up Plane env file and copy quadlets"
	@echo "  plane-start     Start Plane in dependency order"
	@echo "  plane-stop      Stop Plane (reverse order)"
	@echo "  plane-status    Show Plane service status"
	@echo "  plane-logs      Follow Plane logs"
	@echo ""
	@echo "Forgejo (git forge — 3 services)"
	@echo "  forgejo-start     Start Forgejo in dependency order"
	@echo "  forgejo-stop      Stop Forgejo"
	@echo "  forgejo-status    Show Forgejo service status"
	@echo "  forgejo-logs      Follow Forgejo logs"
	@echo ""
	@echo "Standalone containers"
	@echo "  start-<name>    Start a standalone quadlet (e.g. make start-freebsd)"
	@echo "  stop-<name>     Stop a standalone quadlet"
	@echo "  status-<name>   Show status of a standalone quadlet"
	@echo "  logs-<name>     Follow logs of a standalone quadlet"

# ===========================================================================
# Development
# ===========================================================================

format:
	uv run black tools/
	uv run isort tools/

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

test:
	uv run pytest tools/ -v --tb=short

test-cov:
	uv run pytest tools/ -v --tb=short --cov=tools --cov-report=term --cov-report=html
	@echo "Coverage report: htmlcov/index.html"
	uv run python -c "import sys; import subprocess; \
		output = subprocess.check_output(['uv', 'run', 'coverage', 'report', '--format=total'], text=True).strip(); \
		total = float(output); \
		print(f'Total coverage: {total}%'); \
		sys.exit(0 if total >= 85.0 else 1)"

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .mypy_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .ruff_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	rm -rf htmlcov/ .coverage coverage.xml
	rm -f Dockerfile.*.generated Dockerfile.generated
	rm -rf build/resolved-*.json build/resolved-*.yml

validate:
	uv run python -m generator \
		--config adnyeus.yml \
		--validate

ci-lint:
	@echo "==> Running CI linting checks..."
	uv run black --check tools/
	uv run isort --check-only tools/
	uv run ruff check tools/
	uv run pylint tools/*.py || true
	uv run mypy tools/ || true
	@echo "==> CI linting complete"

ci-test:
	@echo "==> Running CI tests..."
	uv run pytest tools/ -v --tb=short --cov=tools --cov-report=term
	@echo "==> CI tests complete"

pre-commit:
	uv run pre-commit run --all-files

readme:
	uv run python tools/generate-readme.py

# ===========================================================================
# Build
# ===========================================================================

build-atomic:
	mkdir -p build
	uv run python -m generator \
		--config adnyeus.yml \
		--image-type fedora-sway-atomic \
		--resolved-package-plan build/resolved-build-plan.atomic.json \
		--output Dockerfile.atomic.generated

build-bootc:
	mkdir -p build
	uv run python -m generator \
		--config adnyeus.yml \
		--image-type fedora-bootc \
		--enable-plymouth \
		--resolved-package-plan build/resolved-build-plan.bootc.json \
		--output Dockerfile.bootc.generated

build:
	podman build -t exousia:latest -f Containerfile.atomic .

push:
	podman push $(IMAGE):$(TAG)

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

local-mirror:
	@echo "==> Copying $(IMAGE):$(TAG) -> localhost:5000/exousia:$(TAG)"
	skopeo copy \
		docker://$(IMAGE):$(TAG) \
		docker://localhost:5000/exousia:$(TAG) \
		--dest-tls-verify=false
	@echo "==> Mirrored to localhost:5000/exousia:$(TAG)"

local-push:
	@echo "==> Copying localhost:5000/exousia:$(TAG) -> $(IMAGE):$(TAG)"
	skopeo copy \
		docker://localhost:5000/exousia:$(TAG) \
		docker://$(IMAGE):$(TAG) \
		--src-tls-verify=false
	@echo "==> Pushed to $(IMAGE):$(TAG)"

# ===========================================================================
# Test
# ===========================================================================

overlay-test:
	@echo "==> Running overlay content tests..."
	bats tests/overlay_content.bats

local-test:
	@echo "==> Running bats tests against localhost:5000/exousia:$(TAG)..."
	podman run --rm localhost:5000/exousia:$(TAG) cat /etc/os-release
	bats tests/image_content.bats

# ===========================================================================
# Quadlets — infrastructure (all apps)
# ===========================================================================

quadlet-install:
	mkdir -p ~/.config/containers/systemd/
	cp overlays/deploy/*.container ~/.config/containers/systemd/ 2>/dev/null || true
	cp overlays/deploy/*.volume ~/.config/containers/systemd/ 2>/dev/null || true
	cp overlays/deploy/*.network ~/.config/containers/systemd/ 2>/dev/null || true
	systemctl --user daemon-reload
	@echo "Quadlets installed. Services are disabled by default."
	@echo "Use app-specific targets to start (e.g. make plane-start)."

quadlet-uninstall:
	systemctl --user stop plane-proxy plane-live plane-admin plane-space plane-web \
		plane-migrator plane-beat-worker plane-worker plane-api \
		plane-minio plane-mq plane-redis plane-db 2>/dev/null || true
	systemctl --user reset-failed 2>/dev/null || true
	rm -f ~/.config/containers/systemd/plane-*.container
	rm -f ~/.config/containers/systemd/plane-*-data.volume
	rm -f ~/.config/containers/systemd/freebsd.container
	rm -f ~/.config/containers/systemd/exousia.network
	systemctl --user daemon-reload
	@echo "All quadlets removed."

# ===========================================================================
# Plane (project management — 13 services)
# ===========================================================================

PLANE_SERVICES_INFRA := plane-db plane-redis plane-mq plane-minio
PLANE_SERVICES_BACKEND := plane-api plane-worker plane-beat-worker plane-migrator
PLANE_SERVICES_FRONTEND := plane-web plane-space plane-admin plane-live plane-proxy
PLANE_SERVICES_ALL := $(PLANE_SERVICES_INFRA) $(PLANE_SERVICES_BACKEND) $(PLANE_SERVICES_FRONTEND)
PLANE_ENV_SRC := overlays/deploy/plane.env.example
PLANE_ENV_DST := /etc/exousia/plane/plane.env

plane-install: quadlet-install
	@if [ ! -f "$(PLANE_ENV_DST)" ]; then \
		echo "==> Installing Plane env file..."; \
		sudo mkdir -p /etc/exousia/plane; \
		sudo cp $(PLANE_ENV_SRC) $(PLANE_ENV_DST); \
		echo "Edit $(PLANE_ENV_DST) — change SECRET_KEY and MINIO_ROOT_PASSWORD."; \
	else \
		echo "$(PLANE_ENV_DST) already exists, skipping."; \
	fi
	@echo "Run 'make plane-start' when ready."

plane-start:
	systemctl --user start plane-proxy.service
	@echo "Plane started — http://localhost:8080"

plane-stop:
	systemctl --user stop $(PLANE_SERVICES_ALL) 2>/dev/null || true
	systemctl --user reset-failed 2>/dev/null || true
	@echo "Plane stopped."

plane-status:
	@systemctl --user status $(PLANE_SERVICES_ALL) --no-pager 2>/dev/null || true

plane-logs:
	journalctl --user $(patsubst %,-u %,$(PLANE_SERVICES_ALL)) -f

# ===========================================================================
# Standalone containers (start-<name>, stop-<name>, status-<name>, logs-<name>)
# ===========================================================================

start-%:
	systemctl --user start $*.service

stop-%:
	systemctl --user stop $*.service

status-%:
	@systemctl --user status $*.service --no-pager

logs-%:
	journalctl --user -u $*.service -f

# ===========================================================================
# Forgejo (git forge — 3 services)
# ===========================================================================

FORGEJO_SERVICES_ALL := forgejo-db forgejo forgejo-runner

forgejo-start:
	systemctl --user start forgejo-runner.service
	@echo "Forgejo started — http://localhost:3000"

forgejo-stop:
	systemctl --user stop $(FORGEJO_SERVICES_ALL) 2>/dev/null || true
	systemctl --user reset-failed 2>/dev/null || true
	@echo "Forgejo stopped."

forgejo-status:
	@systemctl --user status $(FORGEJO_SERVICES_ALL) --no-pager 2>/dev/null || true

forgejo-logs:
	journalctl --user -u forgejo.service -f
