# Base bootc image
FROM quay.io/fedora/fedora-bootc:42
MAINTAINER uryu

# --- Filesystem setup from fedora-bootc ---
RUN rmdir /opt && ln -s -T /var/opt /opt
RUN mkdir /var/roothome

# --- Package lists ---
COPY --chmod=0644 ./custom-pkgs/packages.remove /usr/local/share/sericea-bootc/packages-removed
COPY --chmod=0644 ./custom-pkgs/packages.add /usr/local/share/sericea-bootc/packages-added
RUN jq -r .packages[] /usr/share/rpm-ostree/treefile.json > /usr/local/share/sericea-bootc/packages-fedora-bootc

# --- Repositories ---
RUN dnf install -y dnf5 dnf5-plugins \
    && rm -f /usr/bin/dnf \
    && ln -s /usr/bin/dnf5 /usr/bin/dnf
    
COPY custom-repos/*.repo /etc/yum.repos.d/

RUN bash -c '\
    set -euo pipefail; \
    FEDORA_VERSION=$(rpm -E %fedora); \
    dnf install -y \
      https://mirrors.rpmfusion.org/free/fedora/rpmfusion-free-release-${FEDORA_VERSION}.noarch.rpm \
      https://mirrors.rpmfusion.org/nonfree/fedora/rpmfusion-nonfree-release-${FEDORA_VERSION}.noarch.rpm; \
    dnf config-manager --setopt=fedora-cisco-openh264.enabled=1; \
    dnf clean all'

# --- System Upgrade ---
RUN dnf upgrade -y

# --- Base Environment & Auth ---
RUN dnf -y install @sway-desktop-environment waybar grim slurp mako wl-clipboard kanshi && dnf clean all
RUN dnf -y install pam-u2f pamu2fcfg libfido2 && dnf clean all

RUN dnf -y install authselect && mkdir -p /etc/authselect/custom/u2f-system
COPY --chmod=0644 ./custom-configs/authselect/* /etc/authselect/custom/u2f-system/

RUN groupadd libvirt

# --- Apply Custom Package Lists ---
RUN grep -vE '^#' /usr/local/share/sericea-bootc/packages-removed | xargs dnf -y remove || true
RUN grep -vE '^#' /usr/local/share/sericea-bootc/packages-added | xargs dnf -y install --allowerasing || true
RUN dnf -y autoremove && dnf clean all

# --- Configs & Scripts ---
COPY ./custom-configs/sway/* /etc/sway/config.d/
COPY --chmod=0755 ./custom-scripts/* /usr/local/bin/

# --- Configure Flathub ---
RUN flatpak remote-add --if-not-exists flathub https://flathub.org/repo/flathub.flatpakrepo

# --- Users & Auth Setup ---
COPY --chmod=0755 ./custom-scripts/setup/* /tmp/scripts/
RUN /tmp/scripts/config-users
RUN /tmp/scripts/config-authselect && rm -r /tmp/scripts

# --- Systemd services ---
COPY --chmod=0644 ./custom-configs/systemd/* /usr/lib/systemd/system/
RUN systemctl enable firstboot-setup.service || true
RUN systemctl enable bootloader-update.service || true
RUN systemctl mask bootc-fetch-apply-updates.timer || true

# --- Cleanup + Verify ---
RUN find /var/log -type f ! -empty -delete
RUN bootc container lint