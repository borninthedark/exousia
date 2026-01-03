# Chezmoi Integration

This guide explains how Exousia integrates chezmoi for automated dotfiles management using build-time application.

## Overview

Exousia applies dotfiles during the CI build process, baking them into `/etc/skel` so they're immediately available for all new users. This provides:

- **Build-time application**: Dotfiles are applied during image build, not on first login
- **Immediate availability**: All new users get dotfiles from their first login
- **No boot delays**: No waiting for first-boot services
- **Consistent setup**: All users get identical dotfiles from the built image

## How It Works

### Build Time (CI)

During image build:
- ✅ Chezmoi is installed via DNF
- ✅ Dotfiles repository is cloned from GitHub
- ✅ Dotfiles are applied to `/etc/skel`
- ✅ Default shell is set to zsh for new users
- ✅ Temporary files are cleaned up

### First User Login

When a new user is created:
- 🚀 User home directory is created
- 🚀 Dotfiles from `/etc/skel` are copied to `~/`
- 🚀 User immediately has configured shell, configs, etc.
- 🚀 Default shell is zsh (if user accepts default)

## Configuration

The build-time chezmoi application is configured in:
- `adnyeus.yml:140-171`
- `yaml-definitions/sway-atomic.yml:196-218`
- `yaml-definitions/sway-bootc.yml:147-169`
- `yaml-definitions/fedora-kinoite.yml:59-81`

### Current Settings

```yaml
# Apply dotfiles at build time
- type: script
  scripts:
    - |
      set -euxo pipefail

      # Install chezmoi if not present
      if ! command -v chezmoi &> /dev/null; then
        dnf install -y chezmoi
      fi

      # Apply dotfiles to /etc/skel for new users
      DOTFILES_REPO="https://github.com/borninthedark/dotfiles"
      TEMP_DIR="/tmp/dotfiles-build"

      rm -rf "$TEMP_DIR"
      git clone "$DOTFILES_REPO" "$TEMP_DIR"

      mkdir -p /etc/skel
      export HOME=/etc/skel
      chezmoi init --apply --source="$TEMP_DIR" || echo "Dotfiles application failed, continuing..."
      unset HOME

      rm -rf "$TEMP_DIR"
      echo "✓ Dotfiles applied to /etc/skel"

      # Set zsh as default shell for new users
      if command -v zsh &> /dev/null; then
        sed -i 's|SHELL=/bin/bash|SHELL=/bin/zsh|g' /etc/default/useradd || true
        echo "✓ Default shell set to zsh"
      fi
```

## Verification Methods

### Method 1: Check /etc/skel

```bash
# Verify dotfiles exist in /etc/skel
ls -la /etc/skel

# Check for common dotfile directories
ls -la /etc/skel/.config
ls -la /etc/skel/.local

# View specific config files
cat /etc/skel/.zshrc
cat /etc/skel/.config/sway/config
```

### Method 2: Check chezmoi Binary

```bash
# Verify chezmoi is installed
which chezmoi
# Expected: /usr/bin/chezmoi

# Check version
chezmoi --version
```

### Method 3: Check Default Shell

```bash
# Check default shell for new users
grep SHELL /etc/default/useradd
# Expected: SHELL=/bin/zsh

# Verify zsh is available
which zsh
```

### Method 4: Create Test User

```bash
# Create a test user to verify dotfiles
sudo useradd -m testuser
sudo ls -la /home/testuser

# Check that dotfiles were copied
sudo ls -la /home/testuser/.config
sudo cat /home/testuser/.zshrc

# Clean up
sudo userdel -r testuser
```

## Manual Operations

### Update Dotfiles in Running System

If you want to update dotfiles for existing users:

```bash
# Update your own dotfiles
chezmoi init --apply https://github.com/borninthedark/dotfiles

# Or manually pull updates
cd ~/.local/share/chezmoi
git pull
chezmoi apply
```

### Change Default Repository

To use a different dotfiles repository:

```bash
# Initialize with different repository
chezmoi init --apply https://github.com/YOUR_USERNAME/dotfiles

# Use a specific branch
chezmoi init --apply https://github.com/YOUR_USERNAME/dotfiles --branch=laptop
```

### Manually Apply to /etc/skel

If you need to update /etc/skel on a running system:

```bash
# Clone repository
git clone https://github.com/borninthedark/dotfiles /tmp/dotfiles

# Apply to /etc/skel
sudo rm -rf /etc/skel/.* /etc/skel/*
export HOME=/etc/skel
sudo -E chezmoi init --apply --source=/tmp/dotfiles
unset HOME

# Clean up
rm -rf /tmp/dotfiles
```

## Troubleshooting

### No Dotfiles in /etc/skel

**Symptom:** `/etc/skel/.config` doesn't exist

**Check:**
```bash
# View build logs for errors
# Look for "Dotfiles application failed" message

# Check if dotfiles were applied
ls -la /etc/skel
```

**Cause:** Dotfiles repository may not have been cloned during build

**Fix:** Rebuild image or manually apply dotfiles to /etc/skel

### New Users Don't Get Dotfiles

**Symptom:** New users have empty home directories

**Check:**
```bash
# Verify /etc/skel has dotfiles
ls -la /etc/skel/.config

# Check if files are hidden (start with .)
ls -latr /etc/skel
```

**Fix:**
```bash
# Manually copy dotfiles to existing user
sudo cp -r /etc/skel/. /home/username/
sudo chown -R username:username /home/username
```

### Wrong Shell for New Users

**Symptom:** New users get bash instead of zsh

**Check:**
```bash
# Check default shell setting
grep SHELL /etc/default/useradd
```

**Fix:**
```bash
# Set default shell to zsh
sudo sed -i 's|SHELL=/bin/bash|SHELL=/bin/zsh|g' /etc/default/useradd

# Change existing user's shell
chsh -s /bin/zsh
```

### Repository Clone Failed During Build

**Symptom:** Build fails with git clone errors

**Check CI logs for:**
```
fatal: unable to access 'https://github.com/...': ...
Dotfiles application failed, continuing...
```

**Causes:**
- Network issues during build
- Repository is private (requires authentication)
- Repository doesn't exist

**Fix:**
- Use a public repository for build-time application
- Or fork the dotfiles repository to your own account

## Customization

### Using a Different Repository

To use your own dotfiles repository:

1. Fork or create your dotfiles repository on GitHub
2. Update the repository URL in YAML configurations:
   ```yaml
   DOTFILES_REPO="https://github.com/YOUR_USERNAME/dotfiles"
   ```
3. Rebuild the image

### Using a Specific Branch

```bash
# Modify the git clone command in configs
git clone --branch=laptop "$DOTFILES_REPO" "$TEMP_DIR"
```

### Disable Dotfiles Application

Comment out the entire dotfiles script block in your YAML configuration:

```yaml
# # Apply dotfiles at build time
# - type: script
#   scripts:
#     - |
#       ...dotfiles script...
```

### Keep Bash as Default Shell

Remove the default shell setting portion:

```yaml
# Don't include the "Set zsh as default shell" section
```

## Build-Time Tests

The repository includes automated tests in `custom-tests/image_content.bats` that verify:

1. **Dotfiles applied to /etc/skel** - Checks `/etc/skel/.config` exists
2. **Chezmoi is installed** - Verifies `chezmoi` command is available
3. **Default shell is zsh** - Confirms zsh is installed and configured

These tests run during CI/CD builds to ensure dotfiles were applied correctly.

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
   - Secrets in /etc/skel are visible to all users
   - Use environment-specific configs or encrypted secrets

2. **Review repository before baking in**
   - Malicious dotfiles could affect all users
   - Only use trusted repositories for build-time application

3. **Use HTTPS for public repositories**
   - Build environment may not have SSH keys
   - HTTPS works immediately for public repos

### Performance Tips

1. **Keep repository small**
   - Large repositories slow down builds
   - Avoid binary files in dotfiles

2. **Use shallow clone for builds**
   ```bash
   git clone --depth=1 "$DOTFILES_REPO" "$TEMP_DIR"
   ```

3. **Cache dotfiles between builds**
   - Consider caching the cloned repository in CI
   - Reduces build time and network usage

## Images Using Build-Time Dotfiles

Build-time dotfiles application is enabled in:
- ✅ **Adnyeus** (`adnyeus.yml`) - DevSecOps-hardened Fedora bootc image with Sway
- ✅ **Sway Atomic** (`yaml-definitions/sway-atomic.yml`)
- ✅ **Sway Bootc** (`yaml-definitions/sway-bootc.yml`)
- ✅ **Fedora Kinoite** (`yaml-definitions/fedora-kinoite.yml`)

The RKE2 bootc image does **not** include dotfiles, as it's a minimal server image without desktop environments.

## Migration from Chezmoi Module

**Previous Approach:** BlueBuild chezmoi module with first-boot services

**Current Approach:** Build-time application to /etc/skel

**Why the change:**
- Dotfiles immediately available (no first-boot delay)
- Simpler implementation (no systemd services)
- No dependency on boot-time services
- Consistent for all users
- Easier to verify in CI

**What you lose:**
- No automatic dotfile updates
- Can't have per-user repositories
- Users must manually update dotfiles if needed

**What you gain:**
- Faster first login
- No systemd service complexity
- Smaller images (no service files)
- Build-time verification

## References

- [chezmoi Official Documentation](https://www.chezmoi.io/)
- [chezmoi Quick Start](https://www.chezmoi.io/quick-start/)
- [chezmoi User Guide](https://www.chezmoi.io/user-guide/setup/)
- [Exousia Dotfiles Repository](https://github.com/borninthedark/dotfiles)
- [/etc/skel Documentation](https://www.pathname.com/fhs/pub/fhs-2.3.html#ETCSKELUSERDIRECTORYSKELETON)
