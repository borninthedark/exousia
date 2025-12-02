# Security Boundaries and Input Handling

## YAML configuration paths
- Only YAML definitions located under `yaml-definitions/` (or the repository root `adnyeus.yml` fallback) are considered trusted.
- API calls must provide simple filenames for `definition_filename`; path traversal, nested paths, and absolute paths are rejected at the router layer.
- The YAML selector service resolves requested files against an allowlist of trusted directories and raises an error if a request attempts to escape them.

## YAML content handling
- User-supplied `yaml_content` is validated to reject common code-injection primitives before it is accepted or base64-encoded for transport.
- Base64 encoding is used strictly for transport safety; decoding happens only after validation to prevent injection payloads from bypassing checks.

## Webhook and trigger endpoints
- Webhook triggers should be fronted by infrastructure-level rate limiting (e.g., API gateway or reverse proxy) to mitigate brute-force or resource exhaustion attacks.
- GitHub workflow dispatch payloads are constrained to validated YAML filenames or validated YAML content, blocking path traversal attacks against workflow runners.

## Testing coverage
- Security regression tests guard against directory traversal attempts when triggering builds or resolving YAML definitions.
- YAML content validation tests assert that shell-injection primitives are rejected.
