# Makefile for building and managing the Exousia OS configuration layer.
# This automates the build, tagging, and push process.

# --- Configuration ---
# Set the name of your image and the registry it belongs to.
IMAGE_NAME = exousia
REGISTRY   = localhost:5000
LATEST_TAG = latest

# --- Dynamic Variables ---
# This command gets the unique short hash of the most recent git commit.
# This hash will become our version tag, e.g., "a1b2c3d".
GIT_VERSION := $(shell git rev-parse --short HEAD)

# The full name of the image, including the registry and git version tag.
# Example: localhost:5000/exousia:a1b2c3d
FULL_IMAGE_NAME = $(REGISTRY)/$(IMAGE_NAME):$(GIT_VERSION)
LATEST_IMAGE_NAME = $(REGISTRY)/$(IMAGE_NAME):$(LATEST_TAG)

# --- Commands ---
# .PHONY tells make that these are command names, not files.
.PHONY: all build push deploy

# The default command if you just type 'make'. It will run the 'build' command.
all: build

# 'make build' - Builds the image and applies two tags: the unique git hash and ':latest'.
build:
	@echo "--> Building image with tags: $(GIT_VERSION) and $(LATEST_TAG)"
	podman build -t $(FULL_IMAGE_NAME) -t $(LATEST_IMAGE_NAME) .

# 'make push' - Builds the image (if needed) and pushes both tags to the local registry.
push: build
	@echo "--> Pushing git-tagged image to local registry: $(FULL_IMAGE_NAME)"
	podman push $(FULL_IMAGE_NAME)
	@echo "--> Pushing latest-tagged image to local registry: $(LATEST_IMAGE_NAME)"
	podman push $(LATEST_IMAGE_NAME)

# 'make deploy' - Provides instructions for switching to the image.
deploy:
	@echo "--> To enable the 'bootc upgrade' workflow, switch to the ':latest' tag:"
	@echo "sudo bootc switch ostree-unverified-container:$(LATEST_IMAGE_NAME)"
	@echo "--> To pin to this specific version ($(GIT_VERSION)), use:"
	@echo "sudo bootc switch ostree-unverified-container:$(FULL_IMAGE_NAME)"
