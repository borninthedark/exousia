# Chezmoi Integration

This guide explains how Exousia integrates chezmoi for automated dotfiles management using the BlueBuild chezmoi module.

## Overview

Exousia uses the [BlueBuild chezmoi module](https://blue-build.org/reference/modules/chezmoi/) to provide automated dotfiles management across all desktop images. This integration handles:

- **Build-time installation**: chezmoi binary is installed to `/usr/bin/chezmoi` during image build
- **Automatic initialization**: Dotfiles repository is cloned on first user login
- **Automatic updates**: Dotfiles are updated daily via systemd timer
- **Conflict resolution**: Configured to replace local changes with repository version

## How It Works

### Phase 1: Build Time

During image build, the chezmoi module:
- ✅ Downloads the latest chezmoi binary from GitHub releases (amd64)
- ✅ Installs it to `/usr/bin/chezmoi`
- ✅ Creates systemd user services for initialization and updates
- ✅ Configures the repository URL and update policy

### Phase 2: First User Login

When a user logs in for the first time:
- 🚀 The `chezmoi-init.service` runs automatically
- 🚀 Dotfiles repository is cloned to `~/.local/share/chezmoi`
- 🚀 Initial dotfiles are applied to the home directory
- 🚀 The service marks itself complete and won't run again

### Phase 3: Automatic Updates

After initialization:
- 🔄 The `chezmoi-update.timer` runs daily (configurable)
- 🔄 Waits 5 minutes after boot before first update (configurable)
- 🔄 Updates dotfiles from the repository
- 🔄 Replaces local changes with repository version (configurable)

## Configuration

The chezmoi module is configured in the following files:
- `yaml-definitions/sway-atomic.yml:202-208`
- `yaml-definitions/sway-bootc.yml:152-158`
- `yaml-definitions/fedora-kinoite.yml:60-66`

### Current Settings

```yaml
type: chezmoi
repository: "https://github.com/borninthedark/dotfiles"
all-users: true                # Enabled for all users by default
file-conflict-policy: skip     # Skip files with local changes
run-every: "1d"                # Update once per day
wait-after-boot: "5m"          # Wait 5 minutes after boot
```

### Configuration Options

| Option | Value | Description |
|--------|-------|-------------|
| `repository` | `https://github.com/borninthedark/dotfiles` | Git repository URL for dotfiles |
| `all-users` | `true` | Enable services globally for all users |
| `file-conflict-policy` | `skip` | Skip files with local changes |
| `run-every` | `1d` | Update interval (1 day) |
| `wait-after-boot` | `5m` | Delay before first update after boot |

#### File Conflict Policy

- **`skip`** (current): Skip files that have local changes
  - Uses: `chezmoi update --no-tty --keep-going`
  - Best for: Users who make local customizations and push changes to the repository
  - **This is the default** - allows flexibility to modify dotfiles locally and commit to remote

- **`replace`** (alternative): Overwrite changed files with repository version
  - Uses: `chezmoi update --no-tty --force`
  - Best for: Users who want dotfiles to always match the repository exactly

#### Update Intervals

You can customize update frequency using systemd time syntax:
- `1d` - Once per day (default)
- `6h` - Every 6 hours
- `1w` - Once per week
- `10m` - Every 10 minutes (for testing)

See [systemd.time documentation](https://www.freedesktop.org/software/systemd/man/latest/systemd.time.html) for complete syntax.

## Verification Methods

### Method 1: Check chezmoi Binary

```bash
# Verify chezmoi is installed
which chezmoi
# Expected: /usr/bin/chezmoi

# Check version
chezmoi --version
```

### Method 2: Check Systemd Services

```bash
# Check if services are enabled for current user
systemctl --user is-enabled chezmoi-init.service
systemctl --user is-enabled chezmoi-update.timer

# Check service status
systemctl --user status chezmoi-init.service
systemctl --user status chezmoi-update.timer

# Check when last update ran
systemctl --user list-timers chezmoi-update.timer
```

### Method 3: Verify Repository

```bash
# Check if repository is initialized
ls -la ~/.local/share/chezmoi

# Show repository status
chezmoi status

# Show repository source
chezmoi source path
```

### Method 4: Check Applied Dotfiles

```bash
# List managed files
chezmoi managed

# Show what chezmoi would apply
chezmoi diff

# Verify files match repository
chezmoi verify
```

## Manual Operations

### Initialize Dotfiles Manually

If you disabled `all-users` or want to use a different repository:

```bash
# Initialize with default repository
chezmoi init https://github.com/borninthedark/dotfiles

# Initialize and apply
chezmoi init --apply https://github.com/borninthedark/dotfiles

# Use a specific branch
chezmoi init --apply https://github.com/borninthedark/dotfiles --branch=laptop
```

### Enable Services Manually

If `all-users: false` is set, enable services per user:

```bash
# Enable services for current user
systemctl --user enable chezmoi-init.service
systemctl --user enable chezmoi-update.timer

# Start services immediately
systemctl --user start chezmoi-init.service
systemctl --user start chezmoi-update.timer
```

### Enable Lingering (Advanced)

Enable lingering to run user services at boot without login:

```bash
# Enable lingering for current user
sudo loginctl enable-linger $USER

# Check lingering status
loginctl show-user $USER | grep Linger
```

**Note:** Only enable lingering if your dotfiles contain system-critical configurations. For cosmetic settings and aliases, lingering is not needed.

### Force Update Dotfiles

```bash
# Update immediately
chezmoi update

# Update with force (replace local changes)
chezmoi update --force

# Update from specific branch
chezmoi update --branch=main
```

### View Update Logs

```bash
# View initialization logs
journalctl --user -u chezmoi-init.service

# View update timer logs
journalctl --user -u chezmoi-update.service

# Follow logs in real-time
journalctl --user -u chezmoi-update.service -f
```

## Troubleshooting

### No Dotfiles After Login

**Symptom:** `~/.local/share/chezmoi` doesn't exist after login

**Check:**
```bash
# Is the service enabled?
systemctl --user is-enabled chezmoi-init.service

# Did the service run?
systemctl --user status chezmoi-init.service

# Check for errors
journalctl --user -u chezmoi-init.service
```

**Fix:**
```bash
# Manually start the service
systemctl --user start chezmoi-init.service

# Or initialize manually
chezmoi init --apply https://github.com/borninthedark/dotfiles
```

### Repository Clone Failed

**Symptom:** Service fails with git clone errors

**Check:**
```bash
# Check network connectivity
ping github.com

# Test repository access
git ls-remote https://github.com/borninthedark/dotfiles

# View detailed error
journalctl --user -u chezmoi-init.service -n 50
```

**Fix:**
```bash
# Try with different protocol (SSH)
chezmoi init --apply git@github.com:borninthedark/dotfiles.git

# Or use HTTPS with credentials
chezmoi init --apply https://github.com/borninthedark/dotfiles
```

### Updates Not Running

**Symptom:** Dotfiles never update automatically

**Check:**
```bash
# Is the timer enabled?
systemctl --user is-enabled chezmoi-update.timer

# Is the timer active?
systemctl --user is-active chezmoi-update.timer

# When will it run next?
systemctl --user list-timers chezmoi-update.timer
```

**Fix:**
```bash
# Enable and start the timer
systemctl --user enable --now chezmoi-update.timer

# Force an update immediately
systemctl --user start chezmoi-update.service
```

### Local Changes Not Syncing

**Symptom:** Local dotfile modifications don't update from repository

**Explanation:** This is expected behavior with `file-conflict-policy: skip`

**Workflow for local changes:**
1. **Make changes locally** - Edit your dotfiles as needed
2. **Commit to local repository**
   ```bash
   cd ~/.local/share/chezmoi
   git add .
   git commit -m "Local customizations"
   git push
   ```
3. **Future updates** will pull these changes on other systems

**To force update a specific file:**
```bash
# Re-apply from repository, overwriting local changes
chezmoi apply --force ~/.config/specific-file
```

**To always override local changes:**
Change the conflict policy in `yaml-definitions/*.yml`:
```yaml
file-conflict-policy: replace
```

### Services Not Found

**Symptom:** `systemctl --user status chezmoi-init.service` shows "not found"

**Check:**
```bash
# List all chezmoi services
systemctl --user list-unit-files | grep chezmoi

# Check if chezmoi binary exists
which chezmoi
ls -l /usr/bin/chezmoi
```

**Fix:**
If services don't exist, the module may not have run during build. Check:
```bash
# View build logs for chezmoi module errors
# In your CI/CD pipeline or local build logs
```

## Customization

### Using a Different Repository

To use your own dotfiles repository:

1. Fork or create your dotfiles repository on GitHub
2. Update the repository URL in YAML configurations:
   ```yaml
   repository: "https://github.com/YOUR_USERNAME/dotfiles"
   ```
3. Rebuild the image

### Using a Specific Branch

```yaml
repository: "https://github.com/borninthedark/dotfiles"
branch: "laptop"  # Add this line
```

### Disable Auto-Updates

```yaml
disable-update: true  # Disable the update timer
```

### Disable Auto-Initialization

```yaml
disable-init: true  # Disable automatic initialization
```

### Require Manual Enablement

```yaml
all-users: false  # Don't enable services by default
```

Users will need to manually enable services:
```bash
systemctl --user enable chezmoi-init.service chezmoi-update.timer
```

## Build-Time Tests

The repository includes automated tests in `custom-tests/image_content.bats` that verify:

1. **chezmoi binary is installed** - Verifies `/usr/bin/chezmoi` exists
2. **chezmoi is executable** - Confirms binary has execute permissions
3. **chezmoi version works** - Tests `chezmoi --version` command
4. **Systemd init service exists** - Checks `chezmoi-init.service` is installed
5. **Systemd update service exists** - Checks `chezmoi-update.service` is installed
6. **Systemd update timer exists** - Checks `chezmoi-update.timer` is installed

These tests run during CI/CD builds to ensure the module installed correctly.

## Best Practices

### Repository Structure

Organize your dotfiles repository for chezmoi:
```
dotfiles/
├── .chezmoi.toml.tmpl      # Config with templates
├── .chezmoiignore          # Files to ignore
├── dot_bashrc              # ~/.bashrc
├── dot_zshrc               # ~/.zshrc
├── dot_config/             # ~/.config/
│   ├── nvim/
│   ├── sway/
│   └── kitty/
└── scripts/
    └── run_once_setup.sh   # Run once scripts
```

### Security Considerations

1. **Never commit secrets to dotfiles**
   - Use `chezmoi edit --apply ~/.env` for encrypted secrets
   - Use chezmoi's age encryption for sensitive files

2. **Review repository before auto-apply**
   - Malicious dotfiles could execute arbitrary code
   - Only use trusted repositories with `all-users: true`

3. **Use HTTPS for public repositories**
   - SSH requires key setup on each system
   - HTTPS works immediately for public repos

### Performance Tips

1. **Keep repository small**
   - Avoid large binary files
   - Use `.chezmoiignore` for generated content

2. **Adjust update frequency**
   - Daily updates (`1d`) are usually sufficient
   - Frequent updates (`10m`) increase network usage

3. **Use `run_once` scripts**
   - Scripts in `run_once_*.sh` only execute once
   - Great for initial setup without slowing updates

## Images Using Chezmoi

The chezmoi module is enabled in:
- ✅ **Sway Atomic** (`yaml-definitions/sway-atomic.yml`)
- ✅ **Sway Bootc** (`yaml-definitions/sway-bootc.yml`)
- ✅ **Fedora Kinoite** (`yaml-definitions/fedora-kinoite.yml`)

The RKE2 bootc image does **not** include chezmoi, as it's a minimal server image without desktop environments.

## References

- [BlueBuild chezmoi Module Documentation](https://blue-build.org/reference/modules/chezmoi/)
- [chezmoi Official Documentation](https://www.chezmoi.io/)
- [chezmoi Quick Start](https://www.chezmoi.io/quick-start/)
- [chezmoi User Guide](https://www.chezmoi.io/user-guide/setup/)
- [Exousia Dotfiles Repository](https://github.com/borninthedark/dotfiles)
- [systemd.time Documentation](https://www.freedesktop.org/software/systemd/man/latest/systemd.time.html)
