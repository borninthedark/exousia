# Kernel and Module Artifact Plan

This document replaces the earlier ZFS-only implementation sketch with a more
general design for custom kernels and out-of-tree kernel modules in Exousia.

OpenZFS remains the first intended implementation, but the goal is broader:

- support alternative kernel versions
- support custom-built kernels
- support reusable out-of-tree kernel module workflows
- keep the final bootc image reproducible and reasonably small

The key design change is this:

- **development fallback**: build modules in-image with helper scripts when needed
- **preferred production path**: build kernel and module RPM artifacts outside
  the final image, publish them as OCI artifacts, and install them during image
  build

That model works for OpenZFS, NVIDIA, VirtualBox, custom filesystem modules,
and future kernel variants without turning `adnyeus.yml` into a shell-script
dump.

## Objective

Add support for:

1. selecting a non-default kernel for the image
2. installing prebuilt kernel-module RPM artifacts matched to that kernel
3. performing the required boot integration declaratively
4. making the resulting build plan visible and testable

For OpenZFS specifically, that means:

- install ZFS userspace tooling
- install kernel-matched ZFS module RPMs
- run `depmod`
- include ZFS in initramfs
- enable the required ZFS services

But the design should not stop at ZFS.

## Design Principles

1. Kernel choice is a first-class build input.
2. Kernel modules should be treated as installable artifacts, not ad hoc build
   side effects.
3. The final image build should prefer consuming prepared RPM artifacts over
   running DKMS in the production image path.
4. Boot integration should be declarative and visible in the resolved build
   plan.
5. ZFS should be the first consumer of the framework, not the framework itself.

## Current State

The repo already contains useful building blocks:

- typed ZFS package set in [zfs.yml](../overlays/base/packages/common/zfs.yml)
- a ZFS build helper in [build-zfs-kmod](../overlays/base/tools/build-zfs-kmod)
- RPM override support in [rpm-overrides.yml](../overlays/base/packages/common/rpm-overrides.yml)
- transpiler support for pulling RPM artifacts from OCI images in
  [yaml-to-containerfile.py](../tools/yaml-to-containerfile.py)
- existing `enable_zfs` condition plumbing in the transpiler and config
  resolver
- a separate kernel guidance document in [kernel-options.md](kernel-options.md)

Those pieces are enough to define a better architecture without starting from
zero.

## Problem With the Old ZFS-Only Plan

The earlier plan was useful as a phase-1 spike, but it had three major
limitations:

1. It was too ZFS-specific.
   The document assumed a single feature-specific build flow instead of a
   reusable kernel/module model.

2. It was too DKMS-centric.
   Building modules inside the final image is fine for local experimentation,
   but it is the wrong default abstraction for a production-quality bootc
   pipeline.

3. It mixed artifact production and artifact consumption.
   The final image should ideally install prepared artifacts, not become the
   environment that compiles them.

## Recommended Architecture

Use a three-layer model:

1. **kernel profile**
2. **module artifact pipeline**
3. **boot integration**

### 1. Kernel Profile

This selects the kernel family and version to include in the image.

Examples:

- Fedora stable kernel
- CachyOS kernel
- Fedora vanilla mainline kernel
- custom kernel RPM set built by you

The kernel profile should define:

- which kernel RPMs are installed or replaced
- whether the source is a repo, COPR, or OCI artifact
- the expected `kernel-devel` and `kernel-headers` pairing
- any version pinning rules

The important design point is that kernel choice should not be expressed
primarily as loose script snippets in the blueprint.

### 2. Module Artifact Pipeline

This produces installable RPM artifacts for out-of-tree modules matched to the
selected kernel.

Examples:

- OpenZFS
- NVIDIA
- VirtualBox
- a custom driver or filesystem module

Preferred production model:

1. build module RPMs in a dedicated builder image or CI job
2. publish the resulting RPMs as an OCI artifact
3. have the final image build `COPY --from` those RPMs
4. install the RPMs with `dnf`

This reuses the same idea already implemented for security-related RPM
overrides, but broadens it to kernel and module artifacts.

### 3. Boot Integration

After kernel and module artifacts are installed, the image may still need
boot-aware configuration:

- `depmod`
- dracut module inclusion
- initramfs rebuild
- `modules-load.d`
- kernel arguments
- systemd unit enablement

These actions should be expressed declaratively and emitted into the resolved
build plan, not buried in one-off scripts where possible.

## Why OCI-Hosted RPM Artifacts Are the Better Default

Compared with DKMS-in-image, prebuilt artifacts have several advantages:

- more reproducible builds
- better CI caching
- smaller final images
- no requirement to carry compiler toolchains in the production image path
- cleaner support for multiple kernels
- easier reuse across multiple module types

For ZFS specifically, this means:

- **preferred path**: build kernel-matched ZFS RPM artifacts elsewhere, then
  install them in the image
- **fallback path**: keep DKMS helper scripts only for local experiments,
  debugging, or bring-up

## Proposed Contract

The long-term build contract should be explicit enough that the resolved build
plan can answer all of these:

- which kernel profile was selected?
- which module profiles were selected?
- which RPM artifacts were installed?
- which package sets were installed?
- which dracut/initramfs actions were required?
- which systemd units were enabled?

### Example resolved-plan shape

```json
{
  "image": {
    "name": "exousia",
    "base_image": "quay.io/fedora/fedora-bootc:43",
    "image_type": "fedora-bootc",
    "fedora_version": "43"
  },
  "kernel": {
    "profile": "fedora-mainline",
    "artifacts": [
      {
        "image": "ghcr.io/example/kernel-mainline-rpms:6.14.2",
        "replaces": [
          "kernel",
          "kernel-core",
          "kernel-modules",
          "kernel-modules-core",
          "kernel-modules-extra",
          "kernel-devel",
          "kernel-headers"
        ]
      }
    ]
  },
  "modules": [
    {
      "name": "zfs",
      "artifacts": [
        {
          "image": "ghcr.io/example/zfs-kmod-rpms:6.14.2-zfs-2.3.1",
          "packages": [
            "kmod-zfs",
            "zfs"
          ]
        }
      ],
      "boot": {
        "depmod": true,
        "dracut_modules": [
          "zfs"
        ],
        "modules_load": [
          "zfs"
        ],
        "enable_units": [
          "zfs.target",
          "zfs-import-scan.service"
        ]
      }
    }
  }
}
```

The exact schema can evolve, but this is the right level of explicitness.

## Recommended Spec Extensions

Exousia does not need all of this immediately, but the current package model is
a natural place to grow the feature set.

### A. Kernel overrides

Analogous to the existing RPM override flow, but for whole kernel sets.

Conceptual shape:

```yaml
spec:
  kernel_overrides:
    - name: kernel-mainline
      image: ghcr.io/example/kernel-mainline-rpms:6.14.2
      reason: Mainline kernel for ZFS validation
      replaces:
        - kernel
        - kernel-core
        - kernel-modules
        - kernel-modules-core
        - kernel-modules-extra
        - kernel-devel
        - kernel-headers
```

### B. Module overrides

Module-specific OCI-hosted RPM artifacts with boot integration metadata.

Conceptual shape:

```yaml
spec:
  module_overrides:
    - name: zfs
      image: ghcr.io/example/zfs-kmod-rpms:6.14.2-zfs-2.3.1
      reason: OpenZFS modules for kernel 6.14.2
      packages:
        - kmod-zfs
        - zfs
      boot:
        depmod: true
        dracut_modules:
          - zfs
        modules_load:
          - zfs
        enable_units:
          - zfs.target
          - zfs-import-scan.service
```

These do not need to be implemented as package YAML keys immediately, but they
show the right boundary.

## ZFS as the First Implementation

OpenZFS should be used to prove the generalized model.

### Preferred production path

1. select a target kernel profile
2. build kernel-matched ZFS RPM artifacts in CI or a builder container
3. publish them as an OCI artifact
4. install them during the image build
5. run `depmod`
6. install or write ZFS dracut config
7. rebuild initramfs
8. enable ZFS units
9. test the result

### Developer fallback path

Retain [build-zfs-kmod](../overlays/base/tools/build-zfs-kmod) only as a local
bring-up and experimentation path.

That script is still useful for:

- quickly testing a new kernel locally
- debugging OpenZFS build failures
- verifying assumptions before moving the logic into a proper artifact pipeline

But it should not be the intended long-term production path.

## What To Change in the Existing ZFS Helper

If `build-zfs-kmod` remains in the repo as a developer fallback, it should be
improved so it is less fragile:

- support all installed kernels, not just the newest detected one
- validate the full OpenZFS module chain, not just `zfs.ko`
- make build dependencies explicit and minimal
- emit clearer diagnostics when header versions do not match
- keep cleanup optional for easier debugging

That still does not make it the preferred architecture. It only makes the
fallback path less painful.

## Build-System Changes Recommended

### 1. Generalize the current RPM override mechanism

The transpiler already supports staging RPMs from OCI images before install.

This should be extended conceptually from:

- “security override for one package”

to:

- kernel artifact overrides
- module artifact overrides
- security remediation overrides

That gives you one artifact-ingestion path instead of multiple special cases.

### 2. Add resolved-plan support for kernel and module actions

The resolved plan should eventually include:

- selected kernel profile
- selected module profiles
- OCI artifact sources
- package replacements
- required boot actions

This is the right place to make kernel/module behavior visible to CI and tests.

### 3. Separate artifact production from image assembly

The image assembly stage should consume:

- package-set selections
- kernel artifacts
- module artifacts

It should not also become the place where arbitrary external modules are
compiled by default.

## Testing Requirements

The generalized model should be tested at three layers.

### 1. Resolver and transpiler tests

Validate:

- kernel profile selection
- module profile selection
- artifact staging output
- generated `COPY --from` behavior
- generated dracut and systemd integration

### 2. Image-content tests

For ZFS and future modules, verify:

- expected RPMs are installed
- expected modules exist for each installed kernel
- `modules.dep` contains the module stack
- dracut config exists
- rebuilt initramfs exists
- `lsinitrd` includes the required module content
- expected systemd units are enabled

### 3. Boot/runtime tests

For any module that matters at boot or storage time:

- module can be loaded
- services start correctly
- the target feature works with the selected kernel

For ZFS specifically:

- `modprobe zfs` succeeds
- `zpool` and `zfs` userspace tools are present
- import-related services are enabled and behave as expected

## Practical Path Forward

This is the optimized implementation order.

### Phase 1: Reframe the architecture

Keep this document as the canonical plan for:

- custom kernels
- out-of-tree module artifacts
- ZFS as the first implementation

Do not continue designing ZFS as a one-off special case.

### Phase 2: Keep the current helper as fallback only

Do not delete `build-zfs-kmod`, but stop treating it as the primary target
architecture.

### Phase 3: Extend the artifact model

Build the design around OCI-hosted RPM artifacts for:

- kernel overrides
- module overrides
- security remediations

This should become the main supported path.

### Phase 4: Implement ZFS on top of that model

For the first usable OpenZFS path:

1. define the kernel profile to support
2. produce ZFS RPM artifacts for that kernel
3. install them during image build
4. add declarative dracut/modules-load/systemd integration
5. test thoroughly

### Phase 5: Generalize to additional modules

Once the artifact contract exists, adding future modules becomes mostly:

- artifact build
- metadata declaration
- boot integration metadata
- tests

## Immediate Recommendations

If you want to move now without overengineering:

1. do **not** make DKMS-in-image the final design
2. do use ZFS as the first module to prove a generic kernel/module artifact flow
3. do extend the current OCI RPM override model rather than inventing a second
   artifact-ingestion path
4. do treat custom kernels and custom modules as separate but cooperating layers
5. do make kernel and module behavior visible in the resolved build plan

## Non-Goals For This Document

- root-on-ZFS boot design
- encrypted ZFS root boot flow
- automatic pool creation
- complete secure-boot signing workflow for self-built kernels
- full schema design for every future module type

Those are downstream concerns once the kernel/module artifact pipeline exists.

## Summary

The optimized direction for Exousia is:

- **custom kernels** via explicit kernel profiles and installable artifacts
- **custom modules** via OCI-hosted RPM artifacts
- **boot integration** via declarative post-install metadata
- **OpenZFS** as the first implementation of that general model

That path is more reusable, more reproducible, and more maintainable than
continuing with a ZFS-specific DKMS-first design.

---

## Implementation Plan (Agent-Assignable Tasks)

This section breaks the phases above into concrete, parallelizable work items
for Claude, Gemini, and Codex. Each task is self-contained with clear inputs,
outputs, and acceptance criteria. Tasks within the same phase can run in
parallel unless noted otherwise.

### Coordination

- **Canonical plan**: this file (`docs/zfs-implementation-plan.md`)
- **Agent assignments**: `AGENTS.md` at repo root
- **No duplicate work**: each task has exactly one owner
- **PR convention**: branch from `uryu/working-dev`, prefix branch name with
  agent (e.g., `claude/kernel-profile-schema`)

---

### Phase 1 -- Kernel Profile Schema and Loader

> Goal: make kernel selection a first-class, typed input to the build system.

#### Task 1.1: Define `KernelProfile` bundle schema

**Owner**: Codex
**Status**: in-progress
**Input**: existing `PackageOverrideBundle` schema in `rpm-overrides.yml`,
kernel override shape from "Recommended Spec Extensions" above
**Output**: `overlays/base/packages/kernels/` directory with:

- `kernel-profile.schema.yml` -- typed YAML schema for `KernelProfile` kind
- `fedora-default.yml` -- profile for Fedora stock kernel (no-op, baseline)
- `cachyos.yml` -- profile for CachyOS COPR kernel

Schema must define:

```yaml
apiVersion: exousia.packages/v1alpha1
kind: KernelProfile
metadata:
  name: <string>
  description: <string>
spec:
  source: repo | copr | oci-artifact
  copr: <optional copr repo string>
  image: <optional OCI image for artifact-based kernels>
  packages:          # kernel RPMs to install/replace
    - kernel
    - kernel-core
    - kernel-modules
    - kernel-modules-core
    - kernel-modules-extra
  devel_packages:    # companion devel/headers
    - kernel-devel
    - kernel-headers
  replaces: [...]    # packages removed before install (--allowerasing equivalent)
  version_pin: <optional version constraint, e.g. "= 6.7.0" or ">= 6.14">
```

The schema must support selecting any kernel version or family. Examples:

- `fedora-default.yml` -- stock Fedora kernel (no-op baseline)
- `cachyos.yml` -- CachyOS BORE scheduler kernel via COPR
- `mainline.yml` -- vanilla mainline from kernel-vanilla COPR
- `pinned-6.7.yml` -- specific kernel version via `version_pin: "= 6.7.0"`
- `custom-built.yml` -- self-built kernel RPMs hosted as OCI artifact on GHCR

A user should be able to set `kernel_profile: pinned-6.7` in `adnyeus.yml`
and get exactly kernel 6.7.x installed.

**Acceptance criteria**:

- yamllint passes on all files
- schema covers repo, COPR, and OCI artifact sources
- version pinning is supported
- at least three concrete profiles exist (fedora-default, cachyos, mainline)

#### Task 1.2: Add `KernelProfile` support to `PackageLoader`

**Owner**: Claude
**Depends on**: Task 1.1 (schema definition)
**Input**: `KernelProfile` schema, existing `PackageLoader` class
**Output**: changes to `tools/package_loader.py`:

- add `"KernelProfile"` to `SUPPORTED_KINDS`
- add `load_kernel_profile(name: str) -> dict` method
- kernel profiles live in `overlays/base/packages/kernels/`
- loader validates the profile against the expected keys
- returns a dict with `source`, `packages`, `devel_packages`, `replaces`,
  and optional `copr`/`image` fields

**Acceptance criteria**:

- `load_kernel_profile("fedora-default")` returns valid dict
- `load_kernel_profile("cachyos")` returns valid dict with `copr` set
- missing profile raises clear error
- tests added to `tools/test_package_loader.py` (min 3 tests)
- pre-commit passes

#### Task 1.3: Wire kernel profile into blueprint and transpiler

**Owner**: Claude
**Depends on**: Task 1.2
**Input**: `PackageLoader.load_kernel_profile()`, existing transpiler
**Output**: changes to `adnyeus.yml` and `tools/yaml-to-containerfile.py`:

- `adnyeus.yml` gains `kernel_profile: fedora-default` (or `cachyos`) field
  in the `package-loader` module
- transpiler reads `kernel_profile` from module config
- if source is `copr`: emit `RUN dnf copr enable -y <repo>` before package
  install, then `dnf install -y --allowerasing <packages>`
- if source is `oci-artifact`: reuse existing `COPY --from` + `dnf install`
  RPM override flow
- if source is `repo`: no special action (stock kernel from base image)

**Acceptance criteria**:

- `fedora-default` profile produces no extra Containerfile lines
- `cachyos` profile produces `copr enable` + `dnf install --allowerasing`
- generated Containerfile is valid
- existing tests still pass
- at least 2 new transpiler tests

---

### Phase 2 -- Module Artifact Schema and Loader

> Goal: define a reusable model for out-of-tree kernel modules.

#### Task 2.1: Define `ModuleProfile` bundle schema

**Owner**: Gemini
**Input**: module override shape from "Recommended Spec Extensions" above
**Output**: `overlays/base/packages/modules/` directory with:

- `zfs.yml` -- module profile for OpenZFS

Schema:

```yaml
apiVersion: exousia.packages/v1alpha1
kind: ModuleProfile
metadata:
  name: zfs
  description: OpenZFS kernel modules and userspace tools
spec:
  source: oci-artifact | dkms-fallback
  image: ghcr.io/borninthedark/zfs-kmod-rpms:<kernel_version>-zfs-<zfs_version>
  packages:
    - kmod-zfs
    - zfs
  build_deps: [...]  # only used for dkms-fallback path
  boot:
    depmod: true
    dracut_modules:
      - zfs
    modules_load:
      - zfs
    enable_units:
      - zfs.target
      - zfs-import-scan.service
    initramfs_rebuild: true
```

**Acceptance criteria**:

- yamllint passes
- `zfs.yml` is complete with boot integration metadata
- schema supports both `oci-artifact` and `dkms-fallback` sources

#### Task 2.2: Add `ModuleProfile` support to `PackageLoader`

**Owner**: Codex
**Depends on**: Task 2.1
**Input**: `ModuleProfile` schema, existing `PackageLoader`
**Output**: changes to `tools/package_loader.py`:

- add `"ModuleProfile"` to `SUPPORTED_KINDS`
- add `load_module_profiles() -> list[dict]` method
- module profiles live in `overlays/base/packages/modules/`
- returns list of dicts with `source`, `image`, `packages`, `boot` fields

**Acceptance criteria**:

- `load_module_profiles()` returns ZFS profile when file exists
- returns empty list when directory is empty/missing
- tests added (min 3 tests)
- pre-commit passes

#### Task 2.3: Wire module profiles into transpiler

**Owner**: Claude
**Depends on**: Task 2.2
**Input**: `load_module_profiles()`, existing transpiler
**Output**: changes to `tools/yaml-to-containerfile.py`:

- `adnyeus.yml` gains `module_profiles: [zfs]` in the `package-loader` module
  (conditional on `enable_zfs`)
- transpiler reads module profiles via loader
- for `oci-artifact` source: emit `COPY --from` + `dnf install` (reuse
  existing RPM override flow)
- for `dkms-fallback`: emit script calling `build-zfs-kmod`
- emit boot integration steps from `boot` metadata:
  - `depmod -a <kernel_version>` if `depmod: true`
  - write `/etc/modules-load.d/<name>.conf` if `modules_load` set
  - write dracut config if `dracut_modules` set
  - `systemctl enable <unit>` for each `enable_units`
  - dracut rebuild if `initramfs_rebuild: true`

**Acceptance criteria**:

- ZFS module with `oci-artifact` source generates correct Containerfile
- ZFS module with `dkms-fallback` source generates script invocation
- boot integration steps appear in Containerfile
- at least 3 new transpiler tests

---

### Phase 3 -- Resolved Build Plan Extension

> Goal: make kernel and module selections visible in the build plan JSON.

#### Task 3.1: Extend resolved build plan schema

**Owner**: Codex
**Depends on**: Tasks 1.3, 2.3
**Input**: existing `resolved-build-plan.json` output, proposed schema from
"Proposed Contract" section above
**Output**: changes to `tools/yaml-to-containerfile.py`:

- resolved plan JSON gains `kernel` and `modules` top-level keys
- `kernel` contains: `profile`, `source`, `packages`, `artifacts`
- `modules` contains: list of `{name, source, packages, artifacts, boot}`

**Acceptance criteria**:

- `resolved-build-plan.json` includes kernel and module metadata
- existing plan fields unchanged
- tests validate new schema keys

---

### Phase 4 -- ZFS Artifact Build Pipeline

> Goal: produce the first real OCI-hosted kernel module artifact.

#### Task 4.1: Build ZFS module RPMs in toolbox

**Owner**: Claude (manual, with user)
**Input**: target kernel version from active kernel profile
**Output**: ZFS kmod RPMs in `~/rpmbuild/RPMS/x86_64/`

Steps:

1. enter toolbox
2. install kernel-devel for target kernel
3. download ZFS SRPM or use upstream tarball
4. build kmod-zfs RPMs matched to target kernel
5. verify RPMs install cleanly

#### Task 4.2: Publish ZFS RPMs as OCI artifact

**Owner**: Claude (manual, with user)
**Depends on**: Task 4.1
**Output**: `ghcr.io/borninthedark/zfs-kmod-rpms:<tag>` on GHCR

Steps (same pattern as flatpak):

1. stage RPMs into scratch container
2. `podman build` + `podman push`
3. verify public access

#### Task 4.3: Update ZFS module profile with real artifact

**Owner**: Gemini
**Depends on**: Task 4.2
**Input**: actual GHCR image tag from Task 4.2
**Output**: updated `overlays/base/packages/modules/zfs.yml` with real image ref

---

### Phase 5 -- Testing

#### Task 5.1: Unit tests for kernel and module loader

**Owner**: Codex
**Output**: additions to `tools/test_package_loader.py`:

- `test_load_kernel_profile`
- `test_load_kernel_profile_missing`
- `test_load_kernel_profile_copr`
- `test_load_module_profiles`
- `test_load_module_profiles_empty`
- `test_load_module_profiles_boot_metadata`

#### Task 5.2: Transpiler tests for kernel and module Containerfile generation

**Owner**: Claude
**Output**: additions to transpiler test suite:

- test: kernel profile `repo` source produces no extra lines
- test: kernel profile `copr` source produces `copr enable` + `dnf install`
- test: kernel profile `oci-artifact` source produces `COPY --from` + `dnf install`
- test: module profile generates boot integration (depmod, dracut, systemd)
- test: resolved plan JSON contains kernel and module metadata

#### Task 5.3: Update Bats image-content tests

**Owner**: Codex
**Output**: updates to `custom-tests/image_content.bats`:

- test: kernel profile packages are installed
- test: ZFS module exists for installed kernel (existing, verify still works)
- test: dracut config for ZFS exists
- test: ZFS systemd units are enabled
- test: `modules.dep` contains ZFS entries

---

### Phase 6 -- Documentation and Cleanup

#### Task 6.1: Update kernel-options.md

**Owner**: Gemini
**Output**: rewrite `docs/kernel-options.md` to reference kernel profiles
instead of manual COPR/script instructions. Link to this plan.

#### Task 6.2: Update README and generate-readme.py

**Owner**: Claude
**Output**: add kernel profile and module support to:

- Package Workflow table in README
- `generate-readme.py` template

#### Task 6.3: Refactor zfs.yml bundle

**Owner**: Codex
**Output**: update `overlays/base/packages/common/zfs.yml`:

- remove DKMS build deps (moved to `ModuleProfile.build_deps`)
- keep only ZFS userspace packages
- update `kind` if needed
- update description to reference module profile

---

### Agent Assignment Summary

| Agent  | Tasks |
|--------|-------|
| Claude | 1.2, 1.3, 2.3, 4.1, 4.2, 5.2, 6.2 |
| Gemini | 2.1, 4.3, 6.1 |
| Codex  | 1.1, 2.2, 3.1, 5.1, 5.3, 6.3 |

### Dependency Graph

```text
Phase 1:  1.1 (Codex) ──> 1.2 (Claude) ──> 1.3 (Claude)
Phase 2:  2.1 (Gemini) ──> 2.2 (Codex) ──> 2.3 (Claude)
Phase 3:                    1.3 + 2.3 ──> 3.1 (Codex)
Phase 4:  4.1 (Claude) ──> 4.2 (Claude) ──> 4.3 (Gemini)
Phase 5:  5.1 (Codex), 5.2 (Claude), 5.3 (Codex) -- parallel after Phase 3
Phase 6:  6.1 (Gemini), 6.2 (Claude), 6.3 (Codex) -- parallel after Phase 5
```

Phases 1 and 2 can run in parallel (kernel profiles and module profiles are
independent schemas). Phase 3 requires both. Phase 4 requires a real kernel
to target. Phases 5 and 6 are parallel cleanup.
