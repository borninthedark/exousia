# Start from the minimal, generic Fedora bootc base image
FROM quay.io/fedora/fedora-bootc:42

# Add metadata for the base image
LABEL \
    name="exousia" \
    version="2.0.0" \
    author="Princeton Strong" \
    description="A bespoke Sway OS, built from a minimal bootc base."

# --- Stage 1: Add All Local Files ---
# Copying files first optimizes the build cache.
COPY custom-configs/ /etc/sway/config.d/
COPY scripts/ /usr/local/bin/
COPY custom-repos/ /etc/yum.repos.d/

# --- Stage 2: Execute System Modifications ---

# Make all copied scripts executable
RUN chmod +x /usr/local/bin/*

# Upgrade all core OS packages provided by the base image.
# This is one of the few places where 'rpm-ostree' is necessary.
RUN rpm-ostree upgrade

# Add RPM Fusion, enable Cisco OpenH264, and install all desired packages in a single layer.
# This is the standard and most efficient way to manage packages with DNF.
RUN dnf install -y \
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

