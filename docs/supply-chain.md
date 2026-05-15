# Supply Chain Hardening

Container build supply chain practices adopted from
[Project Hummingbird](https://hummingbird-project.io/) and
[Konflux](https://konflux-ci.dev/).

## Practices

### 1. Digest-Pinned Base Images

The Gremmy build step resolves the base image digest at build time and
rewrites the `FROM` line to pin by `sha256` digest. This ensures
builds are hermetic — the same commit always builds against the same
base image content, regardless of tag mutations.

```dockerfile
FROM registry:5000/fedora-sway-atomic:44@sha256:abc123...
```

The local registry mirror (updated daily at 07:30 via
`mirror-base-image.timer`) is checked first; quay.io upstream is the
fallback.

### 2. SBOM Generation (CycloneDX)

Every build generates a Software Bill of Materials in CycloneDX JSON
format using Trivy. The SBOM is:

- Generated in the Gremmy build job
- Stored as a separate OCI artifact tagged `<image-tag>-sbom`
- Referenced from the main image via the `org.opencontainers.image.sbom` annotation

To extract the SBOM from a built image:

```bash
# Get the SBOM artifact tag from the image annotation
SBOM_REF=$(skopeo inspect --tls-verify=false docker://registry:5000/exousia:latest \
  | python3 -c "import sys,json; print(json.load(sys.stdin).get('Annotations',{}).get('org.opencontainers.image.sbom',''))")

# Copy the SBOM artifact and extract the file
ID=$(podman create --tls-verify=false "${SBOM_REF}")
podman cp "${ID}":/sbom-cyclonedx.json sbom-cyclonedx.json
podman rm "${ID}"
python3 -m json.tool sbom-cyclonedx.json
```

### 3. SLSA Provenance

A SLSA v1 provenance document is generated for each build, capturing:

- **Builder ID** — Forgejo Actions run URL
- **Source** — repository URL + commit SHA
- **Entry point** — workflow file path
- **Parameters** — image name, tag, base image
- **Materials** — base image URI + digest

The provenance is stored as a separate OCI artifact tagged `<image-tag>-provenance`
and referenced from the main image via the `org.opencontainers.image.provenance`
annotation.

### 4. OCI Image Labels

Built images include standard OCI labels for traceability:

| Label | Value |
|-------|-------|
| `org.opencontainers.image.source` | Repository URL |
| `org.opencontainers.image.revision` | Git commit SHA |
| `org.opencontainers.image.created` | Build timestamp (UTC) |
| `org.opencontainers.image.version` | Git tag version |
| `org.opencontainers.image.title` | Image name |
| `org.opencontainers.image.base.name` | Base image with digest |

### 5. CVE Policy Gate

The Lille (Verify) job enforces a zero-critical-CVE policy:

- Trivy scans the built image for CRITICAL severity vulnerabilities
- **Any critical CVE blocks the release** (`exit 1`)
- HIGH severity vulnerabilities are reported but do not block
- The gate runs against the image in the local registry after push

### 6. Trivy Version Pinning

Trivy is installed by resolving `latest` from the GitHub API at build
time, then verified against the release's published SHA-256 checksums.
This ensures:

- Always using the latest scanner with current vulnerability databases
- No unsigned or tampered binaries via checksum verification
- No hardcoded version that silently goes stale

## Pipeline Flow

```text
Bambietta (CI) ──┐
                 ├─→ Gremmy (Build) ─→ Lille (Verify) ─→ Jugram (Gate)
Askin (Security) ┘     │                   │
                       │                   │
                  SBOM + provenance    CVE policy
                  OCI labels           gate (critical=0)
                  digest-pinned base   metadata validation
```

## What's Not Yet Implemented

| Practice | Status | Notes |
|----------|--------|-------|
| Image signing (cosign/sigstore) | Not yet | Requires key management strategy |
| In-toto attestation framework | Not yet | Would replace custom provenance JSON |
| Hermetic builds (network-isolated) | Partial | Base pinned, but dnf still fetches packages |
| Reproducible builds | Not yet | OCI labels aid traceability but builds aren't bit-for-bit reproducible |
