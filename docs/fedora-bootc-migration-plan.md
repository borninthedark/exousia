# Fedora bootc Base Migration Plan

## Goal

Move Exousia from a `quay.io/fedora/fedora-sway-atomic` base image to a pure
`quay.io/fedora/fedora-bootc` base while preserving the current desktop,
login, audio, portal, and quality-of-life behavior.

The move should only happen after a package and service audit proves that every
capability currently inherited from `fedora-sway-atomic` is either:

- explicitly layered by Exousia, or
- intentionally dropped with a documented reason.

## Why this move

- reduce hidden desktop behavior inherited from the Sway atomic image
- make Exousia’s desktop stack fully declared in the blueprint and package sets
- simplify future custom-kernel and module work by reducing assumptions in the
  base image
- make regressions easier to diagnose because fewer desktop components are
  provided implicitly

## Current Risk

`fedora-sway-atomic` likely provides packages, system defaults, and desktop
integration that Exousia currently benefits from without declaring them all in
package sets or overlay logic.

Switching the base image before auditing those inherited pieces would likely
break some combination of:

- Sway session startup
- greetd or tuigreet login flow
- XDG desktop portals
- Waybar and desktop utilities
- audio/session helpers
- seat and input permissions
- Flatpak desktop integration

## Required Audit

The migration starts with a package and behavior audit between:

- current base: `quay.io/fedora/fedora-sway-atomic:<version>`
- target base: `quay.io/fedora/fedora-bootc:<version>`

### Audit outputs

Create an explicit inventory of:

1. packages present in `fedora-sway-atomic` but not in `fedora-bootc`
2. systemd units enabled by default in the current base
3. desktop/session files currently inherited from the base
4. portal, audio, seat, polkit, and login integration currently inherited
5. packages already declared by Exousia that overlap with the inherited set
6. packages that should become explicit Exousia dependencies
7. packages or defaults that should be removed instead of reintroducing

### Areas to audit

- compositor/session:
  - `sway`
  - `swaybg`
  - `swayidle`
  - `swaylock`
  - `foot`
  - `waybar`
  - `xorg-x11-server-Xwayland`
- login/session management:
  - `greetd`
  - `tuigreet`
  - `seatd`
  - session desktop entries
- portals and desktop integration:
  - `xdg-desktop-portal`
  - `xdg-desktop-portal-wlr`
  - supporting portal glue
- audio/multimedia:
  - `pipewire`
  - `wireplumber`
  - `pipewire-alsa`
  - `pipewire-pulseaudio`
  - JACK-related packages
- auth/policy/runtime helpers:
  - `polkit`
  - `rtkit`
  - NetworkManager applet and tray helpers
- user experience defaults:
  - fonts
  - terminal defaults
  - notification stack
  - screenshot/clipboard tools

## Proposed Execution Plan

### Phase 1: Capture the current inherited surface

1. build or inspect the current `fedora-sway-atomic`-based image
2. collect:
   - `rpm -qa`
   - enabled systemd units
   - `/usr/share/wayland-sessions`
   - relevant `/usr/lib/systemd` and `/etc` desktop files
3. compare with a minimal `fedora-bootc` image of the same Fedora version

Deliverable:

- an audit table checked into the repo or attached to the migration branch

### Phase 2: Make Exousia explicit

Update Exousia package sets and overlays so the current desktop behavior is
provided by Exousia itself rather than inherited from the base.

Likely files:

- `overlays/base/packages/window-managers/sway.yml`
- `overlays/base/packages/common/*.yml`
- `adnyeus.yml`
- `overlays/sway/configs/`
- `overlays/sway/session/`
- `overlays/sway/scripts/setup/`

Deliverable:

- the current user-visible desktop experience still works while remaining on
  `fedora-sway-atomic`

### Phase 3: Add migration tests before switching the base

Required assertions:

- greetd config exists and `greetd.service` is enabled
- Sway session files exist in the expected system paths
- `/etc/sway/environment` and `/usr/bin/start-sway` exist
- expected desktop packages are installed
- portal packages and services are present
- PipeWire/WirePlumber stack is present
- Flatpak remote and Flatpak helper units still work

Likely test files:

- `tests/image_content.bats`
- `tests/overlay_content.bats`
- `tools/test_yaml_to_containerfile.py`

Deliverable:

- failing tests first, then green after explicit package declaration

### Phase 4: Switch the base image

Only after the audit and tests are in place:

1. change `base-image` in `adnyeus.yml` to `quay.io/fedora/fedora-bootc`
2. regenerate the Containerfile
3. run the full local and CI validation path

Deliverable:

- a `fedora-bootc`-based image with no loss of declared desktop behavior

### Phase 5: Remove no-longer-needed compatibility pieces

After the base switch is stable:

- remove packages that were added during exploration but are not needed
- remove overlay workarounds that only existed for `fedora-sway-atomic`
- update docs so they describe the explicit Exousia desktop stack, not inherited
  Sway atomic behavior

## Recommended order of work

1. package audit
2. explicit package-set updates
3. failing migration tests
4. base-image switch
5. cleanup

## Definition of done

The migration is complete when:

- `adnyeus.yml` uses `quay.io/fedora/fedora-bootc`
- all required desktop/session behavior is explicitly declared by Exousia
- Bats and Python tests pass against the new base
- docs no longer assume `fedora-sway-atomic` inheritance for desktop behavior
