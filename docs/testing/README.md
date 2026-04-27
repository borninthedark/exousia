# Testing Documentation

Entry point for the Exousia test docs.

## Quick Start

```bash
make test                                          # pytest (tools/)
make overlay-test                                  # bats overlay validation
make local-test                                    # bats against built image

export TEST_IMAGE_TAG=localhost:5000/exousia:latest
buildah unshare -- bats -r tests/
```

## Canonical Docs

- **[Test Suite Guide](./guide.md)**: primary testing documentation for architecture, execution, and coverage
- **[Test Suite Reference](./test-suite.md)**: compact category and command reference
- **[Writing Tests](../reference/writing-tests.md)**: patterns for adding or updating Bats coverage
- **[Troubleshooting](../reference/troubleshooting.md)**: common failures and debugging steps

## Scope

The suite validates built images and source overlays with:

- Bats tests under `tests/`
- image-aware assertions for `fedora-bootc` and `fedora-sway-atomic`
- verification of package selection, overlay staging, services, Flatpak setup, and bootc compliance

`make local-test` is the supported Make entrypoint for the built-image Bats
suite. It now exports `TEST_IMAGE_TAG` and runs the image suite under
`buildah unshare`, matching the direct invocation shown above.

For details, use [guide.md](./guide.md). This file stays intentionally short so it does not duplicate the guide.
