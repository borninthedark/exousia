# Package Loader CLI

Use `uv run python -m package_loader` to inspect the package-set model without
generating a Containerfile. It is the fastest way to answer:

- Which RPMs and package groups does a given WM or DE selection resolve to?
- Which package set introduced a package or removal?
- What does the legacy `packages.add` / `packages.remove` export contain?

## When To Use It

- Validate edits under [`overlays/base/packages/`](../overlays/base/packages/)
- Inspect package-set provenance before building
- Compare explicit common package sets with feature package sets
- Export the legacy package text files used by older workflows

## Common Commands

Print the default resolved package list for a window manager:

```bash
uv run python -m package_loader --wm sway
```

Print the normalized resolved plan as JSON:

```bash
uv run python -m package_loader --wm sway --json
```

Resolve an explicit package-set selection instead of the default common package sets:

```bash
uv run python -m package_loader \
  --wm sway \
  --json \
  --common base-core \
  --common base-shell \
  --feature audio-production
```

Export legacy text manifests:

```bash
uv run python -m package_loader \
  --wm sway \
  --export \
  --output-dir custom-pkgs
```

List available targets:

```bash
uv run python -m package_loader --list-wms
uv run python -m package_loader --list-des
```

## Options

| Option | Meaning |
|--------|---------|
| `--wm NAME` | Resolve packages for a window manager such as `sway` |
| `--de NAME` | Resolve packages for a desktop environment |
| `--json` | Print the normalized resolved package plan |
| `--common NAME` | Include a specific common package set; repeatable |
| `--feature NAME` | Include a specific feature package set; repeatable |
| `--export` | Write legacy `packages.add` and `packages.remove` outputs |
| `--output-dir PATH` | Directory for legacy export output |
| `--list-wms` | List available window-manager package-set files |
| `--list-des` | List available desktop-environment package-set files |

## Output Model

`--json` emits the same normalized package-plan model consumed by
[`uv run python -m generator`](../tools/generator/) when it
writes `--resolved-package-plan`.

Important sections:

- `selection`: requested WM/DE and package-set choices
- `bundles`: normalized internal records with source files and declared conflicts
- `rpm.install`: RPM install list with provenance
- `rpm.remove`: RPM removals with provenance
- `rpm.groups`: DNF group installs and removals with provenance

## Selection Rules

- If you do not pass `--common`, the loader includes the default
  `base-*` common package sets.
- `--feature` adds optional feature package sets such as `audio-production`
  or `zfs`.
- `base` is not a valid explicit package-set name. Use concrete names such as
  `base-core` or `base-shell`.
- Do not mix implicit extras and explicit feature package-set selection in custom
  code paths; the resolver treats those as mutually exclusive APIs.

## Related Docs

- [Overlay System](overlay-system.md)
- [Package Management Design](package-management-and-container-builds.md)
- [Build Tools](../tools/README.md)
- [Main README](../README.md)
