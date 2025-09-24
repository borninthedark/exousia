# Start from the official Fedora 42 Sway Atomic base image
FROM quay.io/fedora/fedora-bootc:42

# Add metadata for the base image
LABEL \
    name="exousia" \
    version="1.0.0" \
    author="Princeton Strong" \
    description="Monolithic gold image for Exousia OS."

# --- Stage 1: Add All Local Files ---
# By copying all local files first, we ensure that changes to these files
# do not invalidate the package installation layer of the build cache.
COPY custom-repos/ /etc/yum.repos.d/
COPY custom-configs/ /etc/sway/config.d/
COPY scripts/ /usr/local/bin/

# --- Stage 2: Execute System Modifications ---
# These commands run after the files are in place. The results of these
# commands will be cached as long as no files in earlier stages change.

# Add RPM Fusion repositories and upgrade the system
RUN rpm-ostree install \
    [https://mirrors.rpmfusion.org/free/fedora/rpmfusion-free-release-$(rpm](https://mirrors.rpmfusion.org/free/fedora/rpmfusion-free-release-$(rpm) -E %fedora).noarch.rpm \
    [https://mirrors.rpmfusion.org/nonfree/fedora/rpmfusion-nonfree-release-$(rpm](https://mirrors.rpmfusion.org/nonfree/fedora/rpmfusion-nonfree-release-$(rpm) -E %fedora).noarch.rpm \
    && rpm-ostree upgrade

# Make all copied scripts executable
RUN chmod +x /usr/local/bin/*

# Modify the base package set and install new packages
RUN dnf install -y \
    kitty \
    swaync \
    swaylock-effects \
    sway \ 
    swayimg \ 
    swaybg \ 
    rofi \ 
    waybar \ 
    kitty \ 
    wob \ 
    neovim \
    htop \
    nwg-look \
    && dnf clean all

