# ------------------------------
# Base image
# ------------------------------
FROM quay.io/fedora/fedora-sway-atomic:43
LABEL maintainer="uryu"

# ------------------------------
# Detect base image type for conditional logic
# ------------------------------
ARG BASE_IMAGE_TYPE="auto"
RUN if [ "$BASE_IMAGE_TYPE" = "auto" ]; then \
        if rpm -q sway 2>/dev/null; then \
            echo "fedora-sway-atomic" > /tmp/base-image-type; \
        else \
            echo "fedora-bootc" > /tmp/base-image-type; \
        fi; \
    else \
        echo "$BASE_IMAGE_TYPE" > /tmp/base-image-type; \
    fi && \
    echo "Detected base image type: $(cat /tmp/base-image-type)"

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
    BASE_TYPE=$(cat /tmp/base-image-type); \
    dnf install -y dnf5 dnf5-plugins && \
    rm -f /usr/bin/dnf && ln -s /usr/bin/dnf5 /usr/bin/dnf; \
    FEDORA_VERSION=$(rpm -E %fedora); \
    dnf install -y \
      https://mirrors.rpmfusion.org/free/fedora/rpmfusion-free-release-${FEDORA_VERSION}.noarch.rpm \
      https://mirrors.rpmfusion.org/nonfree/fedora/rpmfusion-nonfree-release-${FEDORA_VERSION}.noarch.rpm; \
    dnf config-manager setopt fedora-cisco-openh264.enabled=1; \
    if [ "$BASE_TYPE" = "fedora-bootc" ]; then \
        echo "Installing desktop packages for fedora-bootc base..."; \
        grep -vE '^#' /usr/local/share/sericea-bootc/packages-desktop | xargs -r dnf install -y; \
    fi; \
    grep -vE '^#' /usr/local/share/sericea-bootc/packages-added | xargs -r dnf install -y; \
    grep -vE '^#' /usr/local/share/sericea-bootc/packages-removed | xargs -r dnf remove -y; \
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
RUN ln -sf /tmp /var/tmp

# Add plymouth to dracut modules
RUN cat <<EOF >> /usr/lib/dracut/dracut.conf.d/plymouth.conf
add_dracutmodules+=" plymouth "
EOF

# Set default plymouth theme to our custom theme
RUN plymouth-set-default-theme bgrt-better-luks

# Rebuild initramfs with plymouth support
RUN set -x; \
    kver=\$(cd /usr/lib/modules && echo *); \
    dracut -vf /usr/lib/modules/\$kver/initramfs.img \$kver

# Add kernel arguments for plymouth
RUN mkdir -p /usr/lib/bootc/kargs.d && \
    cat <<EOF >> /usr/lib/bootc/kargs.d/plymouth.toml
kargs = ["splash", "quiet"]
match-architectures = ["x86_64", "aarch64"]
EOF

# ------------------------------
# Enable systemd services based on base image type
# ------------------------------
RUN BASE_TYPE=$(cat /tmp/base-image-type); \
    if [ "$BASE_TYPE" = "fedora-bootc" ]; then \
        echo "Enabling services for fedora-bootc base..."; \
        systemctl set-default graphical.target; \
        systemctl enable greetd.service; \
        systemctl enable libvirtd.service; \
        systemctl enable systemd-resolved.service; \
        systemctl enable NetworkManager.service; \
        echo "Services enabled: graphical.target (default), greetd, libvirtd, systemd-resolved, NetworkManager"; \
    else \
        echo "Skipping service enablement - using fedora-sway-atomic defaults"; \
    fi && \
    rm -f /tmp/base-image-type

# ------------------------------
# Lint Container
# ------------------------------
RUN bootc container lint