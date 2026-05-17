# Beszel Container Monitoring

Lightweight container and system monitoring via [Beszel](https://www.beszel.dev/).

## Architecture

```text
┌─────────────────────┐       ┌──────────────────────┐
│  Beszel Hub         │◄─SSH──│  Beszel Agent        │
│  :8090 (web UI)     │       │  :45876              │
│  exousia.network    │       │  exousia.network     │
│  alias: beszel      │       │  alias: beszel-agent │
└─────────────────────┘       └──────────────────────┘
        │                              │
        ▼                              ▼
  monitor.exousia.local         podman.sock (ro)
  (Caddy reverse proxy)        → container stats
```text

- **Hub**: Web UI + data storage, accessible at `monitor.exousia.local`
- **Agent**: Same network as hub, reads Podman socket for container metrics
- **Connectivity**: Hub connects to agent via container DNS (`beszel-agent:45876`)

## Quadlet Files

- `overlays/deploy/beszel.container` — Hub
- `overlays/deploy/beszel-agent.container` — Agent

## Secrets

Agent credentials stored outside the repo:

```text
~/.config/beszel/agent.env  (mode 600)
```text

Contains `KEY` (hub public key) and `TOKEN` (agent auth token).
Referenced via `EnvironmentFile=%h/.config/beszel/agent.env` in the quadlet.

Note: `KEY` contains a space (`ssh-ed25519 <base64>`), so it must be quoted in
the quadlet if set inline: `Environment="KEY=ssh-ed25519 ..."`. Using an env
file avoids this issue.

## Deployment

```bash
# Copy quadlets to systemd
cp overlays/deploy/beszel.container ~/.config/containers/systemd/
cp overlays/deploy/beszel-agent.container ~/.config/containers/systemd/

# Reload and start
systemctl --user daemon-reload
systemctl --user start beszel beszel-agent
```text

## First-Time Setup

1. Open `http://localhost:8090` and create an admin account
2. Add a system in the UI:
   - **Name**: `exousia`
   - **Host**: `beszel-agent`
   - **Port**: `45876`
3. The UI provides KEY and TOKEN values — write them to `~/.config/beszel/agent.env`:

   ```text
   KEY=ssh-ed25519 <public-key>
   TOKEN=<token>
   ```

1. Start the agent: `systemctl --user start beszel-agent`

## Networking

The agent runs on `exousia.network` (not `network=host`) so the hub can reach
it via container DNS at `beszel-agent:45876`.

Trade-off: The agent sees the container veth (`eth0`) rather than the host WiFi
interface (`wlo1`). Container CPU/memory/disk stats are accurate; host network
interface stats reflect container-level traffic only. If full host network
visibility is needed, switch to WebSocket mode with `HUB_URL` env var.

## Container Monitoring

The agent reads the Podman socket to report per-container CPU/memory/network
stats. Key config:

- Socket mounted to Docker-standard path: `/var/run/docker.sock`
- `DOCKER_HOST=unix:///var/run/docker.sock` env var set
- `SecurityLabelDisable=true` in quadlet (allows SELinux-restricted socket access)

The agent does not log container discovery — containers appear silently in the
hub UI under the system's "Containers" section. Stats populate after the first
polling interval (~1 minute).

## Container Healthchecks

Beszel reports container health status from Podman's healthcheck mechanism. All
quadlets in `overlays/deploy/` have `HealthCmd` directives. Key patterns:

| Service type | HealthCmd format | Example |
|---|---|---|
| HTTP (with wget) | `wget -q -O /dev/null URL \|\| exit 1` | dashy, forgejo |
| HTTP (with curl) | `curl -f URL \|\| exit 1` | immich, paperless, open-webui |
| PostgreSQL | `pg_isready -U <user> \|\| exit 1` | forgejo-db, paperless-db |
| Redis | `redis-cli ping \|\| exit 1` | immich-redis, paperless-redis |
| Process check | `pgrep <process> \|\| exit 1` | temporal-server, immich-ml |
| No shell (scratch) | None (remove HealthCmd) | beszel, coredns, openobserve |

Important notes:

- `|| exit 1` is REQUIRED — it forces `CMD-SHELL` mode (without it, podman uses `CMD` exec mode which fails on multi-word commands)
- Exception: scratch/distroless containers with no `/bin/sh` cannot have healthchecks at all — remove all `Health*` directives
- BusyBox wget: use `-q -O /dev/null` (not `-qO` — BusyBox parses flags differently)
- Temporal-server binds to container IP, not localhost — HTTP checks fail, use `pgrep`
- immich-ml is slow to start (ML model loading) — use process check, not HTTP
- Check available tools: `podman exec <name> which wget curl python3 pgrep`

## Image Policy

`docker.io/henrygd` is allowlisted in `~/.config/containers/policy.json`.

## Reverse Proxy (Caddy)

Beszel uses PocketBase auth internally, which sets `Authorization` headers that
conflict with Authelia's forward-auth (`failed to parse content of Authorization
header: invalid scheme`). **Do not use `import authelia`** on this route.

Instead, Beszel authenticates via OIDC directly with Authelia — no forward-auth
needed. The Caddy config is a plain reverse proxy:

```caddyfile
monitor.exousia.local {
 tls internal
 reverse_proxy beszel:8090
}
```text

After a Caddy config change, a full `systemctl --user restart caddy` may be
required — `caddy reload` can cache stale routes.

## SSO (Authelia OIDC)

Beszel uses Authelia as an OIDC provider (not forward-auth). Configuration:

### Authelia (`~/.config/authelia/configuration.yml`)

```yaml
identity_providers:
  oidc:
    hmac_secret: '<secret>'
    jwks:
      - key_id: 'exousia'
        algorithm: 'RS256'
        use: 'sig'
        key: |
          <RSA private key PEM>
    clients:
      - client_id: 'beszel'
        client_name: 'Beszel'
        client_secret: '<argon2 hash>'
        token_endpoint_auth_method: 'client_secret_post'
        redirect_uris:
          - 'https://monitor.exousia.local/api/oauth2-redirect'
        scopes: ['openid', 'profile', 'email']
        authorization_policy: 'one_factor'
```text

Key details:

- `token_endpoint_auth_method` must be `client_secret_post` (PocketBase default)
- Hash the client secret with `authelia crypto hash generate argon2 --password '<secret>'`
- JWKS RSA key generated via `openssl genrsa -out oidc-jwks.pem 4096`

### Beszel (PocketBase admin `/_/#/settings`)

Configure OAuth2 provider "OpenID Connect":

- **Client ID**: `beszel`
- **Client Secret**: (plaintext secret)
- **Auth URL**: `https://auth.exousia.local/api/oidc/authorization`
- **Token URL**: `https://auth.exousia.local/api/oidc/token`
- **User Info URL**: `https://auth.exousia.local/api/oidc/userinfo`

### Beszel container env

- `APP_URL=https://monitor.exousia.local` — cookie domain
- `USER_CREATION=true` — auto-creates accounts on first OIDC login
- `SSL_CERT_FILE=/etc/ssl/certs/caddy-root-ca.crt` — trusts Caddy's internal CA
  for OIDC token exchange

The CA cert is mounted from `~/.config/beszel/caddy-root-ca.crt` (extracted via
`podman exec caddy cat /data/caddy/pki/authorities/local/root.crt`).

## Access

- Direct: `http://localhost:8090`
- Reverse proxy: `https://monitor.exousia.local`
- Dashy: listed under Monitoring section
