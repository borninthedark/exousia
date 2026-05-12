# Multi-Distro OCI Support & Bleach Naming Overhaul

Branch: `uryu/multi-distro`
Status: **Planning**

## Goals

1. Support any valid OCI base image — not just Fedora
2. Rename all pipeline YAML files after Bleach characters from ALL factions
3. Add Debian bootc support (bootcrew/mono pattern) as first non-Fedora target
4. Add openSUSE bootc support as second target
5. Update all docs and diagrams

## Bleach Character → Pipeline Role Mapping

Characters drawn from **all five factions**: Shinigami, Hollows/Arrancar, Quincy,
Bounts, and Fullbringers. Role assignments are thematic.

| File | Character | Faction | Role | Rationale |
|------|-----------|---------|------|-----------|
| `yamamoto.yml` | Yamamoto Genryusai | Shinigami (Squad 1) | **Orchestrator** | Head Captain — commands all squads |
| `unohana.yml` | Unohana Retsu | Shinigami (Squad 4) | **CI: lint + test** | Healer — ensures codebase health |
| `soifon.yml` | Soifon | Shinigami (Squad 2) | **Security scanning** | Stealth Force commander — infiltration & detection |
| `kenpachi.yml` | Zaraki Kenpachi | Shinigami (Squad 11) | **Build & Push** | Raw power — heavy build work |
| `byakuya.yml` | Byakuya Kuchiki | Shinigami (Squad 6) | **Sign & Release** | Law, order, rules — signing & compliance |
| `ulquiorra.yml` | Ulquiorra Cifer | Arrancar (Espada 4) | **Sealed Boot** | Segunda Etapa (second release) = sealed image |
| `szayel.yml` | Szayelaporro Granz | Arrancar (Espada 8) | **CodeQL** | Scientist Espada — deep code analysis |
| `tsukishima.yml` | Tsukishima Shukuro | Fullbringer | **Dotfiles Watcher** | Book of the End — inserts into history, watches for changes |
| `yukio.yml` | Yukio Hans Vorarlberna | Fullbringer | **Post-CI Status** | Invaders Must Die — digital domain, status tracking |
| `kariya.yml` | Jin Kariya | Bount | **Compliance (OSCAP)** | Bount leader — consumes and validates souls |
| `haschwalth.yml` | Jugram Haschwalth | Quincy (Sternritter B) | **Gate / Summary** | The Balance — weighs pipeline results |

### Name Migration Map (old → new)

| Old File | New File | Notes |
|----------|----------|-------|
| `urahara.yml` | `yamamoto.yml` | Role stays: orchestrator |
| `hikifune.yml` | `unohana.yml` | Role stays: CI |
| `uhin.yml` | `soifon.yml` | Role stays: security |
| `hiyori.yml` | `kenpachi.yml` | Split: build only (sign/release extracted) |
| *(new)* | `byakuya.yml` | Extracted: sign + release from hiyori |
| `ulquiorra.yml` | `ulquiorra.yml` | Role stays: sealed boot |
| `kon.yml` | `szayel.yml` | Role stays: CodeQL |
| `mayuri.yml` | `tsukishima.yml` | Role stays: dotfiles watcher |
| `nemu.yml` | `yukio.yml` | Role stays: post-CI status |
| *(embedded in hiyori)* | `kariya.yml` | Extracted: OSCAP + Trivy compliance |
| *(gate step in urahara)* | `haschwalth.yml` | Extracted: gate/summary as own workflow |

## Multi-Distro Architecture

### Blueprint Schema Changes

Add `distro` top-level key to `adnyeus.yml`:

```yaml
distro:
  family: fedora          # fedora | debian | opensuse
  package-manager: dnf    # dnf | apt | zypper
  bootc-source: native    # native (Fedora ships bootc) | build (compile from source)
```

For Fedora, `bootc-source: native` — bootc is already in the base image.
For Debian/openSUSE, `bootc-source: build` — must compile bootc from source
(following bootcrew/mono `shared/build.sh` pattern).

### Package Manager Abstraction

`DistroConfig` already exists in `tools/generator/context.py` but is unused.
Wire it into the generator:

```python
DISTRO_CONFIGS = {
    "fedora": DistroConfig(
        name="fedora",
        package_manager="dnf",
        install_command="dnf install -y",
        update_command="dnf upgrade -y",
        clean_command="dnf clean all",
        ...
    ),
    "debian": DistroConfig(
        name="debian",
        package_manager="apt",
        install_command="apt-get install -y --no-install-recommends",
        update_command="apt-get update && apt-get upgrade -y",
        clean_command="apt-get clean && rm -rf /var/lib/apt/lists/*",
        ...
    ),
    "opensuse": DistroConfig(
        name="opensuse",
        package_manager="zypper",
        install_command="zypper install -y --no-recommends",
        update_command="zypper update -y",
        clean_command="zypper clean -a",
        ...
    ),
}
```

### Processors Refactor

`processors.py` hardcodes `dnf` ~30 times. Refactor:

1. Pass `DistroConfig` into `ModuleProcessor.__init__`
2. Replace all `dnf install -y` with `self.distro.install_command`
3. Fedora-specific blocks (RPM Fusion, dnf5 upgrade, COPR) → guarded by
   `if self.distro.name == "fedora":`
4. Each distro gets a per-distro package map (`yaml-definitions/packages/`)
   that translates abstract package names to distro-native ones

### bootc-from-Source Stage (Debian + openSUSE)

Non-Fedora distros need a multi-stage build that compiles bootc from source.
Add a `bootc-builder` stage to the generated Containerfile:

```dockerfile
# Stage: bootc builder (Debian/openSUSE only)
FROM rust:latest AS bootc-builder
RUN git clone https://github.com/containers/bootc.git /src/bootc \
    && cd /src/bootc && cargo build --release
```

Then `COPY --from=bootc-builder /src/bootc/target/release/bootc /usr/bin/bootc`
into the final image. This follows the bootcrew/mono `shared/build.sh` pattern.

### Per-Distro Blueprints

```text
yaml-definitions/
  distros/
    fedora.yml        # Fedora-specific packages, repos, base image
    debian.yml        # Debian-specific packages, repos, base image
    opensuse.yml      # openSUSE-specific packages, repos, base image
  packages/
    common.yml        # Abstract package names (mapped per-distro)
    sway.yml          # Desktop packages (mapped per-distro)
```

### Workflow Changes

The orchestrator (`yamamoto.yml`) gains a `distro` matrix dimension:

```yaml
strategy:
  matrix:
    distro: [fedora]             # expand to [fedora, debian, opensuse]
    distro_version: ${{ ... }}
```

Build workflow (`kenpachi.yml`) accepts `distro` + `distro_version` inputs and
delegates to the transpiler which generates the appropriate Containerfile.

## Phased Implementation

### Phase M.0 — Rename + Restructure (no behavior change)

Rename all workflow YAML files. Update all cross-references (`uses:`,
`workflow_run`, docs, diagrams). Pure rename — same pipeline behavior.

### Phase M.1 — Package Manager Abstraction

Wire `DistroConfig` into the generator. Replace hardcoded `dnf` calls with
distro-aware commands. Add distro config registry. All existing Fedora
behavior unchanged — just routed through the abstraction.

### Phase M.2 — Debian Support

- Add `yaml-definitions/distros/debian.yml`
- Add bootc-from-source build stage to generator
- Add Debian package mappings
- Test with `debian:unstable` base (bootcrew/mono reference)
- Wire into workflow matrix

### Phase M.3 — openSUSE Support

- Add `yaml-definitions/distros/opensuse.yml`
- Add openSUSE package mappings
- Test with `opensuse/tumbleweed:latest` base
- Wire into workflow matrix

### Phase M.4 — Docs & Diagrams

- Rewrite `.github/workflows/README.md` with new naming
- Update pipeline flow diagram
- Add multi-distro architecture docs
- Update `docs/modules.md` with distro-aware module docs

## Task Assignments

See AGENTS.md for the task board.

## Reference: bootcrew/mono Pattern

Key takeaways from `bootcrew/mono`:

- Each distro has its own `Containerfile` — ours generates them
- `shared/build.sh` compiles bootc from source with cargo
- `shared/bootc-rootfs.sh` sets up ostree symlinks and composefs prep
- All distros use systemd-boot (no GRUB)
- All end with `bootc container lint` — we should adopt this
