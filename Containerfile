# Start from the minimal, generic Fedora bootc base image
FROM quay.io/fedora/fedora-bootc:42

# Add metadata for the base image
LABEL \
    name="exousia" \
    version="2.0.0" \
    author="Princeton Strong" \
    description="A bespoke Sway OS, built from a minimal bootc base."

# --- Stage 1: Add All Local Files ---
# Copying all local files first optimizes the build cache.
COPY custom-repos/ /etc/yum.repos.d/
COPY custom-configs/ /etc/sway/config.d/
COPY scripts/ /usr/local/bin/

# --- Stage 2: Execute All System Modifications ---
# This single RUN command handles all execution steps for a more efficient layer.
RUN \
    # First, make all copied scripts executable.
    chmod +x /usr/local/bin/*; \
    \
    # Update all packages from the base image using dnf.
    dnf upgrade -y; \
    \
    # Add RPM Fusion, enable Cisco OpenH264, and install all desired packages.
    dnf install -y \
    [https://mirrors.rpmfusion.org/free/fedora/rpmfusion-free-release-$(rpm](https://mirrors.rpmfusion.org/free/fedora/rpmfusion-free-release-$(rpm) -E %fedora).noarch.rpm \
    [https://mirrors.rpmfusion.org/nonfree/fedora/rpmfusion-nonfree-release-$(rpm](https://mirrors.rpmfusion.org/nonfree/fedora/rpmfusion-nonfree-release-$(rpm) -E %fedora).noarch.rpm \
    && dnf config-manager --set-enabled fedora-cisco-openh264 \
    && dnf install -y \
    sway \
    swaybg \
    swayimg \
    swaylock-effects \
    waybar \
    rofi \
    wob \
    kitty \
    neovim \
    htop \
    nwg-look \
    swaync \
    && dnf clean all

