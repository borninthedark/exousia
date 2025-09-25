# Makefile for managing the Exousia OS build process.

# --- Configuration ---
# Default image base path for local development. Can be overridden for CI.
IMAGE_BASE    ?= localhost:5000/exousia
LATEST_TAG    = latest

# --- Dynamic Variables ---
GIT_VERSION       := $(shell git rev-parse --short HEAD)
IMAGE_GIT         := $(IMAGE_BASE):$(GIT_VERSION)
IMAGE_LATEST      := $(IMAGE_BASE):$(LATEST_TAG)

# --- Commands ---
.PHONY: all build test push deploy

# Default 'make' command.
all: build

# 'make build' - Builds the image with git hash and ':latest' tags.
build:
	@echo "--> Building image: $(IMAGE_LATEST)"
	podman build -t $(IMAGE_GIT) -t $(IMAGE_LATEST) .

# 'make test' - Runs the Bats test suite.
test:
	@echo "--> Running Bats tests..."
	bats tests/

# 'make push' - Pushes the image.
push: build
	@echo "--> Pushing image to registry..."
	podman push $(IMAGE_GIT)
	podman push $(IMAGE_LATEST)

# 'make deploy' - Provides instructions for switching to the new image.
deploy:
	@echo "--> To switch to the locally built image, run:"
	@echo "sudo bootc switch ostree-unverified-container:$(IMAGE_LATEST)"