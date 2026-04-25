# RPM Overrides

How Exousia installs selected packages from prebuilt RPM artifacts instead of
the Fedora repositories.

## Contents

- [What RPM Overrides Are](#what-rpm-overrides-are)
- [Source of Truth](#source-of-truth)
- [Schema](#schema)
- [How the Build Uses Overrides](#how-the-build-uses-overrides)
- [When to Use Them](#when-to-use-them)
- [Operational Requirements](#operational-requirements)
- [Lifecycle](#lifecycle)
- [Example](#example)

---

## What RPM Overrides Are

An RPM override tells Exousia:

1. which package family should come from an external RPM artifact
2. which OCI image contains the replacement RPM files
3. which repo-installed packages those RPMs replace
4. why the override exists

The main use case is security remediation when Fedora has not yet shipped the
fixed package version you need.

Exousia does **not** use RPM overrides as a general package-management layer.
They are a targeted escape hatch for exceptions such as:

- urgent CVE remediation
- patched upstream builds not yet available in Fedora
- temporary package replacement during a transition window

---

## Source of Truth

The authoritative file is:

`overlays/base/packages/common/rpm-overrides.yml`

Current schema header:

```yaml
apiVersion: exousia.packages/v1alpha1
kind: PackageOverrideBundle
```

The package loader reads this file through
`PackageLoader.load_rpm_overrides()` in
[tools/package_loader/loader.py](../tools/package_loader/loader.py).

If the file is missing, the loader returns an empty list and the build
continues without overrides.

---

## Schema

Each override entry lives under `spec.overrides`.

Example shape:

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

Field meaning:

- `package`
  The logical package being overridden.

- `version`
  The minimum version goal or effective replacement version the override is
  intended to satisfy.

- `image`
  The OCI image that contains the built RPM artifacts under `/rpms/`.

- `reason`
  Human-readable explanation for why the override exists.

- `replaces`
  Every RPM package name that should be satisfied by the override payload.
  This list matters because Exousia must avoid reinstalling conflicting repo
  versions during the main `dnf` phase.

---

## How the Build Uses Overrides

The generator integrates RPM overrides in two places.

### 1. It stages the override RPMs

In [tools/generator/processors.py](../tools/generator/processors.py), Exousia:

- loads the override list from the package loader
- emits one `COPY --from=...` per override image
- copies `/rpms/` from the OCI artifact into a temporary build directory

This produces Containerfile fragments like:

```dockerfile
# RPM override: CVE remediation (disclosed 2026-04-12)
COPY --from=ghcr.io/borninthedark/flatpak-rpms:1.16.6 /rpms/ /tmp/rpm-override-0/
```

### 2. It installs the override RPMs after the main package install

Later in the same processor, Exousia emits:

```dockerfile
RUN dnf install -y /tmp/rpm-override-0/*.rpm
```

This happens after the base package install phase, so the override RPMs replace
the repo-provided packages in the final image.

### 3. It filters the main install path

The generator also uses the override metadata to avoid conflicting package
requests during the regular install phase. The `replaces` list is the key input
for that behavior.

---

## When to Use Them

Use an RPM override when all of the following are true:

- the package is required in the image
- Fedora has not yet shipped the fixed or desired build
- removing the package is not acceptable
- you can provide a verified replacement RPM artifact

Do **not** use an RPM override when:

- the vulnerable package can simply be removed
- Fedora already ships an acceptable fixed version
- the package is only needed temporarily for debugging
- the replacement is not reproducible or not documented

---

## Operational Requirements

RPM overrides depend on registry access.

### CI

Hiyori must be able to authenticate to GHCR before the image build so
`COPY --from=ghcr.io/...` can pull the override image.

Required secret:

- `GHCR_PAT`

### Local builds

Local builders must also be logged into GHCR if the override artifact is not
publicly pullable:

```bash
podman login ghcr.io
```

### Artifact layout

The referenced OCI image must contain the RPM payload at:

`/rpms/`

That is the path the generated Containerfile expects.

---

## Lifecycle

Treat RPM overrides as temporary.

Recommended lifecycle:

1. identify the package/CVE gap
2. build patched RPMs
3. publish them as an OCI artifact
4. register the override in `rpm-overrides.yml`
5. rebuild and re-scan the image
6. remove the override once Fedora catches up

Any active override should also be reflected in:

- [docs/cve-remediation.md](cve-remediation.md)
- [SECURITY.md](../SECURITY.md) when relevant to current security posture

---

## Example

The current flatpak remediation is the reference example.

Source spec:

- [overlays/base/packages/common/rpm-overrides.yml](../overlays/base/packages/common/rpm-overrides.yml)

Related operational doc:

- [docs/cve-remediation.md](cve-remediation.md)

That example shows the full path:

- patched RPMs built outside the image
- OCI artifact hosted on GHCR
- override registered in Exousia
- final image consuming the replacement packages during assembly
