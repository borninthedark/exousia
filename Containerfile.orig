# Start from the minimal, generic Fedora bootc base image
FROM quay.io/fedora/fedora-bootc:42

# Add metadata for the base image
LABEL \
    name="exousia" \
    version="2.1.0" \
    author="Princeton Strong" \
    description="A bespoke Sway OS, built from a minimal bootc base with DNF5."

# --- Stage 1: Add All Local Files ---
# Copying all local files first optimizes the build cache.
COPY custom-repos/ /etc/yum.repos.d/
COPY custom-configs/ /etc/sway/config.d/
COPY scripts/ /usr/local/bin/

# --- Stage 2: Execute System Modifications ---
# Each RUN command creates a new layer for a clean, reliable build process.

# First, make all copied scripts executable.
RUN chmod +x /usr/local/bin/*

# Second, install dnf5 and create a system-wide alias to it.
# This ensures all subsequent calls to 'dnf' will use the faster 'dnf5'.
RUN dnf install -y dnf5 dnf5-plugins \
    && rm -f /usr/bin/dnf \
    && ln -s /usr/bin/dnf5 /usr/bin/dnf

# Third, update all packages from the base image using the new dnf5 (via the 'dnf' alias).
RUN dnf upgrade -y

# Fourth, use dnf5 to add RPM Fusion and enable the Cisco OpenH264 repo.
RUN dnf install -y \
    https://mirrors.rpmfusion.org/free/fedora/rpmfusion-free-release-$(rpm -E %fedora).noarch.rpm \
    https://mirrors.rpmfusion.org/nonfree/fedora/rpmfusion-nonfree-release-$(rpm -E %fedora).noarch.rpm \
    && dnf config-manager setopt fedora-cisco-openh264.enabled=1

# Finally, install the desired set of packages using dnf5.
RUN dnf install -y \
    sway \
    swaybg \
    sddm \ 
    swayimg \
    waybar \
    rofi \
    wob \
    kitty \
    neovim \
    htop \
    nwg-look \
    swaync \
    && dnf swap -y swaylock swaylock-effects \
    && dnf clean all

