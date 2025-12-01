# Exousia Package Definitions

This directory contains YAML-based package definitions for different desktop environments, window managers, and common package sets.

## Directory Structure

```
packages/
├── window-managers/    # Tiling window managers
│   ├── sway.yml       # Sway WM packages
│   └── hyprland.yml   # Hyprland WM packages
├── desktop-environments/  # Full desktop environments
│   └── gnome.yml      # GNOME DE packages
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

# Package groups (organized by category)
category_name:
  - package1
  - package2
  - package3

another_category:
  - package4
  - package5
```

## Using Package Definitions

### In Build Configurations

To use a window manager or desktop environment in your build configuration:

```yaml
# Desktop environment selection
desktop:
  window_manager: sway  # Options: sway, hyprland
  # OR
  # desktop_environment: gnome  # Options: gnome
  include_common: true  # Include common base packages

# Then use the package-loader module
modules:
  - type: package-loader
    window_manager: sway
    include_common: true
```

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
     window_manager: hyprland  # Change from 'sway' to 'hyprland'
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

The package loader supports multiple distributions through the transpiler:

- Fedora (fedora-bootc, fedora-sway-atomic, fedora-kinoite, etc.)
- Arch (via bootcrew)
- Debian (via bootcrew)
- Ubuntu (via bootcrew)
- openSUSE (via bootcrew)
- Gentoo (via bootcrew)

Different package managers are automatically selected based on the distro.
