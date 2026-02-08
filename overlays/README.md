# Overlays

Static files, configurations, and scripts that are copied into the bootc image
at build time.

## Structure

```text
overlays/
├── base/       # Shared across all image types
├── sway/       # Sway desktop environment
└── deploy/     # Podman Quadlet container definitions
```

| Directory | Purpose |
|-----------|---------|
| [base/](base/) | PAM, polkit, tmpfiles, sysusers, packages, build tools |
| [sway/](sway/) | Sway configs, greetd, runtime and setup scripts, repos, session files |
| [deploy/](deploy/) | Quadlet `.container` files for Forgejo, runner, and local registry |

## How Overlays Work

The YAML blueprint (`adnyeus.yml`) references overlays via `files` modules:

```yaml
modules:
  - type: files
    files:
      - src: overlays/base/configs/
        dst: /etc/
        mode: "0644"
```

The transpiler converts these into `COPY` instructions in the generated
Containerfile. No heredocs are used (Hadolint incompatible).

## See Also

- [Overlay System](../docs/overlay-system.md) -- Detailed architecture docs
- [Blueprint](../adnyeus.yml) -- Main build configuration
