# Base Overlay

Shared configurations and tools included in all Exousia image types.

## Structure

```text
base/
├── configs/        # PAM, polkit, tmpfiles configurations
│   ├── pam.d/      # PAM authentication (YubiKey U2F)
│   ├── polkit/     # Polkit rules
│   └── tmpfiles/   # tmpfiles.d entries
├── packages/       # YAML package definitions
│   ├── common/     # Base, remove, flatpaks, ZFS
│   └── window-managers/  # Sway packages
├── sysusers/       # systemd-sysusers configs
│   └── bootc.conf  # System user definitions
└── tools/          # Build-time scripts (copied to /usr/local/bin/)
```

## See Also

- [Package Definitions](packages/) -- YAML package lists
- [Overlay System](../../docs/overlay-system.md) -- Architecture docs
