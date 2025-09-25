# Base Image
FROM quay.io/fedora/fedora-sway-atomic:43

# --- Layer on Custom Configurations ---
COPY custom-configs/ /etc/sway/config.d/
COPY custom-repos/ /etc/yum.repos.d/
COPY custom-scripts/ /usr/local/bin/

# --- Make Scripts Executable ---
RUN chmod +x /usr/local/bin/*

# This creates a group
RUN groupadd libvirt 

# --- Install DNF5 and Replace DNF ---
RUN dnf install -y dnf5 dnf5-plugins \
    && rm -f /usr/bin/dnf \
    && ln -s /usr/bin/dnf5 /usr/bin/dnf

# --- Update Base Packages ---
RUN dnf upgrade -y

# --- Add RPM Fusion and Enable Cisco OpenH264 ---
RUN bash -c '\
    set -euo pipefail; \
    FEDORA_VERSION=$(rpm -E %fedora); \
    dnf install -y \
      https://mirrors.rpmfusion.org/free/fedora/rpmfusion-free-release-${FEDORA_VERSION}.noarch.rpm \
      https://mirrors.rpmfusion.org/nonfree/fedora/rpmfusion-nonfree-release-${FEDORA_VERSION}.noarch.rpm; \
    dnf config-manager setopt fedora-cisco-openh264.enabled=1; \
    dnf clean all'
    
# --- Remove or Replace Base Packages via rpm-ostree ---
RUN rpm-ostree override remove foot dunst \
    && dnf install -y kitty swaync \
    && dnf clean all

# --- Install Custom Packages ---
RUN dnf install -y \
    wob \
    bat \ 
    chezmoi \
    lsd \ 
    fzf \ 
    direnv \ 
    neovim \
    distrobox \
    wireguard-tools \
    btop \
    fastfetch \ 
    virt-manager \ 
    qemu-kvm \ 
    htop \
    nwg-look \
    glances \
    pam-u2f \
    pamu2fcfg \
    && dnf clean all

# --- Configure Flathub ---
RUN flatpak remote-add --if-not-exists flathub https://flathub.org/repo/flathub.flatpakrepo

