# Bootc Upgrade Workflow

## Overview

One of the key features of bootc is transactional, atomic OS upgrades using container images. This document explains how to upgrade your Exousia bootc system safely and efficiently.

## Understanding Bootc Upgrades

Unlike traditional package managers, bootc treats your entire OS as a container image. Upgrades involve:

1. Pulling a new container image
2. Preparing a new boot entry with the updated OS
3. Rebooting into the new system
4. Keeping the old system available for rollback

This approach provides:

- **Atomic updates**: All-or-nothing upgrades
- **Rollback-ready deployments**: Previous deployments remain available for
  boot selection or manual rollback
- **Predictable state**: Same image everywhere (dev, test, prod)

## Explicit Compatibility Goal

Exousia is intended to stay compatible with same-version Fedora Atomic rebases.
The project support goal is:

- `Fedora Atomic -> Exousia -> Fedora Atomic`
- same Fedora major version in both directions
- no destructive migration requirement outside normal `/etc` and `/var` state

That means Exousia should avoid one-way first-boot mutations, custom partition
assumptions, or boot flow changes that would prevent a user from rebasing back
to the matching Fedora Atomic lineage later. Cross-major-version rebases and
other image-family changes are not implied by this compatibility goal.

## Basic Upgrade Commands

### Check Current Status

```bash
# View current deployment
bootc status

# Check which image you're running
bootc status --json | jq -r '.status.booted.image'
```

### Upgrade to Latest

```bash
# Check for updates (doesn't apply them)
sudo bootc upgrade --check

# Perform upgrade
sudo bootc upgrade

# Reboot to apply
sudo systemctl reboot
```

### Switch to Different Image/Tag

```bash
# Mirror the desired tag from GHCR first
just local-mirror TAG=v1.2.0

# Switch to a specific tag
sudo bootc switch localhost:5000/exousia:v1.2.0

# Mirror the rolling daily build
just local-mirror TAG=current

# Switch to the rolling daily build
sudo bootc switch localhost:5000/exousia:current

# Mirror latest and switch back
just local-mirror
sudo bootc switch localhost:5000/exousia:latest
```

### Rebase Compatibility Notes

For round-trip rebases, keep the Fedora major version aligned:

- Fedora Atomic 44 -> Exousia 44
- Exousia 44 -> Fedora Atomic 44

Do not treat cross-major rebases and image-family changes as the same
operation. Change Fedora major versions separately from changing the image
family whenever you want a reversible path.

## Upgrade Workflow Best Practices

### Pre-Upgrade Checklist

1. **Backup important data** (even though rollback is available)

   ```bash
   # Example: backup home directory configs
   tar -czf ~/backup-configs-$(date +%Y%m%d).tar.gz ~/.config
   ```

2. **Check current status**

   ```bash
   bootc status
   ```

3. **Verify image availability**

   ```bash
   # Check if newer image exists
   skopeo inspect docker://ghcr.io/borninthedark/exousia:latest
   ```

4. **Review changelog/release notes**
   - Check GitHub releases: <https://github.com/borninthedark/exousia/releases>
   - Review commit history for breaking changes

### Performing the Upgrade

```bash
# 1. Update to latest image
sudo bootc upgrade

# 2. Review what changed
bootc status

# 3. Reboot when ready
sudo systemctl reboot
```

### Post-Upgrade Verification

After rebooting:

1. **Verify you're on the new image**

   ```bash
   bootc status
   # Check "Booted:" line shows new image/version
   ```

2. **Test critical functionality**
   - Desktop environment launches correctly
   - Network connectivity works
   - Audio/video devices function
   - Applications launch successfully
   - Rebase-sensitive services still behave correctly:
     `greetd`, NetworkManager, Flatpak, portals, and boot health

3. **Check logs for issues**

   ```bash
   journalctl -b -p err
   ```

## Rollback Procedures

### Automatic Fallback Caveat

Some boot flows may fall back to an older deployment after a failed boot, but
that behavior depends on the surrounding bootloader and health-policy path. Do
not treat automatic fallback as a guaranteed Exousia feature.

### Manual Rollback

If you want to manually roll back after a successful boot:

```bash
# List available deployments
bootc status

# Rollback to previous deployment
sudo bootc rollback

# Reboot to apply
sudo systemctl reboot
```

## Advanced Upgrade Scenarios

### Staged Rollouts

For testing upgrades before full deployment:

```bash
# 1. Test on a VM first
# (See bootc-image-builder.md for VM creation)

# 2. Deploy to test systems
ssh test-system 'sudo bootc upgrade && sudo systemctl reboot'

# 3. Monitor for issues (24-48 hours)

# 4. Deploy to production systems
for host in prod1 prod2 prod3; do
    ssh $host 'sudo bootc upgrade && sudo systemctl reboot'
    sleep 300  # Wait 5 minutes between hosts
done
```

### Round-Trip Rebase Validation

Before declaring a release safe for general use, validate:

1. Fedora Atomic -> Exousia
2. Exousia -> Fedora Atomic
3. login, networking, Flatpak, and boot health after both directions

This is a release-policy goal even when the CI path cannot fully automate the
end-to-end rebase test yet.

### Scheduled Upgrades

Exousia already ships `bootc-fetch-apply-updates.timer` with a staged override.
Use that built-in path first:

```bash
systemctl status bootc-fetch-apply-updates.timer
systemctl list-timers bootc-fetch-apply-updates.timer
```

If you need a custom maintenance-window timer instead, treat a hand-rolled
`bootc-upgrade.timer` as an alternative override rather than the default path.

### Pinning Deployments

Prevent a deployment from being garbage collected:

```bash
# Pin current deployment
sudo ostree admin pin 0

# List pinned deployments
ostree admin status

# Unpin
sudo ostree admin pin -u 0
```

## Monitoring and Maintenance

### Check for Available Updates

Create a script to check for updates:

```bash
#!/bin/bash
# check-updates.sh

CURRENT_DIGEST=$(bootc status --json | jq -r '.status.booted.image.imageDigest')
LATEST_DIGEST=$(skopeo inspect docker://ghcr.io/borninthedark/exousia:latest | jq -r '.Digest')

if [ "$CURRENT_DIGEST" != "$LATEST_DIGEST" ]; then
    echo "Update available!"
    echo "Current: $CURRENT_DIGEST"
    echo "Latest:  $LATEST_DIGEST"
    exit 1
else
    echo "System is up to date"
    exit 0
fi
```

### Cleanup Old Deployments

```bash
# bootc automatically manages old deployments
# But you can force cleanup:
sudo ostree admin cleanup
```

## Troubleshooting

### Issue: Upgrade fails with authentication error

**Solution**: Ensure you're logged into the container registry you use for direct pulls:

```bash
# For GHCR
podman login ghcr.io

# Copy credentials for bootc
sudo cp ~/.config/containers/auth.json /etc/ostree/auth.json
```

### Issue: System boots to old deployment after upgrade

**Cause**: The new deployment may have failed boot, or the boot chain may have
selected an older deployment based on host-specific policy

**Solution**:

1. Check boot logs: `journalctl -b -1`
2. Identify the failure
3. Report issue or wait for fix
4. Try upgrade again later

### Issue: "Image has no bootc metadata"

**Cause**: Attempting to switch to a non-bootc container image

**Solution**: Only use images built with bootc-compatible base images:

- `quay.io/fedora/fedora-bootc`
- `quay.io/fedora/fedora-sway-atomic`

Other Fedora Atomic families should be treated as unverified return paths
unless Exousia documents them explicitly.

Always pin these bases to a specific OS or desktop environment version. When a
supported image reference is untagged, the tooling will automatically append
the requested version tag to avoid pulling a moving `latest` build.

### Issue: Disk space full after multiple upgrades

**Solution**: Clean up old deployments:

```bash
sudo ostree admin cleanup
sudo bootc upgrade --apply
```

## Best Practices Summary

1. ✅ **Always check status** before and after upgrades
2. ✅ **Test in VMs first** before bare metal
3. ✅ **Keep multiple deployments** available for rollback safety
4. ✅ **Monitor logs** after upgrades
5. ✅ **Use specific tags** for production systems
6. ✅ **Document your rollback plan**
7. ✅ **Schedule upgrades** during maintenance windows
8. ✅ **Verify critical services** after upgrade

## Related Documentation

- [README.md](../README.md) - Using pre-built images
- [bootc-image-builder.md](bootc-image-builder.md) - Testing disk images locally
- [testing/README.md](testing/README.md) - Container image testing
- [bootc Project](https://github.com/bootc-dev/bootc)

## Community Resources

- [Fedora Discussion - bootc](https://discussion.fedoraproject.org/tag/bootc)
- [bootc GitHub Issues](https://github.com/bootc-dev/bootc/issues)
- [Fedora Magazine bootc Articles](https://fedoramagazine.org/?s=bootc)
