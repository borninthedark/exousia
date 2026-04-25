# Build Tools

Python tools for managing the Exousia bootc image build process.

## Tools

| Tool | Purpose |
|------|---------|
| `generator/` | Transpiler package for YAML blueprints to Containerfiles (`uv run python -m generator`) |
| `resolve_build_config.py` | Resolves CI build parameters from inputs and `adnyeus.yml` |
| `package_loader/` | Package-loader package for typed YAML package definitions (`uv run python -m package_loader`) |
| `generate-readme.py` | Auto-generates README.md from build configuration (pre-commit hook) |
| `dry_check.py` | DRY enforcement -- detects code duplication via AST analysis |

## Usage

All commands use `uv run` (never raw `python` or `pip`):

```bash
# Generate a Containerfile from the blueprint
uv run python -m generator \
  --config adnyeus.yml \
  --resolved-package-plan build/resolved-build-plan.json \
  --output Dockerfile.generated

# Validate config without generating output
uv run python -m generator \
  --config adnyeus.yml \
  --validate

# Specify image type and Fedora version
uv run python -m generator \
  --config adnyeus.yml \
  --image-type fedora-sway-atomic \
  --fedora-version 44 \
  --resolved-package-plan build/resolved-build-plan.json \
  --output Dockerfile.generated

# Inspect the resolved package selection and provenance directly
uv run python -m package_loader --wm sway --json

# Run DRY check on tools/
uv run python tools/dry_check.py --functions-only --path tools
```

## CLI Options (`uv run python -m generator`)

| Option | Description | Default |
|--------|-------------|---------|
| `-c, --config PATH` | Path to YAML configuration file | Required |
| `-o, --output PATH` | Output Containerfile path | stdout |
| `--image-type TYPE` | Base image type | From config |
| `--fedora-version VER` | Fedora version number (for example `43`, `44`, or `rawhide`) | `43` |
| `--resolved-package-plan PATH` | Write resolved package plan JSON | -- |
| `--enable-plymouth` | Enable Plymouth boot splash | `true` |
| `--disable-plymouth` | Disable Plymouth boot splash | -- |
| `--validate` | Validate config only | -- |
| `-v, --verbose` | Verbose output | -- |

## CLI Options (`uv run python -m package_loader`)

| Option | Description | Default |
|--------|-------------|---------|
| `--wm NAME` | Resolve packages for a window manager | -- |
| `--de NAME` | Resolve packages for a desktop environment | -- |
| `--json` | Print normalized resolved package plan JSON | -- |
| `--common NAME` | Include a specific common package set; repeatable | Default `base-*` bundle set when omitted |
| `--feature NAME` | Include a specific feature package set; repeatable | -- |
| `--export` | Write legacy `packages.add` and `packages.remove` files | -- |
| `--output-dir PATH` | Output directory for legacy export mode | `custom-pkgs/` |
| `--list-wms` | List available window-manager definitions | -- |
| `--list-des` | List available desktop-environment definitions | -- |

Notes:

- `--json` is the easiest way to inspect RPM and DNF group provenance.
- If you pass `--common`, the default common bundle set is not added implicitly.
- Use explicit bundle names like `base-core`; `base` is a logical aggregate, not a real bundle file.

## Tests

| Test File | Covers |
|-----------|--------|
| `test_yaml_to_containerfile.py` | Transpiler output, module rendering, conditionals |
| `test_package_loader.py` | Package loading, merging, YAML parsing |
| `test_distro_mapper.py` | Image type to base image mapping |
| `test_package_dependency_checker.py` | Dependency resolution and conflict detection |
| `test_dry_check.py` | DRY enforcement tool |
| `test_resolve_build_config.py` | CI build parameter resolution |

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
