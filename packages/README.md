# Exousia Package Definitions

This directory contains YAML-based package definitions for different desktop environments, window managers, and common package sets.

## Directory Structure

```
packages/
├── window-managers/    # Tiling window managers
│   └── sway.yml       # Sway WM packages
├── desktop-environments/  # Full desktop environments
│   ├── kde.yml        # KDE Plasma DE packages
│   └── mate.yml       # MATE DE packages
└── common/            # Shared package sets
    ├── base.yml       # Base packages for all builds
    └── remove.yml     # Packages to remove
```

## Package Definition Format

Each YAML file follows this structure:

```yaml
# Metadata
metadata:
  name: package-set-name
  type: window-manager | desktop-environment | common
  description: Description of the package set

# Package groups (for Fedora-based distros - optional)
# These are installed via `dnf install @group-name`
groups:
  - package-group-name

# Package categories (organized by purpose)
category_name:
  - package1
  - package2
  - package3

another_category:
  - package4
  - package5
```

### Package Groups

Package groups provide a convenient way to install sets of related packages on Fedora-based systems:

- **Fedora distros**: Groups are installed via `dnf install -y @group-name`
- **Scope**: fedora-bootc, fedora-sway-atomic, fedora-kinoite, and all Fedora Atomic variants
- **Other distros**: Previously listed options (Arch, Debian, Ubuntu, openSUSE, Gentoo) have been removed from the toolchain for now and will be revisited later.

Example groups:
- `@kde-desktop-environment` - Full KDE Plasma desktop
- `@mate-desktop` - MATE desktop environment
- Custom groups defined in your distro's repositories

## Using Package Definitions

### In Build Configurations

To use a window manager or desktop environment in your build configuration:

```yaml
# Desktop environment selection
desktop:
  window_manager: sway
  # OR
  # desktop_environment: kde  # Options: kde, mate
  include_common: true  # Include common base packages

# Then use the package-loader module
modules:
  - type: package-loader
    window_manager: sway  # or use desktop_environment: kde
    include_common: true
```

**Note**: On Fedora-based distros, desktop environments with groups (like KDE and MATE) will use efficient group installs (`@kde-desktop-environment`, `@mate-desktop`), automatically including all necessary packages. Individual packages are still installed for fine-tuning beyond the group.

### Command Line Tool

The `package_loader.py` tool can be used to inspect and export package lists:

```bash
# List available window managers
python3 tools/package_loader.py --list-wms

# List available desktop environments
python3 tools/package_loader.py --list-des

# Show packages for Sway
python3 tools/package_loader.py --wm sway

# Show packages for GNOME
python3 tools/package_loader.py --de gnome

# Export to legacy text files
python3 tools/package_loader.py --wm sway --export --output-dir custom-pkgs/
```

## Adding New Window Managers or Desktop Environments

1. Create a new YAML file in the appropriate directory:
   - Window managers: `packages/window-managers/your-wm.yml`
   - Desktop environments: `packages/desktop-environments/your-de.yml`

2. Define packages using the standard format with categories:

```yaml
metadata:
  name: your-wm
  type: window-manager
  description: Your window manager description
  homepage: https://example.com

core:
  - your-wm-package

terminals:
  - terminal-emulator

# ... more categories
```

3. Use it in your build configuration:

```yaml
desktop:
  window_manager: your-wm
```

## Package Categories

Common categories used across definitions:

- `core`: Essential components
- `terminals`: Terminal emulators
- `launchers`: Application launchers
- `notifications`: Notification daemons
- `display_manager`: Login managers
- `wayland`: Wayland protocol components
- `session`: Session and authentication
- `audio`: Audio subsystem
- `graphics`: Graphics drivers
- `fonts`: Font packages
- `file_manager`: File managers
- `media`: Media viewers and players
- `screenshot`: Screenshot tools
- `system_controls`: System control utilities
- `bluetooth`: Bluetooth support
- `power`: Power management
- `theme`: Theme and appearance
- `utilities`: Miscellaneous utilities
- `boot_splash`: Boot splash screen

## Switching Between DEs/WMs

To switch between different desktop environments or window managers:

1. **Update your build configuration YAML:**
   ```yaml
   desktop:
     window_manager: sway  # Or set desktop_environment: kde
   ```

2. **Generate a new Containerfile:**
   ```bash
   python3 tools/yaml-to-containerfile.py \
     --config yaml-definitions/your-config.yml \
     --image-type fedora-bootc \
     --output Containerfile.generated
   ```

3. **Build the new image:**
   ```bash
   buildah bud -f Containerfile.generated -t your-image:tag .
   ```

## Distro Support

The package loader targets Fedora images, with configurations focused on Sway and LXQt builds.
Different package managers are automatically selected based on the distro, though Fedora is the only supported target today.
