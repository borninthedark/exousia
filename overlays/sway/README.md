# Sway Overlay

Sway desktop environment configurations and scripts for Exousia images.

## Structure

```text
sway/
├── configs/
│   ├── greetd/       # greetd login manager configuration
│   ├── plymouth/     # Boot splash themes (bgrt-better-luks)
│   ├── sway/         # Sway WM configs and config.d snippets
│   └── swaylock/     # Swaylock configuration
├── repos/            # Custom YUM/DNF repository definitions
├── scripts/
│   ├── runtime/      # Runtime scripts (autotiling, lid, volume)
│   └── setup/        # Build-time setup scripts
└── session/
    ├── sway.desktop   # Wayland session file
    ├── environment    # Sway environment variables
    └── start-sway     # Session startup script
```

## Notes

- Uses `sway-config-minimal` (not upstream) with layered `config.d` overrides
- greetd is the login manager for all image types
- Plymouth is toggled via `build.enable_plymouth` in the blueprint

## See Also

- [Sway + greetd](../../docs/sway-session-greetd.md) -- Session docs
- [Blueprint](../../adnyeus.yml) -- Build configuration
