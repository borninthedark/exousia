# Chezmoi Integration

This guide explains how Exousia integrates chezmoi for automated dotfiles management using the BlueBuild chezmoi module.

## Overview

Exousia automates dotfiles management using a custom chezmoi module. This integration handles:

- **Build-time installation**: chezmoi is installed as an RPM package during the image build
- **Automatic initialization**: the dotfiles repository is cloned on first user login
- **Automatic updates**: dotfiles are updated daily via a systemd timer
- **Conflict handling**: configured to skip files with local changes (keeps your customizations)

## How It Works

### Phase 1: Build Time

During image build, the chezmoi module:

- ✅ Installs chezmoi from Fedora RPM repos to `/usr/bin/chezmoi`
- ✅ Copies systemd user unit files with placeholder values
- ✅ Substitutes the repository URL, conflict policy, and timer intervals into the unit files
- ✅ Enables services globally for all users via `systemctl --global enable`

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

The chezmoi module is declared in the blueprint files:

- `adnyeus.yml`
- `yaml-definitions/sway-atomic.yml`
- `yaml-definitions/sway-bootc.yml`

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

Tests in `custom-tests/` verify chezmoi integration at two stages:

**`overlay_content.bats`** (before build — checks source files):

1. All three unit files exist in `overlays/base/systemd/user/`
2. Each unit file contains the expected placeholder strings (so sed substitution has something to replace)
3. Each unit file has an `[Install]` section (required for `systemctl --global enable` to work)
4. `chezmoi-update.service` declares a `network-online.target` dependency

**`image_content.bats`** (after build — checks the built image):

1. chezmoi binary exists at `/usr/bin/chezmoi` and is executable
2. `chezmoi --version` runs successfully
3. chezmoi is installed as an RPM package
4. All three unit files are present in the image
5. No placeholder strings remain in the unit files (confirms sed substitution ran)
6. The dotfiles repository URL appears in `chezmoi-init.service`
7. Enable symlinks exist for `chezmoi-init.service` and `chezmoi-update.timer`

## Best Practices

### Repository Structure

Organize your dotfiles repository for chezmoi:

```text
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

## Dotfiles Change Detection (Mayuri)

The **Mayuri** workflow (`.github/workflows/mayuri.yml`) automatically triggers a new image build when the dotfiles repository changes:

1. Runs at 04:10, 12:10, and 20:10 UTC — midway between scheduled Urahara builds
2. Fetches the latest commit SHA from `borninthedark/dotfiles` via the GitHub API
3. Compares it against the last-seen SHA stored in `.dotfiles-sha`
4. If they differ: triggers the Urahara pipeline via `workflow_dispatch` and commits the new SHA

This means a push to the dotfiles repository will result in a rebuilt image within ~4 hours.

## Images Using Chezmoi

The chezmoi module is enabled in:

- **Adnyeus** (`adnyeus.yml`) - DevSecOps-hardened Fedora bootc image with Sway
- **Sway Atomic** (`yaml-definitions/sway-atomic.yml`)
- **Sway Bootc** (`yaml-definitions/sway-bootc.yml`)

## References

- [BlueBuild chezmoi Module Documentation](https://blue-build.org/reference/modules/chezmoi/)
- [chezmoi Official Documentation](https://www.chezmoi.io/)
- [chezmoi Quick Start](https://www.chezmoi.io/quick-start/)
- [chezmoi User Guide](https://www.chezmoi.io/user-guide/setup/)
- [Exousia Dotfiles Repository](https://github.com/borninthedark/dotfiles)
- [systemd.time Documentation](https://www.freedesktop.org/software/systemd/man/latest/systemd.time.html)
