# Makefile for managing the single-stage Exousia OS build process.

# --- Configuration ---
REGISTRY      = localhost:5000
IMAGE_NAME    = exousia
LATEST_TAG    = latest

# --- Dynamic Variables ---
GIT_VERSION       := $(shell git rev-parse --short HEAD)
IMAGE_GIT         := $(REGISTRY)/$(IMAGE_NAME):$(GIT_VERSION)
IMAGE_LATEST      := $(REGISTRY)/$(IMAGE_NAME):$(LATEST_TAG)

# --- Commands ---
.PHONY: all build push deploy

# Default 'make' command.
all: build

# 'make build' - Builds the image and applies two tags: git hash and ':latest'.
build:
	@echo "--> Building GOLD image with tags: $(GIT_VERSION) and $(LATEST_TAG)"
	podman build -t $(IMAGE_GIT) -t $(IMAGE_LATEST) .

# 'make push' - Pushes the gold image. This is your most common command.
push: build
	@echo "--> Pushing GOLD image to local registry..."
	podman push $(IMAGE_GIT)
	podman push $(IMAGE_LATEST)

# 'make deploy' - Provides instructions for switching to the image.
deploy:
	@echo "--> To follow updates, switch to the ':latest' tag:"
	@echo "sudo bootc switch ostree-unverified-container:$(IMAGE_LATEST)"
