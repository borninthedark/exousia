# ZFS on Fedora bootc Images

OpenZFS kernel module support for Exousia bootc images.

## Overview

ZFS modules are built at image build time using DKMS against the kernel
shipped in the base image. This produces a self-contained bootc image with
ZFS support baked in -- no runtime compilation required on the target host.

## How It Works

1. The `build-zfs-kmod` script (Python) runs during the image build.
2. It adds the [ZFS on Linux](https://zfsonlinux.org/) Fedora repository.
3. Installs `zfs` and build dependencies (`kernel-devel`, `dkms`, `gcc`, etc.).
4. Runs `dkms autoinstall` to compile the ZFS module against the image kernel.
5. Verifies `zfs.ko` exists under `/usr/lib/modules/<kver>/extra/zfs/`.
6. Runs `depmod` for the target kernel.
7. Removes build-time-only packages (gcc, make, devel headers) to keep the
   image small.

## Enabling ZFS

ZFS is **disabled by default**. To enable it, add the ZFS build step to
`adnyeus.yml`:

```yaml
# Optional: ZFS filesystem support
- type: script
  condition: enable_zfs == true
  scripts:
    - /usr/local/bin/build-zfs-kmod
```

Then set `enable_zfs: true` in the `build:` section:

```yaml
build:
  enable_plymouth: true
  enable_zfs: true
```

## Package Definition

The ZFS package list lives in `overlays/base/packages/common/zfs.yml` and
includes the ZFS userspace tools plus all build dependencies needed for DKMS.

## DKMS vs Pre-built Kmod

| Approach | Pros | Cons |
|----------|------|------|
| **DKMS** (this project) | Works with any kernel version | Slower build, needs compiler in image temporarily |
| **Pre-built kmod RPM** | Fast install, no compiler needed | Must match exact kernel version; breaks on kernel updates |

Exousia uses DKMS because bootc images pin the kernel at build time, and DKMS
guarantees the module matches exactly.

## ZFS Pool Import on bootc Systems

After booting an image with ZFS support:

```bash
# Load the module
sudo modprobe zfs

# Import existing pools
sudo zpool import -a

# Auto-load ZFS at boot
echo zfs | sudo tee /etc/modules-load.d/zfs.conf
```

### Persistent Mounts

Add ZFS datasets to `/etc/fstab` or use the ZFS `canmount` property:

```bash
# Set a dataset to auto-mount
sudo zfs set canmount=on mountpoint=/data tank/data
```

## Limitations

- The ZFS kmod must match the running kernel exactly. If the host boots a
  different kernel than what the image was built with, ZFS will not load.
  Use `bootc upgrade` to keep the host kernel in sync with the image.
- ZFS as root filesystem (`/`) is **not supported** in bootc images. bootc
  manages the root via ostree/composefs. Use ZFS for data pools only.
- The DKMS build adds time to image builds (typically 2-5 minutes).
- ZFS modules are not signed for Secure Boot. Disable Secure Boot or enroll
  a MOK key if needed.

## dracut Integration

If ZFS pools need to be available during early boot (e.g., for `/home`),
add ZFS to dracut:

```bash
echo 'add_dracutmodules+=" zfs "' >> /etc/dracut.conf.d/zfs.conf
echo 'force_drivers+=" zfs "' >> /etc/dracut.conf.d/zfs.conf
```

This is **not** done automatically by Exousia since ZFS-as-root is not
a supported configuration for bootc.

## Troubleshooting

### Module fails to build

Check the DKMS build log:

```bash
tail -n 30 /var/lib/dkms/zfs/*/build/make.log
```

Common causes:
- Kernel headers mismatch: ensure `kernel-devel` matches the installed kernel.
- GPL symbol errors: the kernel version may not yet be supported by OpenZFS.
  Check [OpenZFS compatibility](https://openzfs.github.io/openzfs-docs/Getting%20Started/Fedora/index.html).

### Module loads but pool won't import

```bash
# Check ZFS version
zfs version

# Check pool status
zpool status

# Force import if pool was last used on a different host
zpool import -f <pool-name>
```

## References

- [OpenZFS Fedora Getting Started](https://openzfs.github.io/openzfs-docs/Getting%20Started/Fedora/index.html)
- [ZFS on Linux](https://zfsonlinux.org/)
- [bootc documentation](https://bootc-dev.github.io/bootc/)
