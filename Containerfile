# ------------------------------
# Base image
# ------------------------------
FROM quay.io/fedora/fedora-sway-atomic:43
LABEL maintainer="uryu"

# ------------------------------
# Copy all inputs first
# ------------------------------
COPY --chmod=0644 ./custom-pkgs/packages.remove /usr/local/share/sericea-bootc/packages-removed
COPY --chmod=0644 ./custom-pkgs/packages.add    /usr/local/share/sericea-bootc/packages-added
COPY --chmod=0644 custom-configs/plymouth/themes/bgrt-better-luks/ /usr/share/plymouth/themes/bgrt-better-luks/
COPY --chmod=0644 custom-repos/*.repo           /etc/yum.repos.d/
COPY --chmod=0644 custom-configs/               /etc/
COPY --chmod=0755 custom-scripts/               /usr/local/bin/

# ------------------------------
# Package lists
# ------------------------------
RUN jq -r .packages[] /usr/share/rpm-ostree/treefile.json \
    > /usr/local/share/sericea-bootc/packages-fedora-bootc

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
# Lint Container
# ------------------------------
RUN bootc container lint
