# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| Latest (main branch) | Yes |
| Older releases | No |

Only the latest image built from the `main` branch is supported with security
updates. Older tagged releases do not receive patches.

## Reporting a Vulnerability

If you discover a security vulnerability in Exousia, please report it
responsibly:

1. **Do not** open a public GitHub issue for security vulnerabilities.
2. Send a private report via
   [GitHub Security Advisories](https://github.com/borninthedark/exousia/security/advisories/new).
3. Include as much detail as possible: affected component, reproduction steps,
   and potential impact.

You should receive an acknowledgment within 48 hours. We will work with you
to understand the scope and develop a fix before any public disclosure.

## Security Measures

Exousia employs a defense-in-depth approach:

### CI/CD Pipeline

- **Checkov** -- Static analysis for Containerfile and IaC misconfigurations
- **Trivy** -- Container image vulnerability scanning (config + image)
- **Bandit** -- Python SAST for security anti-patterns
- **Hadolint** -- Dockerfile/Containerfile best-practice linting
- **Cosign** -- Image signing for supply-chain integrity
- **Dependabot** -- Automated dependency security updates

### Image Hardening

- Minimal package set (no unnecessary services)
- SELinux enforcing mode supported
- PAM U2F hardware authentication support
- composefs enabled for integrity verification
- bootc container lint enforced at build time
- Build-time caches and logs cleaned from final image

### Development Practices

- Pre-commit hooks enforce linting and security checks locally
- Conventional commits for auditable change history
- TDD with minimum 75% code coverage on Python tools

## Dependency Management

Dependencies are managed via:

- **GitHub Dependabot** for automated security updates on Actions and pip
  dependencies
- **uv lock** for reproducible Python dependency resolution

## Contact

For security-related questions that are not vulnerability reports, open a
regular GitHub issue.
