# Build Tools

Python tools for managing the Exousia bootc image build process.

## Tools

| Script | Purpose |
|--------|---------|
| `yaml-to-containerfile.py` | Transpiles YAML blueprints into Containerfiles |
| `resolve_build_config.py` | Resolves CI build parameters from inputs and `adnyeus.yml` |
| `package_loader.py` | Loads and merges YAML package definitions for the transpiler |
| `validate_installed_packages.py` | Validates package sets against the generated Containerfile |
| `package_dependency_checker.py` | Checks for missing or conflicting package dependencies |
| `yaml_selector_service.py` | Selects the correct YAML definition for a given build target |
| `constants.py` | Shared constants and enums (`ImageType`, `BuildStatus`) |
| `distro_mapper.py` | Maps image types to base images and package managers |
| `copr_manager.py` | Manages Copr repository integration |
| `dry_check.py` | DRY enforcement -- detects code duplication via AST analysis |

## Usage

All commands use `uv run` (never raw `python` or `pip`):

```bash
# Generate a Containerfile from the blueprint
uv run python tools/yaml-to-containerfile.py \
  --config adnyeus.yml \
  --output Dockerfile.generated

# Validate config without generating output
uv run python tools/yaml-to-containerfile.py \
  --config adnyeus.yml \
  --validate

# Specify image type and Fedora version
uv run python tools/yaml-to-containerfile.py \
  --config adnyeus.yml \
  --image-type fedora-sway-atomic \
  --fedora-version 43 \
  --output Dockerfile.generated

# Run DRY check on tools/
uv run python tools/dry_check.py --functions-only --path tools
```

## CLI Options (yaml-to-containerfile.py)

| Option | Description | Default |
|--------|-------------|---------|
| `-c, --config PATH` | Path to YAML configuration file | Required |
| `-o, --output PATH` | Output Containerfile path | stdout |
| `--image-type TYPE` | Base image type | From config |
| `--fedora-version VER` | Fedora version number | `43` |
| `--enable-plymouth` | Enable Plymouth boot splash | `true` |
| `--disable-plymouth` | Disable Plymouth boot splash | -- |
| `--validate` | Validate config only | -- |
| `-v, --verbose` | Verbose output | -- |

## Tests

| Test File | Covers |
|-----------|--------|
| `test_yaml_to_containerfile.py` | Transpiler output, module rendering, conditionals |
| `test_package_loader.py` | Package loading, merging, YAML parsing |
| `test_distro_mapper.py` | Image type to base image mapping |
| `test_package_dependency_checker.py` | Dependency resolution and conflict detection |
| `test_build_zfs_kmod.py` | ZFS kernel module build script |

Run tests:

```bash
uv run pytest tools/ -q --tb=short
```

## Supported Image Types

- `fedora-bootc` -- Minimal Fedora bootc base
- `fedora-sway-atomic` -- Sway Wayland desktop

## See Also

- [Blueprint](../adnyeus.yml) -- Main build configuration
- [Package Definitions](../overlays/base/packages/) -- YAML package lists
- [Overlay System](../docs/overlay-system.md) -- How overlays map into images
