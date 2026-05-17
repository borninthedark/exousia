# LUKS FIDO2 Unlock with YubiKey

Drive encryption with FIDO2 hardware token authentication on Fedora Atomic/bootc.

## Prerequisites

Image must include:

- `libfido2` package (in `overlays/base/packages/common/base-security.yml`)
- `fido2` dracut module (configured in `adnyeus.yml` build script)

## Enrollment

Enroll each YubiKey separately. Each gets its own LUKS keyslot.
The original passphrase remains as fallback in keyslot 0.

```bash
# Insert first YubiKey
sudo systemd-cryptenroll --fido2-device=auto /dev/nvme0n1p3

# Insert second YubiKey
sudo systemd-cryptenroll --fido2-device=auto /dev/nvme0n1p3
```

Each enrollment prompts for:

1. Existing LUKS passphrase
2. YubiKey FIDO2 PIN (if PIN is set on the key)
3. YubiKey touch

## Verify Enrollment

```bash
sudo cryptsetup luksDump /dev/nvme0n1p3 | grep -A5 "systemd-fido2"
```

Expected output shows Token 0 and Token 1 with `fido2-clientPin-required: true`.

## Kernel Command Line

The FIDO2 options must be in the kernel cmdline (not `/etc/crypttab`)
because the initramfs decrypts the root volume before `/etc/crypttab`
is available.

```bash
sudo rpm-ostree kargs \
  --append='rd.luks.options=<UUID>=fido2-device=auto,fido2-with-client-pin=true,discard'
```

Replace `<UUID>` with the LUKS partition UUID (without the `luks-` prefix).
Find it with: `sudo cryptsetup luksDump /dev/nvme0n1p3 | grep UUID`

This persists across image upgrades (stored in bootloader config).

## crypttab

`/etc/crypttab` should also be updated for consistency (used post-boot):

```text
luks-<UUID> UUID=<UUID> - fido2-device=auto,fido2-with-client-pin=true discard
```

Note: on ostree/bootc, `/etc/crypttab` is in the mutable overlay and survives
reboots but gets overwritten on image upgrades. The kernel cmdline is the
authoritative source for boot-time unlock.

## Boot Flow

```text
BIOS → GRUB → kernel + initramfs
  → systemd-cryptsetup reads rd.luks.options from cmdline
  → Detects FIDO2 token via fido2-device=auto
  → Plymouth prompts: "Enter FIDO2 PIN for /dev/nvme0n1p3"
  → User enters PIN
  → Plymouth prompts: "Please touch your security token"
  → User touches YubiKey
  → LUKS decrypted → root mounted → boot continues
```

If no YubiKey is present or PIN is wrong after 3 attempts, falls back to
passphrase prompt.

## Plymouth Integration

The Plymouth theme must use the `two-step` module (current: `bgrt-better-luks`).
Plymouth receives prompts from `systemd-ask-password-plymouth.service`.

Key requirement: `rd.luks.options` must include `fido2-with-client-pin=true`
in the **kernel cmdline** — without it, systemd-cryptsetup tries to use the
token without a PIN and fails with "PIN of security token incorrect".

## Troubleshooting

### "PIN of security token incorrect" at boot

The FIDO2 options are not reaching the initramfs. Check:

```bash
# Verify kernel args include fido2 options
cat /proc/cmdline | grep fido2

# If missing, add them
sudo rpm-ostree kargs \
  --append='rd.luks.options=<UUID>=fido2-device=auto,fido2-with-client-pin=true,discard'
```

### "PIN is blocked, please remove/reinsert token"

Too many failed PIN attempts (3). Remove and reinsert the YubiKey.
If PIN is permanently blocked, reset it:

```bash
ykman fido reset
```

Warning: this erases all FIDO2 credentials on the key. Re-enroll afterward.

### Plymouth shows no prompt at all

Verify dracut has the fido2 module:

```bash
sudo lsinitrd /boot/ostree/*/initramfs-$(uname -r).img | grep fido2
```

If missing, regenerate initramfs:

```bash
sudo dracut --force /boot/ostree/fedora-*/initramfs-$(uname -r).img $(uname -r)
```

### Removing FIDO2 enrollment

```bash
# Remove all FIDO2 tokens
sudo systemd-cryptenroll --wipe-slot=fido2 /dev/nvme0n1p3

# Remove kernel args
sudo rpm-ostree kargs --delete='rd.luks.options=...'
```

## Image Build Requirements

In `adnyeus.yml`:

```yaml
# dracut fido2 module for LUKS FIDO2 unlock
echo 'add_dracutmodules+=" fido2 "' > /usr/lib/dracut/dracut.conf.d/fido2.conf
```

In `overlays/base/packages/common/base-security.yml`:

```yaml
packages:
  - libfido2
  - pam-u2f
  - pamu2fcfg
```

The kernel cmdline args are per-machine (set via `rpm-ostree kargs` at
install time, not during image build).
