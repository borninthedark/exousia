# Plymouth Boot Splash Configuration Guide

## Overview

The Plymouth boot splash system has been modularized into separate components:

1. **Theme Configuration** (`setup-plymouth-theme`) - Manages Plymouth theme selection and kernel arguments
2. **Initramfs Management** (`dracut-rebuild`) - Handles initramfs regeneration independently
3. **Build-time Toggle** (`ENABLE_PLYMOUTH`) - Optional Plymouth installation during image build

## Architecture

### Separation of Concerns

```
┌─────────────────────────────────────┐
│  setup-plymouth-theme                │
│  - Set theme                         │
│  - Enable/disable boot splash        │
│  - Configure kernel arguments        │
└─────────────────────────────────────┘
            │
            ▼
┌─────────────────────────────────────┐
│  dracut-rebuild                      │
│  - Configure dracut modules          │
│  - Rebuild initramfs                 │
│  - Manage /var/tmp symlink           │
└─────────────────────────────────────┘
```

### Why This Design?

- **Modularity**: Each script has a single, clear responsibility
- **Flexibility**: Theme changes don't require initramfs rebuild
- **Build Time Optimization**: Optional Plymouth during build (saves ~2 minutes)
- **Runtime Management**: Users can configure Plymouth after deployment
- **AMD-Optimized**: No Intel-specific configurations

## Build-Time Configuration

### Enabling Plymouth (Default)

```bash
# Using Make
make build

# Using Podman directly
podman build \
  --build-arg ENABLE_PLYMOUTH=true \
  -t localhost:5000/exousia:latest \
  -f Containerfile.atomic .
```

### Disabling Plymouth

```bash
# Using Make
make build ENABLE_PLYMOUTH=false

# Using Podman directly
podman build \
  --build-arg ENABLE_PLYMOUTH=false \
  -t localhost:5000/exousia:latest \
  -f Containerfile.atomic .
```

### GitHub Actions Workflow Dispatch

1. Go to **Actions** → **Fedora Bootc DevSec CI**
2. Click **Run workflow**
3. Select options:
   - **Fedora Version**: 42, 43, etc.
   - **Image Type**: fedora-bootc or fedora-sway-atomic
   - **Enable Plymouth**: ✓ (checked) or ☐ (unchecked)
4. Click **Run workflow**

## Runtime Configuration

### Using setup-plymouth-theme

#### Check Current Status

```bash
sudo setup-plymouth-theme status
```

Output:
```
Plymouth Configuration Status
==============================

Status: Enabled
Plymouth Package: Installed
Current Theme: bgrt-better-luks

Configuration Files:
  Dracut Config: Present (/usr/lib/dracut/dracut.conf.d/plymouth.conf)
  Kernel Args: Present (/usr/lib/bootc/kargs.d/plymouth.toml)

Theme Directory: Present (/usr/share/plymouth/themes/bgrt-better-luks)
```

#### List Available Themes

```bash
sudo setup-plymouth-theme list
```

#### Change Theme

```bash
# Set theme (requires initramfs rebuild afterward)
sudo setup-plymouth-theme set spinner

# Or with environment variable
PLYMOUTH_THEME=bgrt-better-luks sudo setup-plymouth-theme set
```

#### Enable/Disable Boot Splash

```bash
# Enable Plymouth boot splash
sudo setup-plymouth-theme enable

# Disable (removes kernel arguments but keeps theme)
sudo setup-plymouth-theme disable
```

### Using dracut-rebuild

#### Rebuild Current Kernel Initramfs

```bash
# Standard rebuild
sudo dracut-rebuild

# Force rebuild (even if exists)
sudo dracut-rebuild --force

# Verbose output
sudo dracut-rebuild --verbose
```

#### Rebuild Specific Kernel

```bash
# List installed kernels
sudo dracut-rebuild --list

# Rebuild specific version
sudo dracut-rebuild 6.8.5-301.fc40.x86_64
```

## Common Workflows

### Workflow 1: Change Plymouth Theme

```bash
# 1. Set new theme
sudo setup-plymouth-theme set spinner

# 2. Rebuild initramfs
sudo dracut-rebuild --force

# 3. Apply bootc changes
sudo bootc upgrade

# 4. Reboot
sudo systemctl reboot
```

### Workflow 2: Disable Boot Splash After Installation

```bash
# 1. Disable Plymouth kernel arguments
sudo setup-plymouth-theme disable

# 2. Apply bootc changes
sudo bootc upgrade

# 3. Reboot
sudo systemctl reboot
```

### Workflow 3: Fresh Installation with Custom Theme

```bash
# 1. List available themes
sudo setup-plymouth-theme list

# 2. Enable with custom theme
PLYMOUTH_THEME=spinner sudo setup-plymouth-theme enable

# 3. Rebuild initramfs
sudo dracut-rebuild --force

# 4. Deploy changes
sudo bootc upgrade && sudo systemctl reboot
```

## Technical Details

### File Locations

```
/usr/local/bin/
├── setup-plymouth-theme       # Theme configuration script
└── dracut-rebuild             # Initramfs rebuild script

/usr/lib/dracut/dracut.conf.d/
└── plymouth.conf              # Dracut Plymouth module config

/usr/lib/bootc/kargs.d/
└── plymouth.toml              # Kernel arguments for bootc

/usr/share/plymouth/themes/
├── bgrt-better-luks/          # Custom LUKS-optimized theme
├── spinner/                   # Default spinner theme
└── ...                        # Other themes

/usr/lib/modules/
└── 6.8.5-301.fc40.x86_64/
    └── initramfs.img          # Generated initramfs
```

### Environment Variables

#### Build Time

- `ENABLE_PLYMOUTH` (default: `true`)
  - Set to `false` to skip Plymouth configuration during build

#### Runtime

- `PLYMOUTH_THEME` (default: `bgrt-better-luks`)
  - Override default theme when running `setup-plymouth-theme`

### Kernel Arguments

When Plymouth is enabled, the following kernel arguments are added:

```toml
kargs = ["splash", "quiet"]
match-architectures = ["x86_64", "aarch64"]
```

- `splash` - Enable Plymouth boot splash
- `quiet` - Suppress boot messages (cleaner display)
- Applies to: AMD64 (x86_64) and ARM64 (aarch64) systems

## AMD System Optimization

This configuration is optimized for **AuthenticAMD** systems:

- No Intel-specific workarounds
- AMD graphics drivers pre-configured
- Optimized kernel parameters for AMD processors
- No unnecessary Intel microcode updates

## Troubleshooting

### Plymouth Theme Not Showing

```bash
# 1. Check if Plymouth is enabled
sudo setup-plymouth-theme status

# 2. Verify kernel arguments
cat /usr/lib/bootc/kargs.d/plymouth.toml

# 3. Check current boot parameters
cat /proc/cmdline | grep -o 'splash\|quiet'

# 4. Rebuild initramfs
sudo dracut-rebuild --force --verbose

# 5. Apply and reboot
sudo bootc upgrade && sudo systemctl reboot
```

### Initramfs Build Fails

```bash
# Check for errors
sudo dracut-rebuild --verbose

# Verify /var/tmp symlink
ls -la /var/tmp

# Check kernel modules
ls -la /usr/lib/modules/

# Verify Plymouth is installed
rpm -q plymouth plymouth-system-theme
```

### Theme Not Available

```bash
# List installed themes
sudo setup-plymouth-theme list

# Install additional themes
sudo dnf install plymouth-theme-*

# Check theme directory
ls -la /usr/share/plymouth/themes/
```

## Testing

### Test Plymouth Configuration

```bash
# Run tests with Plymouth enabled (default)
make test

# Run tests with Plymouth disabled
ENABLE_PLYMOUTH=false make test
```

### Manual Testing in Container

```bash
# Build with Plymouth
podman build --build-arg ENABLE_PLYMOUTH=true -t test:plymouth .

# Check configuration
podman run --rm test:plymouth /usr/local/bin/setup-plymouth-theme status

# Check scripts are executable
podman run --rm test:plymouth ls -la /usr/local/bin/ | grep plymouth
```

## Best Practices

### For Developers

1. **Test both configurations**: Always test with `ENABLE_PLYMOUTH=true` and `ENABLE_PLYMOUTH=false`
2. **Use helper functions**: Check `is_plymouth_enabled()` in tests
3. **Document changes**: Update this guide when modifying Plymouth behavior
4. **Modular changes**: Keep theme and dracut logic separate

### For Users

1. **Check status first**: Run `setup-plymouth-theme status` before changes
2. **Backup before changes**: Plymouth changes affect boot, test in VM first
3. **One change at a time**: Don't mix theme changes with other system updates
4. **Reboot to apply**: Plymouth changes require reboot to take effect

## Performance Impact

### Build Time

- **With Plymouth**: ~5-7 minutes (includes dracut rebuild)
- **Without Plymouth**: ~3-5 minutes (skips dracut rebuild)
- **Savings**: ~2 minutes per build

### Boot Time

- **With Plymouth**: +0.5-1 second (graphical splash overhead)
- **Without Plymouth**: Standard boot time
- **AMD System**: Optimized for AMD GPU performance

## References

- [Fedora Plymouth Documentation](https://fedoraproject.org/wiki/Plymouth)
- [Plymouth Theme Guide](https://www.freedesktop.org/wiki/Software/Plymouth/Theme-Format/)
- [Dracut Documentation](https://man7.org/linux/man-pages/man8/dracut.8.html)
- [Bootc Kernel Arguments](https://docs.fedoraproject.org/en-US/bootc/kernel-arguments/)
