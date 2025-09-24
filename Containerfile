# Base Image
FROM localhost:500/exousia:latest

# Add metadata for my custom bootc image
LABEL \
    name="exousia" \
    version="0.0.2" \
    author="Princeton Strong" \
    description="Fedora Atomic - Bootc Custom"

# --- Add Your Customizations Below ---
RUN dnf install -y \
    glances \
    pam-u2f \ 
    pamu2fcfg \ 
    && dnf clean all

# --- Layer on Custom Configurations ---
# This copies your latest configs into the system-wide override directory.
# Since packages are already in the base, this is all we need to do.
COPY custom-configs/ /etc/sway/config.d/

# --- Add Custom Scripts ---
# Copy the contents of our local 'scripts' directory into the image
COPY scripts/ /usr/local/bin/

# Make all scripts in that directory executable
RUN chmod +x /usr/local/bin/*
