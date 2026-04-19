# Refined Package Management and Container Build Design

This document proposes a stricter package-management model for Exousia and a cleaner container build pipeline that is easier to validate, cache, and evolve.

It is based on the current build entrypoint in [adnyeus.yml](../adnyeus.yml), the package-set definitions in [overlays/base/packages/](../overlays/base/packages/), and the current resolver in [tools/resolve_build_config.py](../tools/resolve_build_config.py).

## Goals

- Make package selection explicit, typed, and testable
- Separate package intent from image-build implementation
- Reduce ad hoc package logic embedded in the blueprint
- Improve build reproducibility across RPM, Flatpak, and Python tooling
- Produce resolved manifests that tests and CI can verify directly
- Support multiple image profiles without duplicating package logic

## Current Pain Points

The current package YAMLs are readable, but they have several structural weaknesses:

- Category names are free-form and drift across files
  `core`, `core_utilities`, `system`, `extra`, `utilities`, and `audio_media` are all machine-visible keys today.
- Feature boundaries are implied instead of formalized
  `audio-production.yml` behaves like a feature bundle, but it is not modeled differently from the shared base bundles.
- Conflict handling is detached from the features that cause it
  [remove.yml](../overlays/base/packages/common/remove.yml) is global, which makes provenance harder to audit.
- Build logic spans multiple package channels without a clear contract
  RPMs, Flatpaks, and `uv pip install --system` all contribute to the final image.
- The main blueprint mixes declarative config and imperative build policy
  [adnyeus.yml](../adnyeus.yml) currently contains package selection, inline scripts, user/session staging, Flatpak setup, and Python-based tool installation.

## Design Principles

1. Package specs should declare intent, not build mechanics.
2. Every selected feature should be traceable to a resolved manifest.
3. Conflicts and removals should be owned by the feature that introduces them.
4. Non-RPM software should not silently bypass the package model.
5. Container builds should be layered so config-only changes do not invalidate package-heavy steps.

## Proposed Model

### 1. Replace free-form package sets with typed feature bundles

The current `common/` and `window-managers/` layout is a reasonable start, but the format should be normalized.

Recommended top-level kinds:

- `base`
- `window-manager`
- `desktop-environment`
- `feature`
- `remove`
- `flatpak`

Recommended directory layout:

```text
overlays/base/packages/
├── base/
│   ├── core.yml
│   ├── devtools.yml
│   ├── security.yml
│   ├── virtualization.yml
│   └── shell.yml
├── features/
│   ├── audio-production.yml
│   ├── zfs.yml
│   └── containers.yml
├── window-managers/
│   └── sway.yml
├── desktop-environments/
│   └── ...
├── removals/
│   └── defaults.yml
└── flatpaks/
    └── defaults.yml
```

This keeps package ownership closer to the domain that introduces it.

### 2. Formal package-spec schema

Every package-definition file should validate against a strict schema.

Example:

```yaml
apiVersion: exousia.packages/v1alpha1
kind: FeatureBundle

metadata:
  name: audio-production
  description: Fedora Jam audio production suite with PipeWire JACK support
  owners:
    - uryu
  platforms:
    os:
      - fedora
    image_types:
      - fedora-bootc
      - fedora-sway-atomic

spec:
  source: rpm
  stage: build
  packages:
    - name: pipewire-jack-audio-connection-kit
      reason: Provide JACK compatibility for DAW workloads
    - name: tuned
    - name: tuned-profiles-realtime

  conflicts:
    packages: []
    features: []

  replaces: []

  requires:
    features:
      - wm-sway
```

### 3. Normalized entry shape

Each package entry should support optional metadata:

- `name`
- `reason`
- `when`
- `arch`
- `stage`
- `source`

This avoids overloading YAML file names or category headings with machine semantics.

### 4. Separate channels explicitly

Treat software installation channels as separate first-class concepts:

- `rpm`
- `flatpak`
- `python`
- `script`

Recommended rule set:

- RPM packages are resolved during image build
- Flatpaks are resolved into a separate boot-time or user-time manifest
- Python tooling is either packaged as RPM, vendorized as a build artifact, or isolated into a dedicated managed tool bundle
- Script-based installs must be declared explicitly and should be the exception

This directly addresses the current `uv pip install --system autotiling` step in [adnyeus.yml](../adnyeus.yml), which is functional but weak for reproducibility and provenance.

## Resolver Design

### Inputs

The resolver should consume:

- selected image type
- Fedora version
- selected window manager and/or desktop environment
- enabled features
- optional build profile

Current inputs already exist in [tools/resolve_build_config.py](../tools/resolve_build_config.py); the next step is to extend the output model.

### Outputs

The resolver should generate canonical build artifacts:

```text
build/
├── resolved-config.yml
├── resolved-packages.json
├── resolved-flatpaks.json
├── resolved-removals.json
└── resolved-build-plan.json
```

Suggested `resolved-build-plan.json` shape:

```json
{
  "image": {
    "name": "exousia",
    "base_image": "quay.io/fedora/fedora-sway-atomic:43",
    "image_type": "fedora-bootc",
    "version": "43"
  },
  "selection": {
    "window_manager": "sway",
    "desktop_environment": null,
    "features": ["audio-production"],
    "profile": "sway-audio"
  },
  "rpm": {
    "remove": ["firefox", "foot", "rofi-wayland"],
    "install": [
      {
        "name": "sway",
        "from": ["wm-sway"]
      },
      {
        "name": "tuned",
        "from": ["feature-audio-production"]
      }
    ]
  },
  "flatpak": {
    "scope": "system",
    "install": ["org.mozilla.firefox//stable"]
  },
  "python": {
    "install": [
      {
        "name": "autotiling",
        "source": "uv",
        "from": ["feature-wm-sway"]
      }
    ]
  }
}
```

### Resolver responsibilities

The resolver should:

- validate schema before merging anything
- reject duplicate bundle names
- reject unknown `kind` values
- detect package conflicts before build generation
- record provenance for every install/remove action
- emit stable ordering for package operations

### Resolver non-goals

The resolver should not:

- perform package installation directly
- execute arbitrary shell logic
- rely on implicit YAML key conventions

## Blueprint and Build Refactor

### Current state

[adnyeus.yml](../adnyeus.yml) is currently both:

- the declarative image blueprint
- a build-policy script host

That makes it hard to reason about what changed when a build breaks.

### Proposed split

Refactor the build into these layers:

1. `resolve`
   Generate resolved config and manifests from bundle selection.
2. `render`
   Generate the final Containerfile or BlueBuild-consumable blueprint.
3. `build`
   Install RPMs, stage overlays, enable services, and produce the OCI image.
4. `verify`
   Assert image contents against resolved manifests.
5. `promote`
   Push or publish only after verification succeeds.

### Inline script reduction

Several inline scripts in [adnyeus.yml](../adnyeus.yml) should move into named setup scripts under `overlays/.../scripts/setup/`.

Examples:

- PipeWire JACK defaults
- tuned profile activation
- Flathub remote setup policy
- Plymouth regeneration policy

This has two benefits:

- easier code review
- more stable build caching because the generated blueprint stops changing on formatting-only edits

## Build Profiles

Introduce explicit profiles so image variants are resolved by composition rather than ad hoc conditionals.

Recommended initial profiles:

- `sway`
- `sway-audio`
- `sway-zfs`
- `sway-audio-zfs`

Example:

```yaml
apiVersion: exousia.build/v1alpha1
kind: BuildProfile

metadata:
  name: sway-audio

spec:
  image_type: fedora-bootc
  window_manager: sway
  features:
    - audio-production
```

Profiles should select bundles. They should not duplicate package lists.

## Conflict and Removal Model

### Problem

The current [remove.yml](../overlays/base/packages/common/remove.yml) is global and does not clearly encode why a package must be removed.

### Proposed approach

Move removals closer to the feature or base bundle that requires them.

Example:

```yaml
spec:
  packages:
    - name: fuzzel
  conflicts:
    packages:
      - rofi
      - rofi-wayland
  replaces:
    - rofi
    - rofi-wayland
```

Then the resolver can generate the final removal list from selected bundles and feature relationships.

This makes package drift easier to detect and reduces stale global removals.

## Python and Non-RPM Tooling

### Problem

`uv pip install --system autotiling` works, but it is outside the package model and is harder to reproduce, audit, and verify.

### Options

Preferred order:

1. Package the tool as an RPM or consume an existing Fedora package
2. Vendor a wheel or pinned artifact into the build with checksum verification
3. Install into an isolated managed path with a manifest entry
4. Keep `--system` installs only as a temporary bridge

### Recommendation

Model Python tools as a separate bundle type:

```yaml
apiVersion: exousia.packages/v1alpha1
kind: PythonToolBundle

metadata:
  name: autotiling

spec:
  installer: uv
  stage: build
  packages:
    - name: autotiling
      version: "==1.9.0"
```

Then the build can treat this as explicit managed state instead of an invisible side effect.

## Flatpak Model

[overlays/base/packages/common/flatpaks.yml](../overlays/base/packages/common/flatpaks.yml) is already separate, which is good. The main improvement is to make Flatpak selection part of the resolved build plan.

Recommended changes:

- split runtime/platform Flatpaks from end-user applications
- record scope explicitly in the resolved manifest
- support profile-specific Flatpak bundles
- validate duplicate refs and conflicting branches

That makes it easier to answer questions like:

- which Flatpaks are expected in a desktop-audio image?
- which are system-wide versus user-scoped?
- which refs are runtime dependencies rather than user apps?

## Testing Strategy

### Schema tests

Add tests for:

- invalid `apiVersion`
- invalid `kind`
- missing `metadata.name`
- missing `spec`
- invalid source/stage combinations

### Semantic resolver tests

Extend or complement [tools/test_resolve_build_config.py](../tools/test_resolve_build_config.py) with tests for:

- duplicate package entries across bundles
- bundle conflict detection
- feature dependency resolution
- resolved install/remove order
- profile selection
- invalid WM/DE combinations

### Image-content tests

The current BATS tests in [custom-tests/image_content.bats](../custom-tests/image_content.bats) should be able to consume or reference the resolved manifest so expectations are derived from declared intent rather than being entirely handwritten.

That creates a stronger contract:

selected bundles -> resolved plan -> built image -> test assertions

## Container Build Pipeline

### Recommended stage model

```text
resolve -> validate -> render -> build -> verify -> promote
```

### Stage details

#### Resolve

- load selected profile and base config
- validate all package specs
- compute resolved RPM install/remove lists
- compute resolved Flatpak and Python tool manifests

#### Validate

- schema validation
- semantic conflict checks
- duplicate detection
- profile compatibility checks

#### Render

- emit `resolved-config.yml`
- emit `resolved-build-plan.json`
- generate final Containerfile

#### Build

- apply RPM removals first
- install RPM package plan
- stage overlays and scripts
- enable services
- register Flatpak policy
- apply managed Python tools

#### Verify

- run image-content tests
- lint bootc container
- compare image contents against resolved manifest

#### Promote

- push only after build and verification succeed

## Migration Plan

### Phase 1: Validation without behavior change

- add schema validation for existing package YAML files
- normalize metadata fields where missing
- keep current file layout and package-loader behavior

Outcome:
early failure for malformed package definitions without breaking the current build model

### Phase 2: Normalize bundle model

- convert current YAMLs to typed bundle schema
- split shared package definitions into smaller base bundles
- remove legacy compatibility paths from the loader once the migration is complete

Outcome:
package ownership becomes clearer and feature selection becomes more explicit

### Phase 3: Emit resolved manifests

- extend [tools/resolve_build_config.py](../tools/resolve_build_config.py)
- produce `build/resolved-*.json` outputs
- teach tests to inspect them

Outcome:
package resolution becomes observable and testable

### Phase 4: Refactor blueprint and build logic

- reduce inline scripts in [adnyeus.yml](../adnyeus.yml)
- move imperative setup into named scripts
- make the blueprint consume resolved manifests

Outcome:
cleaner layering, better cache behavior, clearer reviews

### Phase 5: Eliminate unmanaged installs

- replace or formalize `uv pip install --system` steps
- move Flatpak selection to profile-aware manifests

Outcome:
better reproducibility and provenance

## Immediate Next Steps

Highest-value short-term work:

1. Add a schema validator for package definitions.
2. Extend the resolver to emit a resolved RPM install/remove plan.
3. Keep refining the split base bundles by intent and selection profile.
4. Move `autotiling` into an explicit managed-tool model instead of an inline system pip install.
5. Move package-conflict ownership out of the global [remove.yml](../overlays/base/packages/common/remove.yml) model.

## Summary

The current YAML package specs are serviceable, but they are too loose for long-term image composition and testing. The main improvement is not just better YAML formatting. It is introducing a typed bundle model, generating resolved manifests, and making the build consume those manifests in a staged pipeline.

That would give Exousia:

- clearer package ownership
- fewer hidden build side effects
- better CI validation
- more stable container layering
- easier support for multiple image profiles
