# Flatpak Installation Verification

This guide explains how to verify that flatpak applications are installed correctly on your Exousia image.

## Understanding the Installation Process

Exousia uses a two-phase approach for flatpak installation:

### Phase 1: Build Time

- ✅ Flathub remote is configured and downloaded
- ✅ Remote repository is registered with flatpak
- ✅ Flatpak binary and dependencies are included
- ✅ default-flatpaks module configuration is embedded

### Phase 2: First Boot

- 🚀 The `default-flatpaks` systemd service runs automatically
- 🚀 All configured flatpak applications are installed (~20+ apps)
- 🚀 All required runtimes are installed (Freedesktop, GNOME, KDE)
- 🚀 Codecs and platform extensions are installed

**Important:** Flatpak applications are NOT present in the container image itself. They are installed when the system boots for the first time.

## Verification Methods

### Method 1: Automated Verification Script (Recommended)

Run the built-in verification script:

```bash
sudo verify-flatpak-installation
```

This script will:

- Check if Flathub remote is configured
- Count installed applications and runtimes
- Verify core applications are present
- Check default-flatpaks service status
- Generate a detailed log file

**Output Example:**

```text
=========================================
Flatpak Installation Verification
=========================================

✓ Flathub remote is configured

Installed Applications:
  System: 24 apps
  User: 0 apps
✓ Flatpak applications are installed

Core applications:
  ✓ com.bitwarden.desktop
  ✓ org.mozilla.firefox
  ✓ org.videolan.VLC
  ✓ org.libreoffice.LibreOffice
  ✓ us.zoom.Zoom

Installed Runtimes: 15
✓ Flatpak runtimes are installed
=========================================
All checks passed!
=========================================
```

### Method 2: Manual Verification

#### Check Flathub Remote

```bash
flatpak remotes
```

Expected output should include `flathub`.

#### List Installed Applications

```bash
flatpak list --app
```

#### List Installed Runtimes

```bash
flatpak list --runtime
```

#### Check Specific Applications

```bash
flatpak list | grep -E "(firefox|chrome|vlc|libreoffice|zoom)"
```

Expected applications (from packages/common/flatpaks.yml):

- com.bitwarden.desktop
- com.github.tchx84.Flatseal
- com.google.Chrome
- com.obsproject.Studio
- org.mozilla.firefox
- org.videolan.VLC
- org.libreoffice.LibreOffice
- us.zoom.Zoom
- And 15+ more...

### Method 3: Check Service Status

Check if the default-flatpaks service has run:

```bash
systemctl status bluebuild-default-flatpaks.service
```

Or check journal logs:

```bash
journalctl -u bluebuild-default-flatpaks.service
```

## Testing on a Fresh Image

### Option 1: Boot with systemd-nspawn (Quick Test)

```bash
# Pull or load your built image
podman pull docker.io/1borninthedark/exousia:latest

# Export to a directory
mkdir -p /tmp/exousia-test
podman export $(podman create docker.io/1borninthedark/exousia:latest) | tar -C /tmp/exousia-test -xf -

# Boot with systemd-nspawn
sudo systemd-nspawn -D /tmp/exousia-test --boot

# After boot completes, check flatpaks
flatpak list --app
verify-flatpak-installation

# Exit when done
poweroff
```

### Option 2: Deploy to Virtual Machine

```bash
# Build and deploy with bootc
sudo bootc install to-filesystem --target-no-signature-verification /dev/vda

# Or use bootc-image-builder
sudo podman run --rm -it --privileged \
  --pull=newer \
  -v /var/lib/containers/storage:/var/lib/containers/storage \
  quay.io/centos-bootc/bootc-image-builder:latest \
  --type qcow2 \
  docker.io/1borninthedark/exousia:latest

# Boot the VM and verify
ssh user@vm-ip
verify-flatpak-installation
```

### Option 3: Deploy to Physical Hardware

After deploying to physical hardware:

1. Boot the system
2. Wait 2-5 minutes for first-boot services to complete
3. Log in
4. Run: `verify-flatpak-installation`

## Troubleshooting

### No Flatpaks Installed After Boot

**Symptom:** `flatpak list --app` returns empty or very few apps

**Check:**

```bash
# Is the service enabled?
systemctl is-enabled bluebuild-default-flatpaks.service

# Did the service run?
systemctl status bluebuild-default-flatpaks.service

# Check for errors in journal
journalctl -u bluebuild-default-flatpaks.service -b
```

**Fix:**

```bash
# Manually trigger the service
sudo systemctl start bluebuild-default-flatpaks.service

# Watch the logs
journalctl -u bluebuild-default-flatpaks.service -f
```

### Flathub Remote Not Configured

**Symptom:** `flatpak remotes` doesn't show flathub

**Fix:**

```bash
# Add Flathub remote manually
flatpak remote-add --if-not-exists flathub \
  https://flathub.org/repo/flathub.flatpakrepo

# For system-wide:
sudo flatpak remote-add --if-not-exists --system flathub \
  https://flathub.org/repo/flathub.flatpakrepo
```

### Service Not Found

**Symptom:** `systemctl status bluebuild-default-flatpaks.service` shows "not found"

**Check:**
The service name may vary depending on the BlueBuild version. Try:

```bash
systemctl list-units | grep -i flatpak
systemctl list-unit-files | grep -i flatpak
```

**Alternative:**
If the service doesn't exist, you can manually install flatpaks using the list from `packages/common/flatpaks.yml`:

```bash
# Install core apps
flatpak install -y flathub com.bitwarden.desktop
flatpak install -y flathub org.mozilla.firefox
flatpak install -y flathub org.videolan.VLC
# ... etc
```

### Installation in Progress

**Symptom:** Some apps are installed but not all

**Explanation:** Flatpak installation can take 5-15 minutes depending on network speed and number of packages.

**Check Progress:**

```bash
# Watch the journal in real-time
journalctl -u bluebuild-default-flatpaks.service -f

# Monitor flatpak processes
ps aux | grep flatpak

# Check network activity
sudo iftop
```

## Build-Time Tests

The repository includes automated tests in `custom-tests/image_content.bats` that verify:

1. **Flathub remote is configured** (line 525)
2. **Flathub flatpakrepo file exists** (line 532)
3. **Flatpak binary is available** (line 537)
4. **Can query Flathub remote** (line 548)
5. **Configuration file is present** (line 554)
6. **Verification script exists** (line 561)

These tests run during the CI/CD build process and verify that the image is correctly configured for flatpak installation at boot time.

## Expected Timeline

| Time After Boot | Expected State |
|-----------------|---------------|
| 0-2 minutes | System booting, services starting |
| 2-3 minutes | default-flatpaks service starts |
| 3-8 minutes | Flatpak applications downloading and installing |
| 8-15 minutes | All applications and runtimes installed |

Large applications like Blender, LibreOffice, and GIMP can take several minutes each to download and install.

## Logs and Diagnostics

### Verification Log

```bash
cat /var/log/flatpak-installation-verification.log
```

### Service Logs

```bash
# All flatpak-related services
journalctl -b | grep -i flatpak

# Specific service
journalctl -u bluebuild-default-flatpaks.service --no-pager

# Since last boot
journalctl -u bluebuild-default-flatpaks.service -b
```

### System Status

```bash
# Overall system boot time
systemd-analyze

# Service startup times
systemd-analyze blame | grep flatpak
```

## References

- [BlueBuild default-flatpaks Module](https://blue-build.org/reference/modules/default-flatpaks/)
- [Flatpak Documentation](https://docs.flatpak.org/)
- [Exousia Flatpak Configuration](../packages/common/flatpaks.yml)
