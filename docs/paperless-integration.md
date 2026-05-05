# Paperless-ngx Integration

Paperless-ngx serves as the document management system for Exousia, accessible
at both `https://paperless.exousia.local` and `https://docs.exousia.local`.

## API Access

API requests bypass Authelia SSO and authenticate via token. Generate a token
from the Paperless admin UI at `https://paperless.exousia.local/admin/`.

```bash
TOKEN="your-api-token"
API="http://127.0.0.1:8000/api"
HOST="Host: paperless.exousia.local"
```

The direct host port (`127.0.0.1:8000`) is used for API calls to avoid SSO
interception. The `Host` header is required for Paperless to accept the request.

## Uploading Documents

Upload a single document with a tag:

```bash
curl -s -X POST -H "Authorization: Token $TOKEN" -H "$HOST" \
  -F "document=@docs/my-doc.md" \
  -F "title=my-doc" \
  -F "tags=1" \
  "$API/documents/post_document/"
```

## Bulk Upload (Project Docs)

Upload all markdown files from the `docs/` directory:

```bash
TAG_ID=1  # exousia tag

for f in $(find docs/ -name '*.md' -type f | sort); do
  title=$(echo "$f" | sed 's|docs/||;s|\.md$||;s|/| - |g')
  curl -s -X POST -H "Authorization: Token $TOKEN" -H "$HOST" \
    -F "document=@$f" \
    -F "title=$title" \
    -F "tags=$TAG_ID" \
    "$API/documents/post_document/"
done
```

## Tags

| Tag | Color | Purpose |
|-----|-------|---------|
| `exousia` | `#4fc3f7` | Project documentation from the repo |

## Caddy Configuration

Paperless responds to both `paperless.exousia.local` and `docs.exousia.local`.
API paths (`/api/*`) bypass Authelia SSO for token-based access:

```caddyfile
paperless.exousia.local, docs.exousia.local {
    tls internal
    @api path /api/*
    reverse_proxy @api paperless:8000
    import authelia
    reverse_proxy paperless:8000
}
```

## Superuser Setup

Required on first start:

```bash
podman exec -it paperless python3 manage.py createsuperuser
```

## SMTP

Paperless uses Proton Mail SMTP for notifications. Credentials are in
`~/.config/paperless/smtp.env` (loaded via `EnvironmentFile` in the quadlet).

---

**[Back to Documentation Index](README.md)** | **[Back to Main README](../README.md)**
