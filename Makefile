# Makefile for managing the Exousia OS build process.

# --- Configuration ---
# Default image base path for local development. Can be overridden for CI.
IMAGE_BASE_GHCR  ?= ghcr.io/borninthedark/exousia
LATEST_TAG       = latest

# --- Dynamic Variables ---
GIT_VERSION      := $(shell git rev-parse --short HEAD)
GIT_COMMIT       := $(shell git rev-parse HEAD)

# GHCR tags
IMAGE_GHCR_SHORT  := $(IMAGE_BASE_GHCR):$(GIT_VERSION)
IMAGE_GHCR_FULL   := $(IMAGE_BASE_GHCR):$(GIT_COMMIT)
IMAGE_GHCR_LATEST := $(IMAGE_BASE_GHCR):$(LATEST_TAG)

# --- Commands ---
.PHONY: all build test push deploy clean

# Default 'make' command.
all: build

# 'make build' - Builds the image with all tags.
build:
	@echo "--> Building image:  $(IMAGE_GHCR_LATEST)"
	podman build \
	  -t $(IMAGE_GHCR_SHORT) -t $(IMAGE_GHCR_FULL) -t $(IMAGE_GHCR_LATEST) .

# 'make test' - Runs the Bats test suite.
test:
	@echo "--> Running Bats tests..."
	bats tests/image_content.bats

# 'make push' - Pushes all tags.
push: build
	@echo "--> Pushing image to GHCR..."
	podman push $(IMAGE_GHCR_SHORT)
	podman push $(IMAGE_GHCR_FULL)
	podman push $(IMAGE_GHCR_LATEST)

# 'make deploy' - Provides instructions for switching to the new image.
deploy:
	@echo "--> To switch to the locally built image, run:"
	@echo "sudo bootc switch ostree-unverified-container:$(IMAGE_LOCAL_LATEST)"
	@echo "or with a specific commit tag:"
	@echo "sudo bootc switch ostree-unverified-container:$(IMAGE_LOCAL_FULL)"
	@echo ""
	@echo "--> To switch to the GHCR image, run:"
	@echo "sudo bootc switch ghcr.io/borninthedark/exousia:latest"
	@echo "or with a specific commit tag:"
	@echo "sudo bootc switch ghcr.io/borninthedark/exousia:$(GIT_COMMIT)"

# 'make clean' - Removes locally built images.
clean:
	@echo "--> Removing images..."
	-podman rmi $(IMAGE_GHCR_SHORT) $(IMAGE_GHCR_FULL) $(IMAGE_GHCR_LATEST) 2>/dev/null || true
	@echo "--> Cleanup complete."
