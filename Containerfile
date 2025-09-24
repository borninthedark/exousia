# Base Image
FROM localhost:5000/exousia:latest

# Add metadata for my custom bootc image
LABEL \
    name="exousia" \
    version="0.0.2" \
    author="Princeton Strong" \
    description="Fedora Atomic - Bootc Custom"

# --- Modify the Base Package Set ---
# Add RPM Fusion repos to the image
# Add RPM Fusion repos using dnf
RUN bash -c '\
    set -euo pipefail; \
    FEDORA_VERSION=$(rpm -E %fedora); \
    dnf install -y \
      https://mirrors.rpmfusion.org/free/fedora/rpmfusion-free-release-${FEDORA_VERSION}.noarch.rpm \
      https://mirrors.rpmfusion.org/nonfree/fedora/rpmfusion-nonfree-release-${FEDORA_VERSION}.noarch.rpm; \
    dnf clean all \
'

# Use rpm-ostree to remove or replace packages from the base image.
# For example, let's remove the default 'foot' terminal and replace 'dunst' notifications.
# RUN rpm-ostree override remove foot dunst \
#     && dnf install -y kitty swaync \
#     && dnf clean all

# --- Add Your Customizations Below ---
# RUN dnf install -y \
#    glances \
#    wob \
#    pam-u2f \ 
#    pamu2fcfg \ 
#    && dnf clean all

# --- Layer on Custom Configurations ---
# This copies your latest configs into the system-wide override directory.
# Since packages are already in the base, this is all we need to do.
COPY custom-configs/ /etc/sway/config.d/

# --- Add Custom Scripts ---
# Copy the contents of our local 'scripts' directory into the image
COPY scripts/ /usr/local/bin/

# Make all scripts in that directory executable
RUN chmod +x /usr/local/bin/*
