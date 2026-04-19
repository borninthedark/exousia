# ZFS Implementation Plan

This document captures the intended ZFS integration for Exousia. It is a reference plan, not active build behavior yet.

## Objective

Add OpenZFS support to the image in a way that is compatible with the current bootc build model:

- install ZFS userspace tooling
- build the OpenZFS kernel modules for the installed kernel set
- add the required modules into initramfs
- enable the systemd units needed for pool import and ZFS runtime behavior

The immediate target is usable in-image ZFS support. Root-on-ZFS is a separate later phase.

## Current State

The repo already contains pieces of the implementation:

- typed ZFS package bundle in [zfs.yml](../overlays/base/packages/common/zfs.yml)
- DKMS build helper in [build-zfs-kmod](../overlays/base/tools/build-zfs-kmod)
- modules-load config in [zfs.conf](../overlays/base/configs-zfs/modules-load.d/zfs.conf)
- tests that expect ZFS artifacts in [image_content.bats](../custom-tests/image_content.bats)

What is missing is the actual build wiring:

- `enable_zfs` does not currently select the `zfs` bundle in the blueprint
- the module build helper is not invoked from the image build
- dracut is not configured to include ZFS
- initramfs is not rebuilt after the ZFS module build
- `zfs.target` and `zfs-import-scan.service` are not enabled in the blueprint

## Required Contract

When `enable_zfs == true`, the build should do all of the following:

1. Select the ZFS package feature bundle.
2. Install ZFS userspace and build dependencies.
3. Build OpenZFS kernel modules for every kernel present in `/usr/lib/modules`.
4. Run `depmod` for each built kernel.
5. Add dracut configuration so ZFS modules are included in initramfs.
6. Rebuild initramfs after the module build.
7. Enable the required ZFS systemd units.
8. Verify both userspace and kernel integration in tests.

## Implementation Phases

### Phase 1: In-image ZFS support

This phase does not assume root-on-ZFS. It provides working ZFS tooling and boot-aware module availability.

#### 1. Blueprint integration

In [adnyeus.yml](../adnyeus.yml), when `enable_zfs == true`:

- add `zfs` to the `package-loader` `feature_bundles`
- copy `overlays/base/configs-zfs/` into `/etc/`
- run `/usr/local/bin/build-zfs-kmod`
- write a ZFS dracut config file
- rebuild initramfs for each installed kernel
- enable:
  - `zfs.target`
  - `zfs-import-scan.service`

#### 2. Kernel module build helper

Refine [build-zfs-kmod](../overlays/base/tools/build-zfs-kmod) so it:

- supports `--all-kernels`
- iterates every kernel under `/usr/lib/modules`
- verifies the expected OpenZFS module chain, not just `zfs.ko`
- exits clearly when headers or module outputs are missing
- keeps package installation/build/cleanup steps explicit

Recommended module verification list:

- `icp`
- `spl`
- `zavl`
- `znvpair`
- `zunicode`
- `zcommon`
- `zfs`

Exact names may vary slightly by packaging layout, but the helper should verify the actual OpenZFS dependency set instead of a single module.

#### 3. Dracut integration

Add a ZFS dracut config such as:

```text
/usr/lib/dracut/dracut.conf.d/zfs.conf
```

This config should:

- add the ZFS-related kernel drivers/modules needed in initramfs
- coexist with Plymouth dracut configuration
- be generated or installed only when ZFS is enabled

The critical ordering is:

1. install ZFS packages
2. build DKMS modules
3. run `depmod`
4. write dracut ZFS config
5. rebuild initramfs

### Phase 2: Stronger verification

Extend tests in [image_content.bats](../custom-tests/image_content.bats) so they verify:

- all required OpenZFS modules exist for each installed kernel
- dracut ZFS config exists
- rebuilt initramfs exists for each kernel
- `modules.dep` references the ZFS module stack
- `lsinitrd` output includes ZFS content
- `zfs.target` is enabled
- `zfs-import-scan.service` is enabled

### Phase 3: Root-on-ZFS evaluation

Only after Phase 1 is stable should the repo consider root-on-ZFS.

That work would require additional decisions around:

- pool import timing in initramfs
- hostid handling
- cachefile strategy versus scan-based import
- bootloader and kernel command line expectations
- rollback/upgrade behavior for bootc images using ZFS root

This should be treated as a separate project.

## Build Pipeline Implications

The package-management refit should eventually make ZFS visible in the resolved build plan.

Example expected build-plan actions when `enable_zfs == true`:

```json
{
  "features": ["zfs"],
  "rpm": {
    "install": ["zfs", "kernel-devel", "dkms"]
  },
  "build_actions": [
    "build-zfs-kmod --all-kernels",
    "depmod",
    "write-zfs-dracut-config",
    "rebuild-initramfs"
  ],
  "systemd": {
    "enable": ["zfs.target", "zfs-import-scan.service"]
  }
}
```

That is the right long-term contract because it ties package selection to the required post-install integration steps.

## Immediate Next Steps

When ZFS becomes active work, the recommended order is:

1. Wire `enable_zfs` into [adnyeus.yml](../adnyeus.yml).
2. Invoke [build-zfs-kmod](../overlays/base/tools/build-zfs-kmod) conditionally.
3. Add ZFS dracut configuration.
4. Rebuild initramfs after DKMS output exists.
5. Enable `zfs.target` and `zfs-import-scan.service`.
6. Strengthen image tests around the built modules and initramfs contents.

## Non-Goals For Now

- root-on-ZFS
- encrypted ZFS root boot flow
- snapshot/rollback boot integration
- automatic pool creation during image build

Those can be revisited once the image-level ZFS support path is stable.
