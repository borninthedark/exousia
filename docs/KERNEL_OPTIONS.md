# Kernel Options for Exousia

This document explains how to run different kernel versions on your Exousia bootc images.

## Default Kernel (Current: CachyOS)

**As of the latest build, Exousia uses the CachyOS performance-optimized kernel by default.**

- **CachyOS kernel** → Latest kernel.org with BORE scheduler and performance patches
- Better performance than Fedora stable and vanilla mainline
- Optimized for desktop/gaming workloads
- **Requires: x86-64-v3 CPU** (Intel Haswell 2013+, AMD Excavator 2015+)

### Previous Default (Fedora Stable)
- **fedora-bootc:43** → Fedora 43 stable kernel (~6.11.x)
- Most tested and stable, but older
- Use if your CPU doesn't support x86-64-v3

## Alternative Kernel Options

### Option 1: CachyOS Kernel (Current Default) ⭐

Performance-optimized kernel with BORE scheduler and sched-ext support.

**Pros:**
- ✅ **Best performance** (desktop, gaming, general workloads)
- ✅ BORE (Burst-Oriented Response Enhancer) scheduler
- ✅ sched-ext support for custom schedulers
- ✅ AMD P-State Preferred Core enhancements
- ✅ Latest features + performance patches
- ✅ Secure Boot signed

**Cons:**
- ❌ Requires x86-64-v3 CPU (2013+ for Intel, 2015+ for AMD)
- ❌ Slightly less tested than Fedora stable

**How to Enable (Already Default):**

This is now the default! But if you need to re-enable:

```yaml
- type: script
  scripts:
    - dnf copr enable -y bieszczaders/kernel-cachyos
    - dnf install -y --allowerasing kernel-cachyos kernel-cachyos-headers kernel-cachyos-devel
```

**Runtime Override:**
```bash
sudo dnf copr enable -y bieszczaders/kernel-cachyos
sudo rpm-ostree override replace \
  --experimental --freeze \
  --from repo='copr:copr.fedorainfracloud.org:bieszczaders:kernel-cachyos' \
  kernel-cachyos
sudo systemctl reboot
```

### Option 2: Mainline Kernel (Vanilla)

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

**CachyOS is now the default!** But if you want to test other kernels:

1. **Test locally first:**
   ```bash
   # For vanilla mainline:
   sudo rpm-ostree override replace \
     --experimental --freeze \
     --from repo='copr:copr.fedorainfracloud.org:group_kernel-vanilla:mainline' \
     kernel kernel-core kernel-modules kernel-modules-core
   sudo systemctl reboot
   ```

2. **If it works well, bake it into your image:**
   - Update `adnyeus.yml` with the appropriate configuration
   - Rebuild and redeploy your image

3. **Keep previous kernel as fallback:**
   - bootc keeps multiple boot entries
   - If new kernel fails, you can boot to previous deployment

## Kernel Comparison

| Kernel Type | Version Example | Stability | Performance | Hardware Support | Desktop/Gaming |
|-------------|----------------|-----------|-------------|------------------|----------------|
| **CachyOS** ⭐ | 6.12.x | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| Fedora Stable | 6.11.5 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| Mainline | 6.12.1 | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| linux-next | 6.13-rc1 | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ |
| Rawhide | 6.13-git | ⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ |

**Notes:**
- **CachyOS**: Best overall for desktop/gaming, BORE scheduler excels at interactive workloads
- **Fedora Stable**: Most tested, but older features
- **Mainline**: Latest upstream, but no special optimizations
- **linux-next**: Bleeding edge, expect bugs
- **Rawhide**: Debug kernel, slow performance

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

- [CachyOS Kernel GitHub](https://github.com/CachyOS/linux-cachyos)
- [CachyOS COPR for Fedora](https://github.com/CachyOS/copr-linux-cachyos)
- [Fedora Kernel Vanilla Repositories Wiki](https://fedoraproject.org/wiki/Kernel_Vanilla_Repositories)
- [bootc rpm-ostree Integration](https://docs.fedoraproject.org/en-US/bootc/rpm-ostree/)
- [BOOTC_UPGRADE.md](./BOOTC_UPGRADE.md) - Upgrade and rollback procedures

## Sources

- [GitHub - CachyOS/copr-linux-cachyos: CachyOS Packages for Fedora](https://github.com/CachyOS/copr-linux-cachyos)
- [bieszczaders/kernel-cachyos - Fedora Copr](https://copr.fedorainfracloud.org/coprs/bieszczaders/kernel-cachyos)
- [CachyOS Kernel for Fedora with Secure Boot](https://gist.github.com/mikaeldui/bf3cd9b6932ff3a2d49b924def778ebb)
- [Kernel Vanilla Repositories - Fedora Project Wiki](https://fedoraproject.org/wiki/Kernel_Vanilla_Repositories)
- [Kernel-install integration with dnf and rpm-ostree - Fedora Discussion](https://discussion.fedoraproject.org/t/kernel-install-integration-with-dnf-and-rpm-ostree-coming-to-bootc-images/143217)
- [override replace --experimental | rpm-ostree](https://coreos.github.io/rpm-ostree/ex-replace/)
- [Fedora Linux Kernel Overview :: Fedora Docs](https://docs.fedoraproject.org/en-US/quick-docs/kernel-overview/)
