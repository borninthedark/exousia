# AGENTS.md -- Agent Coordination

This file coordinates work across Claude, Gemini, Codex, and Qwen3.

## Reporting Structure

- **User**: borninthedark (final authority)
- **Claude, Gemini, Codex, Qwen3**: peers -- any agent picks up the next available task

## Agents

| Agent | Provider | Access |
|-------|----------|--------|
| Claude | Anthropic (cloud) | Claude Code CLI |
| Gemini | Google (cloud) | Gemini CLI |
| Codex | OpenAI (cloud) | Codex CLI |
| Qwen3 | Ollama (local) | `ollama.container` quadlet on `127.0.0.1:11434`, model `qwen3:8b` |

## PRIORITY: Multi-Distro OCI Support & Bleach Naming Overhaul

**Status: ACTIVE — all agents prioritize this over other work.**

Branch: `uryu/multi-distro`
Plan: [`docs/plan-multi-distro.md`](docs/plan-multi-distro.md)

### Summary

Support any valid OCI base image. Rename all pipeline YAML files after Bleach
characters from all five factions (Shinigami, Hollows/Arrancar, Quincy, Bounts,
Fullbringers). Add Debian and openSUSE as first non-Fedora targets using the
[bootcrew/mono](https://github.com/bootcrew/mono) pattern as reference.

### Bleach Naming Scheme

| New File | Character | Faction | Role |
|----------|-----------|---------|------|
| `yamamoto.yml` | Yamamoto Genryusai | Shinigami (Squad 1) | Orchestrator |
| `unohana.yml` | Unohana Retsu | Shinigami (Squad 4) | CI: lint + test |
| `soifon.yml` | Soifon | Shinigami (Squad 2) | Security scanning |
| `kenpachi.yml` | Zaraki Kenpachi | Shinigami (Squad 11) | Build & Push |
| `byakuya.yml` | Byakuya Kuchiki | Shinigami (Squad 6) | Sign & Release |
| `ulquiorra.yml` | Ulquiorra Cifer | Arrancar (Espada 4) | Sealed Boot |
| `szayel.yml` | Szayelaporro Granz | Arrancar (Espada 8) | CodeQL |
| `tsukishima.yml` | Tsukishima Shukuro | Fullbringer | Dotfiles Watcher |
| `yukio.yml` | Yukio Hans Vorarlberna | Fullbringer | Post-CI Status |
| `kariya.yml` | Jin Kariya | Bount | Compliance (OSCAP) |
| `haschwalth.yml` | Jugram Haschwalth | Quincy (Sternritter B) | Gate / Summary |

### Multi-Distro Task Board

| Task | Owner | Status | Description |
|------|-------|--------|-------------|
| M.0  | Claude | in-progress | Create plan, branch, coordinate agents |
| M.1  | --    | pending | Rename all workflow YAML files (old → new names), update all `uses:` / `workflow_run` refs |
| M.2  | --    | pending | Update `.github/workflows/README.md` — new naming table, pipeline diagram, faction lore |
| M.3  | --    | pending | Wire `DistroConfig` into generator — replace hardcoded `dnf` calls in `processors.py` |
| M.4  | --    | pending | Add distro config registry (`DISTRO_CONFIGS` dict) with Fedora, Debian, openSUSE entries |
| M.5  | --    | pending | Add `distro` section to blueprint schema (`adnyeus.yml`) |
| M.6  | --    | blocked | Add bootc-from-source build stage to generator for non-Fedora distros (needs M.3, M.4) |
| M.7  | --    | blocked | Add Debian blueprint + package mappings in `yaml-definitions/distros/debian.yml` (needs M.4) |
| M.8  | --    | blocked | Add openSUSE blueprint + package mappings in `yaml-definitions/distros/opensuse.yml` (needs M.4) |
| M.9  | --    | blocked | Add `distro` matrix dimension to orchestrator workflow (needs M.1, M.5) |
| M.10 | --    | blocked | Add `bootc container lint` as final build validation step (needs M.6) |
| M.11 | --    | blocked | Tests: DistroConfig wiring, multi-distro Containerfile generation (needs M.3, M.4) |
| M.12 | --    | blocked | Docs: multi-distro architecture, per-distro setup guide (needs M.7, M.8) |

### Multi-Distro Dependency Graph

```text
M.0 ──> M.1 ──> M.2
          └──> M.9 (needs M.5)

M.3 ──> M.4 ──> M.5
  │       │
  │       ├──> M.6 ──> M.10
  │       ├──> M.7
  │       └──> M.8
  └──> M.11

M.7 + M.8 ──> M.12
```

M.1/M.2 (rename) and M.3/M.4 (abstraction) are independent tracks that can
run in parallel. M.1 is pure file renames — safe for any agent. M.3/M.4
require deep generator knowledge.

### Recommended Agent Assignments

- **Claude**: M.3, M.4, M.6, M.11 (generator internals — requires deep context)
- **Gemini**: M.1, M.2, M.9 (workflow renames + orchestrator matrix — YAML-heavy)
- **Codex**: M.5, M.7, M.8, M.10, M.12 (blueprints, package mappings, docs)

These are suggestions — any agent can claim any unblocked task per the rules.

### Temporal Agent Orchestration Task Board

Plan: [`docs/plan-temporal-orchestration.md`](docs/plan-temporal-orchestration.md)

| Task | Owner | Status | Description |
|------|-------|--------|-------------|
| T.0  | Claude | done | Deploy Temporal quadlets (server, db, ui) and update all docs |
| T.1  | --    | pending | Python worker skeleton under `tools/temporal/` with Temporal SDK |
| T.2  | --    | pending | Qwen3 activity — Ollama HTTP API wrapper with retry policy |
| T.3  | --    | pending | Claude activity — CLI subprocess wrapper with timeout |
| T.4  | --    | pending | Gemini and Codex activities — CLI subprocess wrappers |
| T.5  | --    | pending | Forgejo activity — REST API wrapper (PR, comment, review) |
| T.6  | --    | pending | Plane activity — REST API wrapper (task status, issue create) |
| T.7  | --    | blocked | Code Review workflow — Qwen3 triage + Claude deep review (needs T.2, T.3, T.5) |
| T.8  | --    | blocked | Task Execution workflow — Plane task to agent routing (needs T.2-T.6) |
| T.9  | --    | blocked | Forgejo webhook receiver — FastAPI service for PR/push events (needs T.7) |
| T.10 | --    | blocked | Scheduled codebase scan workflow — stale TODOs, dead code (needs T.7, T.8) |

### Key Technical Decisions

- `DistroConfig` already exists in `tools/generator/context.py` — wire it, don't reinvent
- `processors.py` hardcodes `dnf` ~30 times — all must route through `DistroConfig`
- Non-Fedora distros compile bootc from source (Rust/cargo) as a multi-stage build
- Per-distro package maps translate abstract names to native packages
- `bootc container lint` validates every generated image
- All distros use systemd-boot (no GRUB)

---

## Completed Priorities

### Sealed Boot Implementation (DONE)

Branch: `uryu/sealed-bootc` (merged)

| Task | Owner | Status | Description |
|------|-------|--------|-------------|
| S.0  | Claude | done | Coordinate LLM team — update AGENTS.md, assign phases |
| S.1  | Claude | done | Add supporting Containerfiles: `sbctl`, `systemd-boot`, `tools`, `uki-addon` |
| S.2  | Claude | done | Integrate signed systemd-boot into image build (needs S.1) |
| S.3  | Claude | done | composefs + chunkah rechunking + UKI generation (needs S.2) |
| S.4  | Claude | done | CI integration — GHA secrets for SB keys, workflow changes (needs S.3) |
| S.5  | Claude | done | QCOW2 disk image generation + libvirt testing (needs S.4) |
| S.6  | Claude | done | Documentation — sealed boot architecture, key mgmt, usage (needs S.3) |

### Operational Tasks (DONE)

| Task | Owner | Status | Description |
|------|-------|--------|-------------|
| O.1  | Codex  | done   | Extend `pam_u2f` from `sudo` to `login`, with docs and Bats coverage updates |
| O.2  | Codex  | done   | Standardize shared `pam_u2f` authfile at `/etc/Yubico/u2f_keys` |
| O.3  | Claude | done   | Flatpak auto-update systemd timers (system + user scope) |
| O.4  | Claude | done   | Parameterize Fedora version — `adnyeus.yml` `image-version` as single source of truth |
| O.5  | Codex  | done   | Add a Plane Podman Quadlet stack |
| O.6  | Codex  | done   | Add advanced CodeQL setup with repo-local config |
| O.7  | Codex  | done   | Add Trivy artifact/SBOM reporting docs |
| O.8  | Gemini | done   | Remediate CVE-2026-33186, CVE-2020-10696, CVE-2026-33747 and CodeQL #16 |
| O.9  | Gemini | done   | Integrate OpenSCAP (Hiyori) and OSV-Scanner (Uhin) workflows |
| O.10 | Codex  | done   | Refine security documentation |

---

## Active Plan (deprioritized)

**Custom Kernel Builds, Version Selection & Module Artifact Pipeline**

The goal is to support arbitrary kernel versions and sources (Fedora stable,
CachyOS, mainline, linux-next, custom-built, or a specific version like 6.7)
as a declarative build input. Out-of-tree kernel modules (ZFS, NVIDIA, etc.)
are a secondary consumer of that kernel selection.

Kernel profiles and build tooling live in [Akon](https://github.com/borninthedark/akon).
Exousia consumes built artifacts via `COPY --from` during image assembly.

### Current Integration Gaps

1. Exousia still consumes a static `KernelConfig` file instead of resolving
   first-class `KernelProfile` and `ModuleProfile` documents by name.
2. `kernel_profile` is accepted by workflow inputs, but the transpiler package
   path still reads `overlays/base/packages/common/kernel-config.yml` as the
   source of truth.
3. The current `repository_dispatch` payload mapping is lossy.
4. The resolved build plan does not yet emit top-level `kernel` and `modules` metadata.
5. Exousia only models `default` / `copr` / `oci` kernel sources today.

### Phase 1 -- Kernel Profile Schema & Loader

| Task | Owner | Status  | Description |
|------|-------|---------|-------------|
| 1.1  | Codex | done | Define `KernelProfile` YAML schema + profiles |
| 1.2  | Gemini| done    | Add `KernelProfile` support to `PackageLoader` (needs 1.1) |
| 1.3  | Gemini| in-progress | Wire kernel profile into blueprint + transpiler (needs 1.2) |

### Phase 2 -- Module Artifact Schema & Loader

| Task | Owner | Status  | Description |
|------|-------|---------|-------------|
| 2.1  | --    | pending | Define `ModuleProfile` YAML schema + ZFS profile |
| 2.2  | --    | blocked | Add `ModuleProfile` support to `PackageLoader` (needs 2.1) |
| 2.3  | --    | blocked | Wire module profiles into transpiler (needs 2.2) |

### Phase 3 -- Resolved Build Plan

| Task | Owner | Status  | Description |
|------|-------|---------|-------------|
| 3.1  | --    | blocked | Extend resolved plan JSON with kernel/module metadata (needs 1.3, 2.3) |

### Phase 4 -- ZFS Artifact Build

| Task | Owner | Status  | Description |
|------|-------|---------|-------------|
| 4.1  | --    | blocked | Build ZFS kmod RPMs in toolbox (needs kernel profile) |
| 4.2  | --    | blocked | Publish ZFS RPMs as OCI artifact on GHCR (needs 4.1) |
| 4.3  | --    | blocked | Update ZFS module profile with real artifact ref (needs 4.2) |

### Phase 5 -- Testing

| Task | Owner | Status  | Description |
|------|-------|---------|-------------|
| 5.1  | --    | blocked | Unit tests for kernel + module loader (needs Phase 2) |
| 5.2  | --    | blocked | Transpiler tests for kernel/module Containerfile gen (needs Phase 3) |
| 5.3  | --    | blocked | Update Bats image-content tests (needs Phase 3) |

### Phase 6 -- Documentation & Cleanup

| Task | Owner | Status  | Description |
|------|-------|---------|-------------|
| 6.1  | --    | blocked | Create kernel-options.md when profiles are implemented (needs Phase 3) |
| 6.2  | Gemini| done    | Update README and generator |
| 6.3  | --    | blocked | Refactor zfs.yml bundle (needs Phase 2) |

### Kernel Dependency Graph

```text
Phase 1:  1.1 ──> 1.2 ──> 1.3 ─┐
                                 ├──> 3.1 ──> 5.1, 5.2, 5.3 ──> 6.1, 6.2, 6.3
Phase 2:  2.1 ──> 2.2 ──> 2.3 ─┘
Phase 4:  (kernel profile) ──> 4.1 ──> 4.2 ──> 4.3
```

---

## Rules

1. **Fully TDD & Shift-Left**: Implementation NEVER starts before tests. Write failing tests first to define the contract, then implement. All quality and security gates (linting, safety, coverage) must pass locally.
2. **Claim before starting** -- set owner and status to `in-progress`.
3. **One owner per task** -- no duplicate work.
4. **Branch convention**: `<agent>/task-<N.N>-<short-desc>` from `uryu/multi-distro`. Note: some work may remain in isolated branches during multi-phase transitions.
5. **Pre-commit required**: `uv run pre-commit run --all-files` must pass.
6. **Tests required**: every code change needs tests. Coverage floor: 95%.
7. **No docker**: always podman. No sudo for containers.
8. **Secrets**: never hardcode. Use direnv or session exports.
9. **Mark done**: update status to `done` when complete.
10. **No inline echoes or heredocs**: Static config must use overlay files + COPY. Dynamic cases handled separately.
11. **Forgejo-only git workflow**: Push to the `forgejo` remote (`http://localhost:3000`) ONLY. Never push directly to `origin` (GitHub). The Forgejo CI gate (Pernida) handles promotion to GitHub and Codeberg automatically on pipeline success.

## Key Files

| File | Purpose |
|------|---------|
| `adnyeus.yml` | Build blueprint (single source of truth for version, packages, overlays) |
| `tools/generator/` | YAML-to-Containerfile transpiler package (`uv run python -m generator`) |
| `tools/generator/context.py` | `BuildContext` + `DistroConfig` dataclasses |
| `tools/generator/processors.py` | Module processors (hardcodes `dnf` — refactor target) |
| `tools/generator/constants.py` | `FEDORA_ATOMIC_VARIANTS` (expand for multi-distro) |
| `tools/resolve_build_config.py` | Build config resolver (reads blueprint version) |
| `tools/package_loader/` | Package set loader package (`uv run python -m package_loader`) |
| `tools/konso_check.py` | Dead code detector (pre-commit hook) |
| `tools/dry_check.py` | DRY violation detector (pre-commit hook) |
| `tools/check_utils.py` | Shared utilities for check tools |
| `tools/test_generator_processors.py` | Generator processor tests |
| `tools/test_generator_cli.py` | CLI unit tests |
| `tests/` | Bats integration tests for built images |
| `docs/plan-multi-distro.md` | Multi-distro + Bleach naming plan |
| `docs/modules.md` | Module reference (all module types and usage) |
| `.github/workflows/README.md` | Pipeline docs (to be rewritten with new naming) |
