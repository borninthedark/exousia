# Makefile for managing the Exousia bootc image lifecycle
# Supports build, test, push, and deployment workflows

# ============================================================================
# Configuration
# ============================================================================

REGISTRY      = localhost:5000
IMAGE_NAME    = exousia
LATEST_TAG    = latest

# Build arguments (can be overridden)
FEDORA_VERSION ?= 43
IMAGE_TYPE     ?= fedora-sway-atomic

# ============================================================================
# Dynamic Variables
# ============================================================================

GIT_VERSION       := $(shell git rev-parse --short HEAD 2>/dev/null || echo "unknown")
IMAGE_GIT         := $(REGISTRY)/$(IMAGE_NAME):$(GIT_VERSION)
IMAGE_LATEST      := $(REGISTRY)/$(IMAGE_NAME):$(LATEST_TAG)

# Detect current configuration from .fedora-version file
ifeq ($(shell test -f .fedora-version && echo exists),exists)
DETECTED_VERSION  := $(shell cut -d: -f1 .fedora-version)
DETECTED_TYPE     := $(shell cut -d: -f2 .fedora-version)
else
DETECTED_VERSION  := $(FEDORA_VERSION)
DETECTED_TYPE     := $(IMAGE_TYPE)
endif

# ============================================================================
# Color Output (optional, for better UX)
# ============================================================================

NO_COLOR      = \033[0m
BLUE          = \033[0;34m
GREEN         = \033[0;32m
YELLOW        = \033[0;33m
RED           = \033[0;31m

# ============================================================================
# Phony Targets
# ============================================================================

.PHONY: all build build-args test test-setup test-run test-clean \
        push deploy clean help lint check-config switch-version info

# ============================================================================
# Default Target
# ============================================================================

all: build

# ============================================================================
# Build Targets
# ============================================================================

## build: Build the bootc image with current configuration
build:
	@echo "$(BLUE)==> Building bootc image$(NO_COLOR)"
	@echo "    Version: $(DETECTED_VERSION)"
	@echo "    Type: $(DETECTED_TYPE)"
	@echo "    Tags: $(GIT_VERSION), $(LATEST_TAG)"
	podman build \
		--build-arg FEDORA_VERSION=$(DETECTED_VERSION) \
		--build-arg IMAGE_TYPE=$(DETECTED_TYPE) \
		-t $(IMAGE_GIT) \
		-t $(IMAGE_LATEST) \
		-f Containerfile \
		.
	@echo "$(GREEN)✓ Build completed successfully$(NO_COLOR)"

## build-args: Build with custom Fedora version and image type
build-args:
	@echo "$(BLUE)==> Building bootc image with custom arguments$(NO_COLOR)"
	@echo "    Version: $(FEDORA_VERSION)"
	@echo "    Type: $(IMAGE_TYPE)"
	podman build \
		--build-arg FEDORA_VERSION=$(FEDORA_VERSION) \
		--build-arg IMAGE_TYPE=$(IMAGE_TYPE) \
		-t $(IMAGE_GIT) \
		-t $(IMAGE_LATEST) \
		-f Containerfile \
		.
	@echo "$(GREEN)✓ Build completed successfully$(NO_COLOR)"

# ============================================================================
# Testing Targets
# ============================================================================

## test: Run all tests on the built image
test: test-setup test-run test-clean

## test-setup: Prepare testing environment
test-setup:
	@echo "$(BLUE)==> Setting up test environment$(NO_COLOR)"
	@if ! command -v bats >/dev/null 2>&1; then \
		echo "$(RED)✗ Error: bats testing framework not found$(NO_COLOR)"; \
		echo "  Install: https://bats-core.readthedocs.io/"; \
		exit 1; \
	fi
	@if ! command -v buildah >/dev/null 2>&1; then \
		echo "$(RED)✗ Error: buildah not found$(NO_COLOR)"; \
		echo "  Install: sudo dnf install buildah"; \
		exit 1; \
	fi
	@echo "$(GREEN)✓ Test environment ready$(NO_COLOR)"

## test-run: Execute bats test suite
test-run:
	@echo "$(BLUE)==> Running test suite$(NO_COLOR)"
	@export TEST_IMAGE_TAG=$(IMAGE_LATEST); \
	buildah unshare -- bats -r tests/
	@echo "$(GREEN)✓ All tests passed$(NO_COLOR)"

## test-clean: Clean up test resources
test-clean:
	@echo "$(BLUE)==> Cleaning up test resources$(NO_COLOR)"
	@# Bats cleanup is handled in teardown_file()
	@echo "$(GREEN)✓ Cleanup completed$(NO_COLOR)"

# ============================================================================
# Quality Assurance Targets
# ============================================================================

## lint: Run linting checks on Containerfile and scripts
lint:
	@echo "$(BLUE)==> Running linting checks$(NO_COLOR)"
	@if command -v hadolint >/dev/null 2>&1; then \
		echo "  - Linting Containerfile..."; \
		hadolint Containerfile --ignore DL3041,DL3059,SC2086,DL4006,SC3037 || true; \
	else \
		echo "$(YELLOW)⚠ hadolint not found, skipping Containerfile linting$(NO_COLOR)"; \
	fi
	@if command -v shellcheck >/dev/null 2>&1; then \
		echo "  - Linting shell scripts..."; \
		find custom-scripts -type f -executable -exec shellcheck {} + || true; \
	else \
		echo "$(YELLOW)⚠ shellcheck not found, skipping script linting$(NO_COLOR)"; \
	fi
	@echo "$(GREEN)✓ Linting completed$(NO_COLOR)"

## check-config: Verify current configuration
check-config:
	@echo "$(BLUE)==> Current Configuration$(NO_COLOR)"
	@if [ -f .fedora-version ]; then \
		echo "  Source: .fedora-version file"; \
		echo "  Version: $(DETECTED_VERSION)"; \
		echo "  Type: $(DETECTED_TYPE)"; \
	else \
		echo "  Source: Default values"; \
		echo "  Version: $(FEDORA_VERSION)"; \
		echo "  Type: $(IMAGE_TYPE)"; \
	fi

# ============================================================================
# Version Management Targets
# ============================================================================

## switch-version: Switch Fedora version and/or image type
switch-version:
	@if [ -z "$(VERSION)" ] || [ -z "$(TYPE)" ]; then \
		echo "$(RED)✗ Error: VERSION and TYPE must be specified$(NO_COLOR)"; \
		echo "  Usage: make switch-version VERSION=43 TYPE=fedora-sway-atomic"; \
		echo "  Valid versions: 41, 42, 43, 44, rawhide"; \
		echo "  Valid types: fedora-bootc, fedora-sway-atomic"; \
		exit 1; \
	fi
	@echo "$(BLUE)==> Switching configuration$(NO_COLOR)"
	@echo "  New Version: $(VERSION)"
	@echo "  New Type: $(TYPE)"
	@./custom-scripts/fedora-version-switcher $(VERSION) $(TYPE)
	@echo "$(GREEN)✓ Configuration updated$(NO_COLOR)"
	@echo "  Run 'make build' to build with new configuration"

# ============================================================================
# Push and Deploy Targets
# ============================================================================

## push: Build and push the image to local registry
push: build
	@echo "$(BLUE)==> Pushing image to local registry$(NO_COLOR)"
	podman push $(IMAGE_GIT)
	podman push $(IMAGE_LATEST)
	@echo "$(GREEN)✓ Image pushed successfully$(NO_COLOR)"

## deploy: Display deployment instructions
deploy:
	@echo "$(BLUE)==> Deployment Instructions$(NO_COLOR)"
	@echo ""
	@echo "To switch to this bootc image:"
	@echo "  $(YELLOW)sudo bootc switch ostree-unverified-container:$(IMAGE_LATEST)$(NO_COLOR)"
	@echo ""
	@echo "To switch and apply immediately:"
	@echo "  $(YELLOW)sudo bootc switch ostree-unverified-container:$(IMAGE_LATEST) && sudo bootc upgrade$(NO_COLOR)"
	@echo ""
	@echo "To verify current status:"
	@echo "  $(YELLOW)bootc status$(NO_COLOR)"
	@echo ""

# ============================================================================
# Cleanup Targets
# ============================================================================

## clean: Remove built images and temporary files
clean:
	@echo "$(BLUE)==> Cleaning up$(NO_COLOR)"
	@podman rmi -f $(IMAGE_GIT) $(IMAGE_LATEST) 2>/dev/null || true
	@echo "$(GREEN)✓ Cleanup completed$(NO_COLOR)"

## clean-all: Remove all exousia images
clean-all:
	@echo "$(BLUE)==> Removing all exousia images$(NO_COLOR)"
	@podman images | grep $(IMAGE_NAME) | awk '{print $$3}' | xargs -r podman rmi -f
	@echo "$(GREEN)✓ All images removed$(NO_COLOR)"

# ============================================================================
# Information Targets
# ============================================================================

## info: Display detailed build information
info:
	@echo "$(BLUE)==> Build Information$(NO_COLOR)"
	@echo "  Image Name: $(IMAGE_NAME)"
	@echo "  Registry: $(REGISTRY)"
	@echo "  Git Version: $(GIT_VERSION)"
	@echo "  Latest Tag: $(IMAGE_LATEST)"
	@echo "  Git Tag: $(IMAGE_GIT)"
	@echo ""
	@echo "$(BLUE)==> Current Configuration$(NO_COLOR)"
	@if [ -f .fedora-version ]; then \
		echo "  Source: .fedora-version file"; \
		echo "  Version: $(DETECTED_VERSION)"; \
		echo "  Type: $(DETECTED_TYPE)"; \
	else \
		echo "  Source: Makefile defaults"; \
		echo "  Version: $(FEDORA_VERSION)"; \
		echo "  Type: $(IMAGE_TYPE)"; \
	fi
	@echo ""

## help: Display this help message
help:
	@echo "$(BLUE)Exousia Bootc Image Makefile$(NO_COLOR)"
	@echo ""
	@echo "$(GREEN)Build Targets:$(NO_COLOR)"
	@echo "  make build          - Build image with current configuration"
	@echo "  make build-args     - Build with custom VERSION and TYPE"
	@echo "                        Example: make build-args FEDORA_VERSION=42 IMAGE_TYPE=fedora-bootc"
	@echo ""
	@echo "$(GREEN)Testing Targets:$(NO_COLOR)"
	@echo "  make test           - Run complete test suite"
	@echo "  make test-setup     - Verify test environment"
	@echo "  make test-run       - Execute bats tests only"
	@echo "  make lint           - Run linting checks"
	@echo ""
	@echo "$(GREEN)Version Management:$(NO_COLOR)"
	@echo "  make switch-version - Switch Fedora version/type"
	@echo "                        Example: make switch-version VERSION=43 TYPE=fedora-bootc"
	@echo "  make check-config   - Display current configuration"
	@echo ""
	@echo "$(GREEN)Deployment Targets:$(NO_COLOR)"
	@echo "  make push           - Build and push to local registry"
	@echo "  make deploy         - Show deployment instructions"
	@echo ""
	@echo "$(GREEN)Cleanup Targets:$(NO_COLOR)"
	@echo "  make clean          - Remove built images"
	@echo "  make clean-all      - Remove all exousia images"
	@echo ""
	@echo "$(GREEN)Information:$(NO_COLOR)"
	@echo "  make info           - Display detailed build information"
	@echo "  make help           - Display this help message"
	@echo ""
	@echo "$(BLUE)Environment Variables:$(NO_COLOR)"
	@echo "  FEDORA_VERSION      - Fedora version to build (default: 43)"
	@echo "  IMAGE_TYPE          - Base image type (default: fedora-sway-atomic)"
	@echo "  REGISTRY            - Container registry (default: localhost:5000)"
	@echo ""
	@echo "$(BLUE)Configuration File:$(NO_COLOR)"
	@echo "  .fedora-version     - Stores current version:type configuration"
	@echo ""