# Sway Overlay

Sway desktop environment configurations and scripts for Exousia images.

## Structure

```text
sway/
├── configs/
│   ├── greetd/       # greetd login manager configuration
│   ├── plymouth/     # Boot splash themes (bgrt-better-luks)
│   ├── sway/         # Sway WM config, config.d snippets, environment
│   ├── swaylock/     # Swaylock configuration (Kripton theme)
│   └── xdg/waybar/   # Waybar config and Kripton theme CSS
├── repos/            # Custom YUM/DNF repository definitions
├── scripts/
│   ├── runtime/      # Runtime scripts (autotiling, lid, volume)
│   └── setup/        # Build-time setup scripts
└── session/
    ├── sway.desktop   # Wayland session file
    └── start-sway     # Session startup script
```

## Notes

- Uses a custom sway config with layered `config.d` overrides and the Kripton color scheme
- System-level configs (`/etc/sway/`, `/etc/xdg/waybar/`, `/etc/swaylock/`) apply to all users
- User-level defaults for new accounts are seeded from `/etc/skel/.config/`
- greetd is the login manager for all image types
- Plymouth is toggled via `build.enable_plymouth` in the blueprint

## See Also

- [Sway + greetd](../../docs/sway-session-greetd.md) -- Session docs
- [Blueprint](../../adnyeus.yml) -- Build configuration
