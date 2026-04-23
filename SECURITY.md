# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| Latest (main branch) | Yes |
| Older releases | No |

Only the latest image built from the `main` branch is supported with security
updates. Older tagged releases do not receive patches.

## Reporting a Vulnerability

If you discover a security vulnerability in Exousia, please report it
responsibly:

1. **Do not** open a public GitHub issue for security vulnerabilities.
2. Send a private report via
   [GitHub Security Advisories](https://github.com/borninthedark/exousia/security/advisories/new).
3. Include as much detail as possible: affected component, reproduction steps,
   and potential impact.

You should receive an acknowledgment within 48 hours. We will work with you
to understand the scope and develop a fix before any public disclosure.

## Security Measures

Exousia employs a defense-in-depth approach:

### CI/CD Pipeline

- **Checkov** -- Static analysis for Containerfile and IaC misconfigurations
- **Trivy** -- Container image vulnerability scanning (config + image)
- **Qualys** -- Repository SCA and container vulnerability scanning with SARIF upload to GitHub Security
- **Bandit** -- Python SAST for security anti-patterns
- **Hadolint** -- Dockerfile/Containerfile best-practice linting
- **Cosign** -- Image signing for supply-chain integrity
- **Dependabot** -- Automated dependency security updates

### Image Hardening

- Minimal package set (no unnecessary services)
- SELinux enforcing mode supported
- PAM U2F hardware authentication support
- composefs enabled for integrity verification
- bootc container lint enforced at build time
- Build-time caches and logs cleaned from final image

### Development Practices

- Pre-commit hooks enforce linting and security checks locally
- Conventional commits for auditable change history
- TDD with minimum 85% code coverage on Python tools (current: 94%)

## Active Remediations

| Package | Minimum Version | Reason | Date Pinned |
|---------|----------------|--------|-------------|
| flatpak | >= 1.16.6 | CVE remediation ([release notes](https://github.com/flatpak/flatpak/releases/tag/1.16.6)) | 2026-04-12 |

## RPM Override Process

When Fedora has not yet shipped a patched version of a package, Exousia can
build the fix from upstream source and inject it into the image at build time.
This is how the flatpak CVE (disclosed 2026-04-12) was remediated before
Fedora shipped `>= 1.16.6`.

### 1. Build the RPM from upstream source

Use a Fedora toolbox to isolate the build environment:

```bash
toolbox enter

# Install build dependencies
sudo dnf builddep flatpak
sudo dnf install rpmdevtools rpm-build

# Set up the RPM build tree
rpmdev-setuptree

# Download the Fedora SRPM as the base spec
dnf download --source flatpak
rpm -ivh flatpak-*.src.rpm

# Replace the upstream tarball with the patched release
cd ~/rpmbuild/SOURCES
curl -LO https://github.com/flatpak/flatpak/releases/download/1.16.6/flatpak-1.16.6.tar.xz

# Patch the spec: bump Version, update changelog
cd ~/rpmbuild/SPECS
# Edit flatpak.spec — set Version: 1.16.6 and add a %changelog entry

# Build (disable debuginfo if not needed)
rpmbuild -bb --define "debug_package %{nil}" flatpak.spec
```

The output RPMs land in `~/rpmbuild/RPMS/x86_64/`.

### 2. Host the RPMs on GHCR as a scratch OCI image

Package the RPMs into a minimal OCI image so the Containerfile can
`COPY --from` them:

```bash
# Create a staging directory
mkdir -p /tmp/flatpak-rpms && cp ~/rpmbuild/RPMS/x86_64/flatpak-*.rpm /tmp/flatpak-rpms/

# Build and push a scratch image containing only the RPMs
cat <<'DOCKERFILE' > /tmp/flatpak-rpms/Containerfile
FROM scratch
COPY *.rpm /rpms/
DOCKERFILE

podman build -t ghcr.io/borninthedark/flatpak-rpms:1.16.6 /tmp/flatpak-rpms/
podman login ghcr.io
podman push ghcr.io/borninthedark/flatpak-rpms:1.16.6
```

### 3. Register the override in the package spec

Add an entry to `overlays/base/packages/common/rpm-overrides.yml`:

```yaml
spec:
  overrides:
    - package: flatpak
      version: ">= 1.16.6"
      image: ghcr.io/borninthedark/flatpak-rpms:1.16.6
      reason: CVE remediation (disclosed 2026-04-12)
      replaces:
        - flatpak
        - flatpak-libs
        - flatpak-session-helper
        - flatpak-selinux
```

The `replaces` list names every sub-package the RPM build produces. The
transpiler (`yaml-to-containerfile.py`) reads this spec via
`PackageLoader.load_rpm_overrides()` and generates:

1. `COPY --from=ghcr.io/borninthedark/flatpak-rpms:1.16.6 /rpms/ /tmp/rpm-override-0/`
2. `RUN dnf install -y /tmp/rpm-override-0/*.rpm`

These stages run after the main `dnf install`, overriding the repo version.

### 4. Ensure CI can pull from GHCR

The build workflow (`hiyori.yml`) authenticates with GHCR before the image
build step so that `COPY --from` can pull the override image:

```yaml
- name: Login to GHCR (pull RPM overrides)
  uses: docker/login-action@v4
  with:
    registry: ghcr.io
    username: ${{ github.actor }}
    password: ${{ secrets.GHCR_PAT }}
```

### 5. Remove the override when Fedora catches up

Once Fedora ships a version that satisfies the minimum version constraint,
remove the entry from `rpm-overrides.yml` and the corresponding row from the
Active Remediations table above. The image on GHCR can be deleted or left
as an archive.

## Dependency Management

Dependencies are managed via:

- **GitHub Dependabot** for automated security updates on Actions and pip
  dependencies
- **uv lock** for reproducible Python dependency resolution

## Qualys CI Integration

Qualys scanning is integrated into the GitHub Actions pipeline in two places:

- `Uhin` runs `qualys/qualys-github/code-scan@v1` against the repository
- `Hiyori` runs `qualys/qualys-github/container-scan@v1` against the built image on `main`

Required GitHub configuration:

- Actions secret: `QUALYS_ACCESS_TOKEN`
- Actions variable: `QUALYS_POD`

Example POD values include `US1`, `US2`, `US3`, and `EU1`.

The integration is configured to skip cleanly when those values are not set, so
the pipeline remains usable before Qualys credentials are provisioned.

## Contact

For security-related questions that are not vulnerability reports, open a
regular GitHub issue.
