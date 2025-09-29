# ------------------------------
# Build arguments for base image selection
# ------------------------------
ARG FEDORA_VERSION=43
ARG IMAGE_TYPE=fedora-sway-atomic

# ------------------------------
# Base image - dynamically selected
# ------------------------------
FROM quay.io/fedora/${IMAGE_TYPE}:${FEDORA_VERSION}
LABEL maintainer="uryu"

# ------------------------------
# Set image type for conditional logic
# ------------------------------
ARG IMAGE_TYPE
ENV BUILD_IMAGE_TYPE=${IMAGE_TYPE}

# ------------------------------
# Unified Auth Strategy for Bootc & Podman 
# ------------------------------
COPY --chmod=0644 containers-auth.conf /usr/lib/tmpfiles.d/containers-auth.conf
COPY --chmod=0600 ./bootc-secrets/auth.json /usr/lib/container-auth.json 
RUN ln -sfr /usr/lib/container-auth.json /etc/ostree/auth.json
    
# ------------------------------
# Copy all inputs first
# ------------------------------
COPY --chmod=0644 ./custom-pkgs/packages.remove /usr/local/share/sericea-bootc/packages-removed
COPY --chmod=0644 ./custom-pkgs/packages.add    /usr/local/share/sericea-bootc/packages-added
COPY --chmod=0644 ./custom-pkgs/packages.desktop /usr/local/share/sericea-bootc/packages-desktop
COPY --chmod=0644 custom-configs/plymouth/themes/bgrt-better-luks/ /usr/share/plymouth/themes/bgrt-better-luks/
COPY --chmod=0644 custom-repos/*.repo           /etc/yum.repos.d/
COPY --chmod=0644 custom-configs/               /etc/
COPY --chmod=0755 custom-scripts/               /usr/local/bin/

# ------------------------------
# Package lists
# ------------------------------
RUN if [ -f /usr/share/rpm-ostree/treefile.json ]; then \
        jq -r .packages[] /usr/share/rpm-ostree/treefile.json \
        > /usr/local/share/sericea-bootc/packages-fedora-bootc; \
    else \
        touch /usr/local/share/sericea-bootc/packages-fedora-bootc; \
    fi

# ------------------------------
# DNF: Install, remove, upgrade, add repos in one layer
# ------------------------------
# hadolint ignore=DL3041,SC2086
RUN set -euxo pipefail; \
    dnf install -y dnf5 dnf5-plugins && \
    rm -f /usr/bin/dnf && ln -s /usr/bin/dnf5 /usr/bin/dnf; \
    FEDORA_VERSION=$(rpm -E %fedora); \
    dnf install -y \
      https://mirrors.rpmfusion.org/free/fedora/rpmfusion-free-release-${FEDORA_VERSION}.noarch.rpm \
      https://mirrors.rpmfusion.org/nonfree/fedora/rpmfusion-nonfree-release-${FEDORA_VERSION}.noarch.rpm; \
    dnf config-manager setopt fedora-cisco-openh264.enabled=1; \
    if [ "$BUILD_IMAGE_TYPE" = "fedora-bootc" ]; then \
        echo "==> Building from fedora-bootc base - installing desktop packages..."; \
        grep -vE '^#|^$' /usr/local/share/sericea-bootc/packages-desktop | xargs -r dnf install -y; \
    else \
        echo "==> Building from fedora-sway-atomic - skipping desktop packages (already included)"; \
    fi; \
    echo "==> Installing custom packages from packages.add..."; \
    grep -vE '^#|^$' /usr/local/share/sericea-bootc/packages-added | xargs -r dnf install -y; \
    echo "==> Removing packages from packages.remove..."; \
    grep -vE '^#|^$' /usr/local/share/sericea-bootc/packages-removed | xargs -r dnf remove -y; \
    dnf upgrade -y; \
    dnf clean all

# ------------------------------
# Add Flathub
# ------------------------------
# hadolint ignore=DL3059
RUN flatpak remote-add --if-not-exists flathub https://flathub.org/repo/flathub.flatpakrepo

# ------------------------------
# Configure Plymouth boot splash
# ------------------------------
# Remove existing /var/tmp directory and create symlink to /tmp
RUN rm -rf /var/tmp && ln -sf /tmp /var/tmp

# Add plymouth to dracut modules
RUN echo 'add_dracutmodules+=" plymouth "' >> /usr/lib/dracut/dracut.conf.d/plymouth.conf

# Set default plymouth theme to our custom theme
RUN plymouth-set-default-theme bgrt-better-luks

# Rebuild initramfs with plymouth support
# hadolint ignore=DL3003
RUN set -x; \
    kver=$(cd /usr/lib/modules && echo *); \
    dracut -vf /usr/lib/modules/$kver/initramfs.img $kver

# Add kernel arguments for plymouth
RUN mkdir -p /usr/lib/bootc/kargs.d && \
    printf 'kargs = ["splash", "quiet"]\nmatch-architectures = ["x86_64", "aarch64"]\n' \
    > /usr/lib/bootc/kargs.d/plymouth.toml

# ------------------------------
# Enable systemd services based on base image type
# ------------------------------
RUN if [ "$BUILD_IMAGE_TYPE" = "fedora-bootc" ]; then \
        echo "==> Enabling services for fedora-bootc base..."; \
        systemctl set-default graphical.target; \
        systemctl enable greetd.service; \
        systemctl enable libvirtd.service; \
        systemctl enable systemd-resolved.service; \
        systemctl enable NetworkManager.service; \
        echo "==> Services enabled: graphical.target (default), greetd, libvirtd, systemd-resolved, NetworkManager"; \
    else \
        echo "==> Skipping service enablement - using fedora-sway-atomic defaults"; \
    fi

# ------------------------------
# Lint Container
# ------------------------------
RUN bootc container lint