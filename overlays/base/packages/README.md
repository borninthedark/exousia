# Package Definitions

YAML-based package definitions for Exousia bootc images.

## Structure

```text
packages/
├── common/            # Shared package sets
│   ├── base.yml       # Base packages for all builds
│   ├── flatpaks.yml   # Flatpak applications (installed at first boot)
│   └── remove.yml     # Packages to remove before installs
└── window-managers/
    └── sway.yml       # Sway WM packages
```

## How It Works

The `package_loader.py` tool reads these YAML files during transpilation.
Removal lists (`remove.yml`) are processed before installs to avoid conflicts.

```yaml
# In adnyeus.yml
modules:
  - type: package-loader
    window_manager: sway
    include_common: true
```

## Package Format

```yaml
metadata:
  name: package-set-name
  type: window-manager | common
  description: Description of the package set

core:
  - package1
  - package2

terminals:
  - terminal-emulator
```

## Categories

| Category | Purpose |
|----------|---------|
| `core` | Essential components |
| `terminals` | Terminal emulators |
| `launchers` | Application launchers |
| `notifications` | Notification daemons |
| `display_manager` | Login managers |
| `wayland` | Wayland protocol components |
| `session` | Session and authentication |
| `audio` | Audio subsystem |
| `graphics` | Graphics drivers |
| `fonts` | Font packages |
| `file_manager` | File managers |
| `media` | Media viewers and players |
| `system_controls` | System control utilities |
| `bluetooth` | Bluetooth support |
| `power` | Power management |
| `theme` | Theme and appearance |
| `utilities` | Miscellaneous utilities |
| `boot_splash` | Boot splash screen |

## Inspecting Packages

```bash
uv run python tools/package_loader.py --list-wms
uv run python tools/package_loader.py --wm sway
```

## See Also

- [Build Tools](../../../tools/) -- Transpiler and package loader
- [Blueprint](../../../adnyeus.yml) -- Main build configuration
