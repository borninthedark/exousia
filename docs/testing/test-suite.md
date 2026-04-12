# Test Suite Reference

Compact reference for the current Exousia test surface. The canonical narrative guide is [guide.md](./guide.md).

## Test Locations

```text
custom-tests/
├── image_content.bats      # built image validation
└── overlay_content.bats    # source overlay and static config validation
```

## Category Reference

| Category | Primary Scope |
|---|---|
| OS and version | Fedora identity, release expectations, image metadata |
| Container auth | tmpfiles wiring and container auth behavior |
| Packages | installed RPMs, removals, DNF5 behavior, repo setup |
| Plymouth | theme assets, dracut config, kernel args when enabled |
| Flatpak | Flathub setup and default-flatpaks behavior |
| Sway session | greetd, session assets, config presence |
| System users | sysusers output and expected service users |
| bootc compliance | `bootc container lint`, ComposeFS, bootc-specific layout |
| Overlay content | presence and validity of staged source files before build |

## Common Commands

```bash
make test
make test-run
buildah unshare -- bats -r custom-tests/
buildah unshare -- bats custom-tests/image_content.bats --filter "Plymouth"
```

## Related Docs

- [guide.md](./guide.md)
- [../reference/writing-tests.md](../reference/writing-tests.md)
- [../reference/troubleshooting.md](../reference/troubleshooting.md)
