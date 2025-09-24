# Start from the minimal, generic Fedora bootc base image
FROM quay.io/fedora/fedora-bootc:42

# Add metadata for the base image
LABEL \
    name="exousia" \
    version="2.2.0" \
    author="Princeton Strong" \
    description="A bespoke Sway OS, built from a minimal bootc base with DNF5 and SDDM."

# --- Stage 1: Add All Local Files ---
COPY custom-repos/ /etc/yum.repos.d/
COPY custom-configs/ /etc/sway/config.d/
COPY scripts/ /usr/local/bin/

# --- Stage 2: Execute System Modifications ---

# First, make all copied scripts executable.
RUN chmod +x /usr/local/bin/*

# Second, install dnf5 and create a system-wide alias to it.
RUN dnf install -y dnf5 dnf5-plugins \
    && rm -f /usr/bin/dnf \
    && ln -s /usr/bin/dnf5 /usr/bin/dnf

# Third, update all packages.
RUN dnf upgrade -y

# Fourth, enable RPM Fusion and Cisco OpenH264 repo.
RUN dnf install -y \
    https://mirrors.rpmfusion.org/free/fedora/rpmfusion-free-release-$(rpm -E %fedora).noarch.rpm \
    https://mirrors.rpmfusion.org/nonfree/fedora/rpmfusion-nonfree-release-$(rpm -E %fedora).noarch.rpm \
    && dnf config-manager setopt fedora-cisco-openh264.enabled=1

# Install Sway desktop stack + SDDM
RUN dnf install -y \
    sway \
    swaybg \
    swayimg \
    waybar \
    rofi \
    wob \
    kitty \
    neovim \
    htop \
    nwg-look \
    swaync \
    sddm \
    && dnf swap -y swaylock swaylock-effects \
    && dnf clean all

# Block Swaylock 
RUN echo "exclude=swaylock" >> /etc/dnf/dnf.conf

# Enable graphical boot and set SDDM as the display manager
RUN systemctl set-default graphical.target && \
    systemctl enable sddm.service

# Ensure SDDM uses Sway as the default session
RUN mkdir -p /usr/share/wayland-sessions && \
    echo "[Desktop Entry]\n\
Name=Sway\n\
Comment=An i3-compatible Wayland compositor\n\
Exec=sway\n\
Type=Application\n\
DesktopNames=Sway\n" > /usr/share/wayland-sessions/sway.desktop

