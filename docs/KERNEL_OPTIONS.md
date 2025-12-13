# Kernel Options for Exousia

This document explains how to run different kernel versions on your Exousia bootc images.

## Default Kernel

By default, Exousia uses the kernel from the Fedora base image:
- **fedora-bootc:43** → Fedora 43 stable kernel (~6.11.x)
- Tested, stable, fully supported
- Recommended for production use

## Newer Kernel Options

### Option 1: Mainline Kernel (Build-Time)

Add the latest stable kernel.org kernel to your image at build time.

**Pros:**
- ✅ Latest features and hardware support
- ✅ Baked into image (consistent across deployments)
- ✅ Easier to test in VMs before deploying

**Cons:**
- ❌ Less tested than Fedora kernel
- ❌ May have regressions
- ❌ Requires rebuilding image for kernel updates

**How to Enable:**

1. **Edit `adnyeus.yml`** - Add a DNF repository configuration module:

```yaml
modules:
  # ... existing modules ...

  # Enable kernel-vanilla COPR for mainline kernels
  - type: script
    scripts:
      - dnf config-manager --set-enabled copr:copr.fedorainfracloud.org:group_kernel-vanilla:mainline

  # Install mainline kernel (will replace Fedora kernel)
  - type: script
    scripts:
      - dnf install -y --allowerasing kernel kernel-core kernel-modules kernel-modules-core kernel-modules-extra
```

2. **Rebuild your image**
3. **Test in VM first!** (See BOOTC_IMAGE_BUILDER.md)

### Option 2: Runtime Kernel Override (Recommended for Testing)

Override the kernel on a running system without rebuilding the image.

**Pros:**
- ✅ Quick to test
- ✅ Easy to rollback
- ✅ No image rebuild needed

**Cons:**
- ❌ Not persistent across bootc upgrades
- ❌ Needs to be applied on each system

**How to Use:**

```bash
# On your running bootc system
sudo rpm-ostree override replace \
  --experimental \
  --freeze \
  --from repo='copr:copr.fedorainfracloud.org:group_kernel-vanilla:mainline' \
  kernel kernel-core kernel-modules kernel-modules-core

# Reboot to apply
sudo systemctl reboot

# After testing, if you want to revert:
sudo rpm-ostree reset
sudo systemctl reboot
```

### Option 3: linux-next Kernel (Bleeding Edge)

For developers who want to test upcoming kernel features.

**Warning:** ⚠️ Very experimental! Expect breakage!

**Enable in adnyeus.yml:**

```yaml
- type: script
  scripts:
    - dnf config-manager --set-enabled copr:copr.fedorainfracloud.org:group_kernel-vanilla:next
    - dnf install -y --allowerasing kernel kernel-core kernel-modules kernel-modules-core
```

### Option 4: Rawhide Kernel

Fedora's development kernel with debug options.

**Not recommended** for bootc due to:
- Slower performance (debug enabled)
- Extreme instability
- May not match Fedora 43 userspace

## Recommended Approach

For most users who want newer hardware support:

1. **Test locally first:**
   ```bash
   # On your deployed bootc system
   sudo rpm-ostree override replace \
     --experimental --freeze \
     --from repo='copr:copr.fedorainfracloud.org:group_kernel-vanilla:mainline' \
     kernel kernel-core kernel-modules kernel-modules-core
   sudo systemctl reboot
   ```

2. **If it works well, bake it into your image:**
   - Update `adnyeus.yml` with the DNF configuration
   - Rebuild and redeploy your image
   - Now all new deployments get the mainline kernel

3. **Keep Fedora kernel as fallback:**
   - bootc keeps multiple boot entries
   - If mainline kernel fails, you can boot to previous deployment

## Kernel Comparison

| Kernel Type | Version Example | Stability | Performance | Hardware Support |
|-------------|----------------|-----------|-------------|------------------|
| Fedora Stable | 6.11.5 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| Mainline | 6.12.1 | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| linux-next | 6.13-rc1 | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| Rawhide | 6.13-git | ⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ |

## Troubleshooting

### Kernel Won't Boot

bootc will automatically rollback to previous deployment.

Manual rollback:
```bash
# At GRUB menu, select previous deployment
# Or after booting to old deployment:
sudo rpm-ostree rollback
```

### Missing Firmware

If you get firmware warnings:

```yaml
# Add to adnyeus.yml packages
- linux-firmware
- linux-firmware-whence  # For newer hardware
```

### Module Signing / Secure Boot

Mainline kernels from COPR are **signed for Secure Boot**.

For custom kernels, you'll need to:
1. Disable Secure Boot, OR
2. Sign the kernel with your own MOK key

## Related Documentation

- [Fedora Kernel Vanilla Repositories Wiki](https://fedoraproject.org/wiki/Kernel_Vanilla_Repositories)
- [bootc rpm-ostree Integration](https://docs.fedoraproject.org/en-US/bootc/rpm-ostree/)
- [BOOTC_UPGRADE.md](./BOOTC_UPGRADE.md) - Upgrade and rollback procedures

## Sources

- [Kernel Vanilla Repositories - Fedora Project Wiki](https://fedoraproject.org/wiki/Kernel_Vanilla_Repositories)
- [Kernel-install integration with dnf and rpm-ostree - Fedora Discussion](https://discussion.fedoraproject.org/t/kernel-install-integration-with-dnf-and-rpm-ostree-coming-to-bootc-images/143217)
- [override replace --experimental | rpm-ostree](https://coreos.github.io/rpm-ostree/ex-replace/)
- [Fedora Linux Kernel Overview :: Fedora Docs](https://docs.fedoraproject.org/en-US/quick-docs/kernel-overview/)
