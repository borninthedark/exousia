# Sealed Boot

Exousia supports sealed bootable container images with a fully measured
boot chain. When enabled, every component from the bootloader to the
root filesystem is cryptographically verified.

## Boot Chain

```text
UEFI firmware (Secure Boot)
  -> systemd-boot (signed with db key)
    -> UKI (signed + TPM-measured)
      -> initrd (composefs backend)
        -> root filesystem (composefs integrity)
```

Each stage verifies the next. A tampered binary at any level breaks the chain
and the system refuses to boot.

## Architecture

The sealed build wraps an existing Exousia image with additional stages:

| Stage | Containerfile | Output |
|-------|--------------|--------|
| Key generation | `Containerfile.sbctl` | PK, KEK, db key hierarchy |
| Bootloader signing | `Containerfile.systemd-boot` | Signed `systemd-bootx64.efi` |
| Build tools | `Containerfile.tools` | Container with ukify + sbsigntools |
| UKI addons | `Containerfile.uki-addon` | Signed kernel cmdline addons |
| Sealed image | `Containerfile` | Final image with signed boot + composefs + UKI |

The main `Containerfile` performs these internal stages:

1. **rootfs** -- installs systemd-boot-unsigned, configures composefs/dracut,
   rebuilds initramfs, replaces bootloader with signed version
2. **lint** -- runs `bootc container lint` for compliance
3. **rechunk** -- uses chunkah to repack OCI layers for correct composefs hash
4. **UKI generation** -- `bootc container ukify` creates a signed, measured UKI
5. **final** -- composites the rechunked rootfs with the UKI

## Key Management

### Generating Keys

```bash
cd sealed
just generate-secure-boot-keys
```

This creates the full Secure Boot key hierarchy in `sealed/keys/`:

```text
keys/
  GUID              # Owner GUID
  PK/PK.pem         # Platform Key
  KEK/KEK.pem       # Key Exchange Key
  db/db.key          # Database private key (signs binaries)
  db/db.pem          # Database certificate
```

**The `keys/` directory is gitignored.** Keys must never be committed.

### CI Secrets

For GitHub Actions, store the key material as repository secrets:

| Secret | Content |
|--------|---------|
| `SECUREBOOT_KEY` | Contents of `keys/db/db.key` |
| `SECUREBOOT_CERT` | Contents of `keys/db/db.pem` |

The sealed workflow writes these to temporary files, uses them during build,
and deletes them in a cleanup step.

### Key Rotation

1. Generate new keys: `just generate-secure-boot-keys`
2. Update GHA secrets with new `db.key` and `db.pem`
3. Generate new OVMF vars: `just generate-ovmf-vars`
4. Rebuild sealed image
5. On enrolled hardware: update PK/KEK/db in firmware

## Local Build

### Prerequisites

- podman (rootless)
- just (`rpm-ostree install just`)
- Secure Boot keys (see above)

### Full Pipeline

```bash
cd sealed

# 1. Generate keys (one-time)
just generate-secure-boot-keys

# 2. Build everything (base image must exist)
just build-all ghcr.io/borninthedark/exousia:44

# Or step by step:
just sign-systemd-boot
just build-tools
just build ghcr.io/borninthedark/exousia:44
```

### Testing in a VM

```bash
# 3. Create QCOW2 disk image
just qcow2

# 4. Generate OVMF vars with custom SB keys
just generate-ovmf-vars

# 5. Boot in libvirt
just libvirt ./exousia-sealed-44.qcow2
```

The VM boots with:

- Secure Boot enabled (custom keys enrolled)
- TPM 2.0 emulation
- UEFI firmware (OVMF)
- btrfs root with zstd compression

### UKI Addons

Build signed kernel cmdline addons for specific boot configurations:

```bash
just uki-addon debug "systemd.debug_shell rd.systemd.debug_shell"
just uki-addon tpm-workaround "systemd.mask=systemd-tpm2-setup-early.service"
```

Addons are placed in `/boot/loader/addons/` and automatically picked up by
systemd-boot.

## CI Pipeline

The sealed build is a separate workflow (`sealed.yml`) called by Urahara
after Hiyori builds the base image. Enable it via the `enable_sealed`
workflow dispatch input.

```text
Urahara (orchestrator)
  -> Hikifune (CI) + Uhin (Security)
    -> Hiyori (Build base image)
      -> Sealed (wrap with measured boot)
```

The sealed job:

1. Installs podman on the GHA runner
2. Writes SB keys from secrets
3. Builds signed systemd-boot and tools containers
4. Builds the sealed image
5. Pushes with `sealed-f${VER}` tags
6. Signs with cosign (keyless OIDC)
7. Cleans up key material

## Composefs

The sealed image uses composefs for root filesystem integrity. The chunkah
rechunking step ensures the OCI image layers produce a correct composefs
digest that the initramfs can verify at boot.

Dracut is configured with the `bootc` module to mount the root filesystem
via composefs, verifying file integrity on every read.

## Credits

This implementation is adapted from
[travier/fedora-atomic-desktops-sealed](https://github.com/travier/fedora-atomic-desktops-sealed).
