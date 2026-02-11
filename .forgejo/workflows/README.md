# Espada Pipeline

Forgejo Actions workflows mirroring the Shinigami Pipeline (GitHub Actions).
Named after the Espada from BLEACH.

## Workflows

| Espada | File | Number | Role |
|--------|------|--------|------|
| **Starrk** | `starrk.yml` | Primera (#1) | Orchestrator: calls Szayelaporro + Ulquiorra, then Harribel, gate, Nelliel |
| **Szayelaporro** | `szayelaporro.yml` | Octava (#8) | CI: lint + test (mirrors Mayuri) |
| **Ulquiorra** | `ulquiorra.yml` | Cuatro (#4) | Security scanning (mirrors Byakuya, no Checkov/Trivy) |
| **Harribel** | `harribel.yml` | Tres (#3) | Build & push (mirrors Kyoraku, localhost:5000, no cosign/semver) |
| **Grimmjow** | `grimmjow.yml` | Sexta (#6) | Weekly ZFS build: mirrors Starrk with `enable_zfs: true` |
| **Nelliel** | `nelliel.yml` | Former Tres | Post-CI: generates STATUS.md, updates README badges |

## Pipeline Flow

```text
Starrk -> Szayelaporro + Ulquiorra (parallel) -> Harribel -> Gate
                                                               |
Nelliel (push to main only) <----------------------------------+

Grimmjow (weekly) -> Szayelaporro + Ulquiorra (parallel) -> Harribel (ZFS) -> Gate
```

## Key Differences from Shinigami

- Runs on `self-hosted` runners
- No Checkov or Trivy
- Pushes to `localhost:5000` (local registry)
- No cosign signing or semver releases

## See Also

- [Shinigami Pipeline](../../.github/workflows/) -- GitHub Actions primary pipeline
