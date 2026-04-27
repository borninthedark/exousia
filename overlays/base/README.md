# Base Overlay

Shared configurations and tools included in all Exousia image types.

## Structure

```text
base/
├── configs/         # PAM, AIDE, containers, skel, sysctl, and auth configs
├── configs-zfs/     # ZFS-specific staged configs
├── packages/        # YAML package definitions and kernel profiles
├── systemd/         # System and user units
├── sysusers/        # systemd-sysusers configs (bootc + atomic)
├── tmpfiles/        # Tmpfiles definitions staged into the image
└── tools/           # Image utilities copied to /usr/local/bin/
```

## See Also

- [Package Definitions](packages/) -- YAML package lists
- [Overlay System](../../docs/overlay-system.md) -- Architecture docs
