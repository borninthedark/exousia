# Application Package Management

This guide explains how applications are managed in Exousia images.

## Package Installation Approach

Exousia uses **native DNF/RPM packages** for all applications, installed during the CI build process. This provides better reliability, smaller images, and immediate availability compared to container-based approaches like Flatpak.

## Installation Process

### Build Time (CI)
- ✅ Applications installed from Fedora repositories
- ✅ Additional applications from RPMFusion (free/nonfree)
- ✅ All dependencies resolved and included
- ✅ Applications immediately available in built image

**Benefits:**
- No first-boot installation delays
- Better system integration
- Smaller image size (no runtime overhead)
- Verified during CI tests

## Installed Applications

Applications are defined in `packages/common/applications.yml`:

### Browsers
- **Firefox** - Mozilla's web browser
- **Chromium** - Open-source web browser

### Development Tools
- **Kate** - Advanced text editor
- **Filezilla** - FTP client

### Media & Graphics
- **OBS Studio** - Video recording and streaming
- **Audacity** - Audio editor
- **Blender** - 3D creation suite
- **GIMP** - Image editor
- **VLC** - Media player
- **Mixxx** - DJ software

### Utilities
- **Transmission** - BitTorrent client
- **Remmina** - Remote desktop client
- **Flameshot** - Screenshot tool
- **Quassel** - IRC client
- **Haruna** - Video player (KDE)

## Verification

Verify packages are installed:

```bash
# Check specific package
rpm -q firefox

# List all installed applications
rpm -qa | grep -E "firefox|chromium|gimp|vlc"

# Verify from packages/common/applications.yml
for app in firefox chromium kate gimp vlc; do
    rpm -q "$app" && echo "✓ $app" || echo "✗ $app missing"
done
```

## Adding New Applications

To add applications to your builds:

1. Edit `packages/common/applications.yml`:

```yaml
type: rpm-ostree

install:
  - firefox
  - chromium
  - your-new-application
```

2. Ensure the package is available in:
   - Fedora repositories (default)
   - RPMFusion free/nonfree (enabled by default)
   - Custom repositories (add to `custom-repos/`)

3. Commit and push - CI will build with new packages

## Package Sources

### Fedora Repositories
Standard Fedora packages from updates and stable repos.

### RPMFusion
Enabled by default for multimedia codecs and non-free software:
- **RPMFusion Free** - Open source multimedia
- **RPMFusion Nonfree** - Proprietary drivers and codecs

### Custom Repositories
Add `.repo` files to `custom-repos/` directory.

## Unavailable Applications

Some applications from the previous Flatpak configuration are not available as RPM packages:

- **Bitwarden** - Use browser extension or manual install from bitwarden.com
- **Google Chrome** - Use Chromium or add Google's repository
- **Zoom** - Add Zoom's repository or use web version
- **Zotero** - Use browser extension or manual install from zotero.org

## Troubleshooting

### Package Not Found

```bash
# Search for package
dnf search package-name

# Check available repositories
dnf repolist

# Check RPMFusion is enabled
rpm -q rpmfusion-free-release rpmfusion-nonfree-release
```

### Package Conflicts

If a package conflicts during build:

1. Check `packages/common/remove.yml` for removed packages
2. Review package dependencies: `dnf deplist package-name`
3. Consider alternative packages

### Build Failures

If CI build fails with package errors:

1. Check package availability: `dnf info package-name`
2. Verify repository URLs in workflow
3. Check for package renames or deprecations

## Migration Notes

**Previous Approach:** Flatpak packages installed on first boot via default-flatpaks module

**Current Approach:** Native RPM packages installed during build

**Why the change:**
- Flathub remote configuration wasn't persisting
- First-boot services were unreliable
- Native packages provide better integration
- Smaller images without runtime overhead
- Faster builds and more predictable results
