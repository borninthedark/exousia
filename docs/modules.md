# Module Reference

The Exousia build system uses a YAML blueprint (`adnyeus.yml`) that declares
build steps as **modules**. The generator transpiles these modules into
Containerfile instructions (COPY, RUN, LABEL, etc.).

Each module has a `type` field that determines how it is processed.

---

## Module Types

| Type | Purpose |
|------|---------|
| [`files`](#files) | Copy files and directories into the image |
| [`script`](#script) | Run shell commands |
| [`rpm-ostree`](#rpm-ostree) | Install/remove RPMs with repo setup |
| [`package-loader`](#package-loader) | YAML-based package management with bundles |
| [`systemd`](#systemd) | Enable/disable systemd units |
| [`chezmoi`](#chezmoi) | Dotfile management via chezmoi |
| [`git-clone`](#git-clone) | Clone a repo and extract files |
| [`github-install`](#github-install) | Install packages from GitHub repos |
| [`signing`](#signing) | Image signature verification policy |
| [`default-flatpaks`](#default-flatpaks) | First-boot flatpak installation |

---

## Common Fields

All modules support these optional fields:

```yaml
- type: <module-type>
  condition: "enable_plymouth == true"  # skip module if condition is false
```

### Condition Syntax

Conditions evaluate against the build context:

- `enable_plymouth == true`
- `image-type == "fedora-bootc"`
- `window_manager == "sway"`
- `distro == "fedora"`
- Logical operators: `&&`, `||`

---

## `files`

Copies files or directories into the image. Each entry becomes a `COPY` instruction.

```yaml
- type: files
  files:
    - src: overlays/base/configs/
      dst: /etc/
      mode: "0644"
    - src: overlays/sway/scripts/runtime/
      dst: /usr/local/bin/
      mode: "0755"
```

| Field | Required | Default | Description |
|-------|----------|---------|-------------|
| `src` | yes | — | Source path relative to repo root |
| `dst` | yes | — | Destination path in the image |
| `mode` | no | `0644` | File permissions |

Trailing `/` on `src` copies directory contents.

---

## `script`

Runs shell commands as a single `RUN` instruction. Multiple scripts are merged
into one layer to reduce image size.

```yaml
- type: script
  scripts:
    - |
      mkdir -p /etc/pipewire/pipewire.conf.d
      echo "context.properties = {}" > /etc/pipewire/pipewire.conf.d/10-defaults.conf
    - bootc container lint
```

| Field | Required | Description |
|-------|----------|-------------|
| `scripts` | yes | List of shell script strings |

- Single-line scripts become `RUN <command>`.
- Multi-line scripts are merged with `set -e` (single script) or
  `set -euxo pipefail` (multiple scripts).
- Heredocs, compound statements (`if/fi`, `for/done`), and line continuations
  are handled automatically.

---

## `rpm-ostree`

Direct RPM package management with repository setup. Prefer `package-loader`
for most use cases.

```yaml
- type: rpm-ostree
  repos:
    - https://mirrors.rpmfusion.org/free/fedora/rpmfusion-free-release-43.noarch.rpm
  config-manager:
    - fedora-cisco-openh264
  install:
    - vim
    - htop
  remove:
    - firefox
  install-conditional:
    - condition: "image-type == fedora-bootc"
      packages:
        - greetd
```

| Field | Required | Description |
|-------|----------|-------------|
| `repos` | no | RPM URLs to install (enables third-party repos) |
| `config-manager` | no | Repos to enable via `dnf config-manager` |
| `install` | no | Packages to install |
| `remove` | no | Packages to remove |
| `install-conditional` | no | Packages installed only when condition matches |

---

## `package-loader`

YAML-based package management using the package-set model under
`overlays/base/packages/`. Resolves bundles, groups, and per-WM/DE selections
into a single dnf transaction.

```yaml
- type: package-loader
  window_manager: sway
  common_bundles:
    - base-core
    - base-media
    - base-devtools
  feature_bundles:
    - audio-production
```

| Field | Required | Description |
|-------|----------|-------------|
| `window_manager` | no | WM selection (loads from `window-managers/<name>.yml`) |
| `desktop_environment` | no | DE selection (loads from `desktop-environments/<name>.yml`) |
| `common_bundles` | no | List of common bundle names to include |
| `feature_bundles` | no | List of feature bundle names to include |
| `include_common` | no | Include all common packages (default: true when no `common_bundles`) |
| `extras` | no | Additional package names (legacy, use `feature_bundles` instead) |

See [package-loader-cli.md](package-loader-cli.md) for inspection commands.

---

## `systemd`

Enables or disables systemd units.

```yaml
- type: systemd
  system:
    enabled:
      - libvirtd.service
      - seatd.service
      - greetd.service
  user:
    enabled:
      - update-user-flatpaks.timer
  default-target: graphical.target
```

| Field | Required | Description |
|-------|----------|-------------|
| `system.enabled` | no | System units to enable |
| `user.enabled` | no | User units to enable globally (`--global`) |
| `default-target` | no | Default systemd target |

---

## `chezmoi`

Configures chezmoi dotfile management with systemd timers for automatic updates.

```yaml
- type: chezmoi
  repository: "https://github.com/user/dotfiles"
  all-users: true
  file-conflict-policy: skip
  run-every: "1d"
  wait-after-boot: "5m"
```

| Field | Required | Default | Description |
|-------|----------|---------|-------------|
| `repository` | yes* | — | Git URL for dotfiles (*required unless `disable-init: true`) |
| `branch` | no | — | Branch to checkout |
| `all-users` | no | `true` | Enable for all users via `--global` |
| `file-conflict-policy` | no | `skip` | `skip` or `replace` |
| `run-every` | no | `1d` | Timer interval for updates |
| `wait-after-boot` | no | `5m` | Delay before first update |
| `disable-init` | no | `false` | Skip initial chezmoi init |
| `disable-update` | no | `false` | Skip update timer |

See [chezmoi-integration.md](chezmoi-integration.md) for details.

---

## `git-clone`

Clones a git repository and extracts specific files into the image.

```yaml
- type: git-clone
  repos:
    - url: https://github.com/user/repo
      branch: main
      files:
        - src: scripts/tool.sh
          dst: /usr/local/bin/tool
          mode: "0755"
```

| Field | Required | Description |
|-------|----------|-------------|
| `repos[].url` | yes | Repository URL |
| `repos[].branch` | no | Branch to clone |
| `repos[].files` | yes | Files to extract |
| `repos[].files[].src` | yes | Path within the repo |
| `repos[].files[].dst` | yes | Destination in the image |
| `repos[].files[].mode` | no | Permissions (default: `0644`) |

Repos are cloned with `--depth 1` and removed after extraction.

---

## `github-install`

Installs packages directly from GitHub repositories. Supports Python packages,
standalone scripts, and make-based projects. Designed for tools that aren't
available as RPMs.

```yaml
- type: github-install
  repos:
    - url: https://github.com/nwg-piotr/autotiling
      name: autotiling
      type: python
      module: autotiling
      bin: autotiling
      entry-point: "from autotiling.main import main\\nmain()"
```

### Install Types

**`python`** (default) — Copies the Python module to site-packages and creates
an entry-point script:

| Field | Required | Default | Description |
|-------|----------|---------|-------------|
| `url` | yes | — | Repository URL |
| `name` | no | `github-pkg-N` | Package name |
| `branch` | no | — | Branch to clone |
| `module` | no | name with `-` → `_` | Python module directory name |
| `bin` | no | name | Binary name in `/usr/local/bin/` |
| `entry-point` | no | `from <module>.main import main\nmain()` | Python entry point code |

**`script`** — Installs a single script:

```yaml
- url: https://github.com/user/tool
  type: script
  bin: my-tool
  src: bin/tool.sh          # path in repo
  dst: /usr/local/bin/tool  # destination (optional)
```

**`make`** — Runs `make install`:

```yaml
- url: https://github.com/user/project
  type: make
  prefix: /usr/local
```

---

## `signing`

Configures container image signature verification using cosign/sigstore.

```yaml
- type: signing
  cosign-key: keys/cosign.pub        # optional
  policy-file: policy/custom.json    # optional
  verification: enforce              # or "warn"
```

| Field | Required | Default | Description |
|-------|----------|---------|-------------|
| `cosign-key` | no | — | Path to cosign public key |
| `policy-file` | no | — | Custom policy JSON to COPY into image |
| `verification` | no | `enforce` | `enforce` (reject unsigned) or `warn` (accept all) |

When `verification: enforce`, the generated policy rejects all images except
those signed with the configured key from `ghcr.io/borninthedark`.

---

## `default-flatpaks`

Generates flatpak install lists for first-boot installation via systemd.

```yaml
- type: default-flatpaks
  configurations:
    - scope: system
      install:
        - org.mozilla.firefox
        - org.gnome.Calculator
    - scope: user
      install:
        - com.spotify.Client
```

| Field | Required | Description |
|-------|----------|-------------|
| `configurations` | yes | List of scope/install pairs |
| `configurations[].scope` | no | `system` or `user` (default: `system`) |
| `configurations[].install` | yes | List of flatpak app IDs |

Install lists are written to `/usr/share/exousia/flatpaks/<scope>-install.list`.

---

## `from-file` Directive

Any module entry can use `from-file` to load its definition from an external
YAML file. Inline fields override the loaded file.

```yaml
- from-file: overlays/base/packages/common/flatpaks.yml
```

The referenced file should contain a valid module definition (with a `type` field).

---

## Module Ordering

Modules execute in declaration order. The recommended phase structure:

1. **Early filesystem bootstrap** — `files` modules for configs, scripts, session assets
2. **System user initialization** — `script` for `systemd-sysusers`
3. **Package installation** — `package-loader` or `rpm-ostree`
4. **Post-package configuration** — `script` for runtime setup
5. **Application installation** — `github-install`, `chezmoi`
6. **Systemd configuration** — `systemd` for service enablement
7. **Final cleanup** — `script` for bootc lint, var cleanup, composefs

---

## Related Docs

- [package-loader-cli.md](package-loader-cli.md) — Inspect resolved package sets
- [overlay-system.md](overlay-system.md) — How overlay files map into images
- [chezmoi-integration.md](chezmoi-integration.md) — Chezmoi module details
