# Base Image
FROM localhost:5000/exousia:latest

# --- Layer on Files & Configurations First ---
# Copying files before running commands optimizes the build cache.
# Changes to these local files won't require reinstalling packages.

# Copy custom repository definitions into the image.
COPY custom-repos/nwg-shell.repo /etc/yum.repos.d/nwg-shell.repo

# Copy sway configuration files.
COPY custom-configs/ /etc/sway/config.d/

# Copy local scripts into the image's binary path.
COPY scripts/ /usr/local/bin/


# --- Execute Build & Installation Steps ---
# These RUN commands are placed after COPY to ensure the package
# installation layer is cached even when local files change.

# Make all copied scripts executable.
RUN chmod +x /usr/local/bin/*

# Install packages from the newly added repo and base repos.
RUN dnf install -y \
    nwg-look \
    && dnf clean all

# --- Optional Customizations (Examples) ---
# Uncomment the following sections to modify the base image's package set.

# Example: Add RPM Fusion Repositories
# RUN bash -c ' \
#    set -euo pipefail; \
#    FEDORA_VERSION=$(rpm -E %fedora); \
#    dnf install -y \
#      https://mirrors.rpmfusion.org/free/fedora/rpmfusion-free-release-${FEDORA_VERSION}.noarch.rpm \
#      https://mirrors.rpmfusion.org/nonfree/fedora/rpmfusion-nonfree-release-${FEDORA_VERSION}.noarch.rpm; \
#    dnf clean all \
# '

# Example: Override base packages using rpm-ostree
# RUN rpm-ostree override remove swaylock \
#     && dnf install -y swaylock-effects \
#     && dnf clean all

