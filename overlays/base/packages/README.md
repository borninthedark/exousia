# Package Definitions

YAML-based package definitions for Exousia bootc images.

## Structure

```text
packages/
├── common/            # Shared package sets
│   ├── base-core.yml
│   ├── base-devtools.yml
│   ├── base-media.yml
│   ├── base-network.yml
│   ├── base-security.yml
│   ├── base-shell.yml
│   ├── base-virtualization.yml
│   ├── audio-production.yml
│   ├── zfs.yml
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
    common_bundles:
      - base-core
      - base-shell
    feature_bundles:
      - audio-production
```

## Package Format

```yaml
apiVersion: exousia.packages/v1alpha1
kind: PackageBundle

metadata:
  name: package-set-name
  type: window-manager | common
  description: Description of the package set

spec:
  source: rpm
  stage: build
  packages:
    - package1
    - package2
  groups:
    install:
      - workstation-product-environment
    remove: []
  conflicts:
    packages: []
    features: []
  requires:
    features: []
```

## Bundle Selection

- `common_bundles` selects shared RPM bundles for the image
- `feature_bundles` selects optional features such as audio or ZFS
- Fedora package groups can be installed or removed declaratively through `spec.groups`
- The transpiler emits `dnf5` group actions and RPM operations from the resolved package plan

## Inspecting Packages

```bash
uv run python tools/package_loader.py --list-wms
uv run python tools/package_loader.py --wm sway --common-bundle base-core --common-bundle base-shell
uv run python tools/package_loader.py --wm sway --common-bundle base-core --feature-bundle audio-production --json
```

## See Also

- [Build Tools](../../../tools/) -- Transpiler and package loader
- [Blueprint](../../../adnyeus.yml) -- Main build configuration
