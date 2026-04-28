# Flatpak Verification

This guide explains what Exousia currently guarantees for Flatpak support and
how to verify that state accurately.

## Current Model

Exousia currently proves three things at build time:

1. the `flatpak` toolchain is installed
2. the Flathub remote is configured
3. a user-session service is present to ensure the user-scope Flathub remote
4. `default-flatpaks` install manifests are generated under
   `/usr/share/exousia/flatpaks/`

What Exousia does **not** currently prove in the built image:

- that a specific first-boot installer unit will exist under one universal name
- that Flatpak applications are already installed in the container image
- that a deployed system has consumed the manifests yet

So the supported contract is:

- **build time**: Flatpak runtime prerequisites and install lists exist
- **deployed system**: applications may be installed later by a runtime
  consumer or by an administrator

## Build-Time Verification

### Check the Flathub remote

```bash
flatpak remotes
```

Expected output should include `flathub`.

### Check generated install manifests

```bash
ls -l /usr/share/exousia/flatpaks/
cat /usr/share/exousia/flatpaks/system-install.list
```

If present, these files are the canonical build artifact produced by the
`default-flatpaks` module.

### Check the user-scope Flathub service

```bash
systemctl --user status ensure-user-flathub-remote.service
```

This service runs:

```bash
flatpak remote-add --if-not-exists flathub https://dl.flathub.org/repo/flathub.flatpakrepo
```

### Check Flatpak binary availability

```bash
which flatpak
flatpak remote-ls flathub --app --columns=application | head
```

## Runtime Verification

On a deployed system, verify whether applications have actually been installed:

```bash
flatpak list --app
flatpak list --runtime
```

Expected applications are defined in:

- `overlays/base/packages/common/flatpaks.yml`
- generated manifests in `/usr/share/exousia/flatpaks/`

## If No Apps Are Installed Yet

That is not automatically a build defect. It usually means the deployment has
not yet consumed the generated install manifests.

Check:

```bash
ls -l /usr/share/exousia/flatpaks/
flatpak remotes
systemctl list-unit-files | grep -i flatpak
journalctl -b | grep -i flatpak
```

If your environment has no runtime installer, install directly from the
generated manifest:

```bash
sudo xargs -a /usr/share/exousia/flatpaks/system-install.list -r flatpak install -y flathub
```

## Verification Script

Exousia ships `verify-flatpak-installation` as a helper. Treat it as a
runtime diagnostic tool, not as proof that the build itself preinstalled
applications.

```bash
sudo verify-flatpak-installation
```

## Repository Tests

The repository test suite currently verifies build-time Flatpak readiness, not
completed application installation:

- Flatpak binary exists
- Flathub is configured
- generated manifests/configuration are present
- Flatpak can query the configured remote

See:

- `tests/image_content.bats`
- `tests/overlay_content.bats`

## References

- [Module Reference](modules.md)
- [BlueBuild default-flatpaks Module](https://blue-build.org/reference/modules/default-flatpaks/)
- [Flatpak Documentation](https://docs.flatpak.org/)
