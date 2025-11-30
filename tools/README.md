# Exousia Build Tools

This directory contains tools for managing the Exousia bootc image build process using declarative YAML configuration.

## YAML to Containerfile Transpiler

The `yaml-to-containerfile.py` script converts a BlueBuild-compatible YAML configuration into a standard Containerfile format.

### Features

- **BlueBuild-inspired specification** - Compatible with BlueBuild module syntax
- **Multi-distro support** - Generate Containerfiles for:
  - **Fedora Atomic variants**: fedora-bootc, fedora-silverblue, fedora-kinoite, fedora-sway-atomic, and 7 community variants
  - **Bootcrew distros**: Arch Linux, Gentoo, Debian, Ubuntu, OpenSUSE, and Proxmox
- **Bootcrew-setup module** - Automated bootc source builds for non-Fedora distros with distro-specific optimizations
- **Conditional logic** - Support for image-type and distro-specific configurations
- **Plymouth integration** - Handle Plymouth configuration for all supported base images
- **Validation** - Built-in YAML schema validation

### Requirements

```bash
pip install pyyaml
```

### Usage

#### Basic Usage

Generate a Containerfile from YAML configuration:

```bash
python3 tools/yaml-to-containerfile.py \
  --config exousia.yml \
  --output Containerfile.generated
```

#### Specify Image Type

Generate for a specific base image type:

```bash
# For fedora-sway-atomic
python3 tools/yaml-to-containerfile.py \
  --config exousia.yml \
  --image-type fedora-sway-atomic \
  --output Containerfile.atomic.generated

# For fedora-bootc with Plymouth
python3 tools/yaml-to-containerfile.py \
  --config exousia.yml \
  --image-type fedora-bootc \
  --enable-plymouth \
  --output Containerfile.bootc.generated

# For Arch Linux bootc
python3 tools/yaml-to-containerfile.py \
  --config yaml-definitions/arch-bootc.yml \
  --image-type arch \
  --output Containerfile.arch

# For Debian bootc
python3 tools/yaml-to-containerfile.py \
  --config yaml-definitions/debian-bootc.yml \
  --image-type debian \
  --output Containerfile.debian
```

#### Validate Configuration

Validate YAML without generating output:

```bash
python3 tools/yaml-to-containerfile.py \
  --config exousia.yml \
  --validate
```

#### Verbose Mode

Get detailed information during generation:

```bash
python3 tools/yaml-to-containerfile.py \
  --config exousia.yml \
  --output Containerfile.generated \
  --verbose
```

### Command-Line Options

| Option | Description | Default |
|--------|-------------|---------|
| `-c, --config PATH` | Path to YAML configuration file | *Required* |
| `-o, --output PATH` | Output Containerfile path | stdout |
| `--image-type TYPE` | Base image type (see Supported Image Types below) | From config |
| `--fedora-version VER` | Fedora version number (ignored for bootcrew distros) | `43` |
| `--enable-plymouth` | Enable Plymouth boot splash | `true` |
| `--disable-plymouth` | Disable Plymouth boot splash | - |
| `--validate` | Validate config only, don't generate | - |
| `-v, --verbose` | Verbose output | - |

### Supported Image Types

**Fedora Atomic variants:**
- `fedora-bootc` - Minimal Fedora bootc base
- `fedora-silverblue` - GNOME desktop
- `fedora-kinoite` - KDE Plasma desktop
- `fedora-sway-atomic` - Sway (Wayland) desktop
- `fedora-onyx`, `fedora-budgie`, `fedora-cinnamon`, `fedora-cosmic`, `fedora-deepin`, `fedora-lxqt`, `fedora-mate`, `fedora-xfce` - Community variants

**Bootcrew distros:**
- `arch` - Arch Linux
- `gentoo` - Gentoo
- `debian` - Debian unstable
- `ubuntu` - Ubuntu Mantic
- `opensuse` - OpenSUSE Tumbleweed
- `proxmox` - Proxmox (Debian-based)

## YAML Configuration Structure

The YAML configuration follows a BlueBuild-inspired modular structure:

### Minimal Example

```yaml
name: exousia
description: Custom Fedora bootc image
image-version: 43
base-image: quay.io/fedora/fedora-sway-atomic:43
image-type: fedora-sway-atomic

modules:
  - type: rpm-ostree
    install:
      - kitty
      - neovim
    remove:
      - firefox-langpacks
```

If a supported custom base image omits a tag, the transpiler automatically
applies the requested OS/DE version to keep images explicitly versioned.

### Full Configuration

See `exousia.yml` in the repository root for a complete example.

### Module Types

The transpiler supports the following module types:

#### `files` - Copy files into the container

```yaml
- type: files
  files:
    - src: custom-configs/sway
      dst: /etc/sway
      mode: "0644"
```

#### `script` - Run shell commands

```yaml
- type: script
  scripts:
    - |
      mkdir -p /var/lib/example
      chown example:example /var/lib/example
```

#### `rpm-ostree` - Package management

```yaml
- type: rpm-ostree
  repos:
    - https://example.com/repo.rpm
  install:
    - package1
    - package2
  remove:
    - unwanted-package
```

#### `systemd` - Service management

```yaml
- type: systemd
  system:
    enabled:
      - service1.service
      - service2.service
  default-target: graphical.target
```

#### `bootcrew-setup` - Build bootc from source (bootcrew distros only)

For Arch, Gentoo, Debian, Ubuntu, OpenSUSE, and Proxmox, this module builds bootc from source and configures the filesystem for bootc compatibility:

```yaml
- type: bootcrew-setup
  system-deps:
    - base
    - linux
    - ostree
    - dracut
    - btrfs-progs
```

**What it does:**
- Installs system dependencies using the distro's package manager
- Builds bootc from source (GitHub)
- Generates dracut initramfs with composefs support
- Restructures filesystem for ostree/bootc (symlinks `/home` → `/var/home`, etc.)
- Configures composefs and readonly sysroot
- Adds `containers.bootc 1` label

**Distro-specific behavior:**
- **Arch**: Relocates `/var` to `/usr/lib/sysimage` for pacman compatibility
- **Debian/Ubuntu**: Uses Rustup installer, applies dracut regression fix
- **Gentoo**: Syncs portage, selects systemd profile, builds custom ostree
- **OpenSUSE**: Uses ENV DEV_DEPS pattern, applies erofs driver flags

See `DISTROS.md` for detailed examples and distro-specific requirements.

### Conditional Modules

Modules can include conditions to control when they run:

```yaml
- type: script
  condition: image-type == "fedora-bootc"
  scripts:
    - echo "This only runs for fedora-bootc"

- type: script
  condition: image-type == "fedora-bootc" && enable_plymouth == true
  scripts:
    - echo "This only runs for fedora-bootc with Plymouth enabled"
```

### Supported Conditions

**Image type conditions:**
- `image-type == "fedora-bootc"` - Minimal Fedora bootc
- `image-type == "fedora-sway-atomic"` - Fedora Sway Atomic
- `image-type == "arch"` - Arch Linux
- `image-type == "debian"` - Debian

**Distro family conditions:**
- `distro == "fedora"` - Any Fedora-based image
- `distro == "arch"` - Arch Linux
- `distro == "gentoo"` - Gentoo
- `distro == "debian"` - Debian-based (Debian, Ubuntu, Proxmox)
- `distro == "opensuse"` - OpenSUSE

**Feature conditions:**
- `enable_plymouth == true` - Plymouth enabled
- `enable_plymouth == false` - Plymouth disabled

Conditions can be combined with `&&` (AND) and `||` (OR) operators.

**Example:**
```yaml
- type: script
  condition: distro == "arch"
  scripts:
    - pacman -Syu --noconfirm
```

## CI/CD Integration

The transpiler is integrated into the GitHub Actions workflow:

1. **Checkout** - Repository is checked out
2. **Python Setup** - Python 3.11 is installed
3. **Dependencies** - PyYAML is installed
4. **Configuration Detection** - Fedora version and image type are determined
5. **Transpilation** - YAML is converted to Containerfile
6. **Build** - Generated Containerfile is built with Buildah

The workflow automatically uses the correct configuration based on:
- Workflow dispatch inputs (manual trigger)
- `.fedora-version` file (automated builds)
- Default values (fallback)

## Development Workflow

### Local Testing

1. **Edit YAML configuration**:
   ```bash
   vim exousia.yml
   ```

2. **Validate changes**:
   ```bash
   python3 tools/yaml-to-containerfile.py --config exousia.yml --validate
   ```

3. **Generate Containerfile**:
   ```bash
   python3 tools/yaml-to-containerfile.py \
     --config exousia.yml \
     --image-type fedora-sway-atomic \
     --output Containerfile.test
   ```

4. **Test build locally**:
   ```bash
   buildah build -f Containerfile.test -t exousia:test .
   ```

### Adding New Packages

Edit `exousia.yml` and add packages to the `rpm-ostree` module:

```yaml
- type: rpm-ostree
  install:
    - your-new-package
```

Then commit and push - the CI pipeline will automatically generate and build the new configuration.

### Adding Custom Files

Add file copy operations to the `files` module:

```yaml
- type: files
  files:
    - src: custom-configs/your-config
      dst: /etc/your-config
      mode: "0644"
```

## Troubleshooting

### Validation Errors

If validation fails, check:
1. YAML syntax is correct (proper indentation, no tabs)
2. Required fields are present (`name`, `description`, `modules`)
3. Module types are spelled correctly
4. File paths in `files` modules exist

### Generation Errors

If Containerfile generation fails:
1. Run with `--verbose` to see detailed output
2. Check condition syntax if using conditional modules
3. Verify Python version is 3.8 or higher
4. Ensure PyYAML is installed

### Build Errors

If the generated Containerfile fails to build:
1. Check the generated Containerfile for syntax errors
2. Verify file paths are correct
3. Test shell scripts individually
4. Review hadolint warnings

## Future Enhancements

Potential improvements for the transpiler:

- [ ] JSON Schema validation for YAML
- [ ] Support for more module types (Flatpak, systemd units, etc.)
- [ ] Variable interpolation in YAML
- [ ] Include/extend support for modular configs
- [ ] Diff tool to compare generated vs existing Containerfiles
- [ ] Web UI integration (Phase 3)

## See Also

- [BlueBuild Documentation](https://blue-build.org/)
- [BlueBuild Module Reference](https://blue-build.org/reference/module/)
- [bootc Project](https://github.com/bootc-dev/bootc)
