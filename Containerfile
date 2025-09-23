# Base Image
FROM quay.io/fedora/fedora-sway-atomic:42

# Add metadata for my custom bootc image
LABEL \
    name="exousia" \
    version="0.0.1" \
    author="Princeton Strong" \
    description="Fedora Atomic - Bootc Custom"

# --- Add Your Customizations Below ---
RUN dnf install -y \
    podman-compose \
    neovim \
    wireguard-tools \ 
    lsd \ 
    htop \ 
    btop \ 
    bat \ 
    fastfetch \
    distrobox \ 
    git \
    make \
    && dnf clean all


