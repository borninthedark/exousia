# Sway Session Validation and greetd/tuigreet Integration

This note documents the resilient Sway session staging fix that satisfies the BATS image-content check and the recommended greetd + tuigreet login flow.

## ensure-sway-session helper

`overlays/sway/scripts/setup/ensure-sway-session` stages or verifies the Sway desktop entry, launcher, and environment file without relying on inline YAML scripts. Key behaviors:

- Prefers the Exousia-provided assets in `/etc/sway` and falls back to upstream defaults when needed.
- Generates a minimal `/etc/sway/environment` when it is not already present, ensuring the Wayland session check passes.
- Supports a `verify` mode to assert that required artifacts exist after package installation.

### Usage

```bash
# Stage (default behavior)
/usr/local/bin/ensure-sway-session

# Verify only (no changes)
/usr/local/bin/ensure-sway-session verify
```

## greetd + tuigreet

1. Install greetd and the `tuigreet` greeter package.
2. Create `/etc/greetd/config.toml` with a sway session, for example:

   ```toml
   [terminal]
   vt = 1

   [default_session]
   command = "/usr/bin/tuigreet --time --remember --cmd /usr/bin/start-sway"
   user = "greeter"
   ```

3. Ensure `greetd.service` is enabled (bootc definitions already enable it for Sway builds).
4. Keep `start-sway` executable and in sync with your session defaults; the helper above guarantees it is staged.
5. Test locally by switching to VT1 and invoking `systemctl start greetd.service`.

For more background on greetd configuration, see the [Arch Wiki entry on greetd](https://wiki.archlinux.org/title/Greetd).
