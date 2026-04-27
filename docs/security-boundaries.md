# Security Boundaries

This document describes the security-relevant trust boundaries that currently
exist in Exousia as implemented in the local tooling and CI workflows.

## Scope

Exousia is currently a repository-local build system plus GitHub Actions
automation. It does **not** ship an API service, webhook receiver, or remote
router layer in this repo. Security guidance here is limited to the actual
implemented surfaces:

- local blueprint selection
- local path resolution
- generated Containerfile assembly
- CI workflow inputs and registry access

## Blueprint Selection

The build flow resolves configuration from a small trusted set of paths:

- root blueprint: `adnyeus.yml`
- curated variants under `yaml-definitions/`

`tools/resolve_build_config.py` resolves `yaml_config=auto` to the canonical
blueprint first and does not treat arbitrary caller-supplied paths as trusted.

## Local Path Resolution

The relevant local selector logic lives in:

- [tools/yaml_selector_service.py](../tools/yaml_selector_service.py)
- [tools/resolve_build_config.py](../tools/resolve_build_config.py)

The intended boundary is:

- build inputs should resolve inside the repository
- trusted definitions come from the root blueprint or curated YAML definitions
- generated outputs are written to explicit build/output paths

When changing these tools, preserve the constraint that repository-local build
selection must not become arbitrary filesystem traversal.

## Generated Image Boundary

The generator consumes:

- YAML blueprint modules
- overlay files under `overlays/`
- package definitions under `overlays/base/packages/`

It emits a deterministic Containerfile rather than executing arbitrary templated
Python from the blueprint. Security-sensitive build behaviors should therefore
remain explicit in module processors and overlay files.

## CI and Registry Boundary

GitHub Actions workflows split trust by stage:

- `Hikifune`: Python lint/test
- `Uhin`: static and source/security scanning
- `Hiyori`: image build, Trivy image scan, SBOM submission, OpenSCAP, signing
- `Kon`: CodeQL

Secrets are intentionally narrow. Today the main sensitive input is:

- `GHCR_PAT` for authenticated GHCR access where required

Forked pull requests do not receive repository secrets, so the build/release
path is intentionally skipped there.

## Regression Expectations

Security regressions in these areas should be covered by tests where practical:

- config resolution chooses trusted blueprint paths
- generator output remains explicit and reviewable
- CI documentation matches the actual workflow behavior
- secret-dependent paths remain excluded from forked PR execution
