# Webhook API Documentation

This document describes how to trigger builds programmatically using GitHub's repository_dispatch webhook API.

## Overview

The Exousia build pipeline can be triggered remotely via webhooks, allowing you to:
- Trigger builds from external services
- Integrate with CI/CD pipelines
- Automate builds based on external events
- Test different configurations programmatically

## Security Model

### Authentication
- Uses GitHub Personal Access Token (PAT) with `repo` scope
- All requests must be authenticated via GitHub API
- Tokens are validated by GitHub before reaching the workflow

### Input Validation
The workflow validates all inputs server-side:
- ✅ Image type must be from allowed list
- ✅ Distro version must be from allowed list
- ✅ Boolean values are strictly validated
- ✅ File paths are sanitized to prevent path traversal
- ✅ YAML configs must be in approved directories

### Rate Limiting
- GitHub API limits: 5,000 requests/hour for authenticated requests
- Workflow concurrency: One build per branch at a time (cancel-in-progress enabled)

## Setup

### 1. Create GitHub Personal Access Token

1. Go to https://github.com/settings/tokens
2. Click **"Generate new token (classic)"**
3. Give it a descriptive name: `exousia-webhook-trigger`
4. Select scopes:
   - For private repos: `repo` (full control)
   - For public repos: `public_repo` (access to public repositories)
5. Click **"Generate token"**
6. **Copy the token immediately** (you won't see it again)
7. Store securely in your password manager or secrets vault

### 2. Install Dependencies

```bash
pip install requests
```

### 3. Set Environment Variable (Optional)

```bash
# Add to ~/.bashrc or ~/.zshrc
export GITHUB_TOKEN="ghp_your_token_here"
```

Alternatively, create a local `.env` file (gitignored) to keep secrets out of your shell history while still letting the CLI
pick up the token automatically:

```bash
echo "GITHUB_TOKEN=ghp_your_token_here" > .env
```

## Usage

### Basic Examples

#### Trigger with Default Settings
```bash
python api/webhook_trigger.py --token ghp_xxxxx
```

#### Trigger Specific Image Type
```bash
python api/webhook_trigger.py \
  --token ghp_xxxxx \
  --image-type fedora-bootc \
  --distro-version 44
```

#### Disable Plymouth Boot Splash
```bash
python api/webhook_trigger.py \
  --token ghp_xxxxx \
  --disable-plymouth
```

#### Use Custom YAML Config from Repository
```bash
# New simplified format - just provide the filename
python api/webhook_trigger.py \
  --token ghp_xxxxx \
  --yaml sway-bootc.yml

# Or use the full path (also works)
python api/webhook_trigger.py \
  --token ghp_xxxxx \
  --yaml-config yaml-definitions/fedora-bootc.yml
```

#### Use YAML Content from Local File
```bash
python api/webhook_trigger.py \
  --token ghp_xxxxx \
  --yaml-content-file my-custom-config.yml
```

#### Verbose Output for Debugging
```bash
python api/webhook_trigger.py \
  --token ghp_xxxxx \
  --image-type fedora-sway-atomic \
  --verbose
```

### Advanced Examples

#### Trigger from Shell Script
```bash
#!/bin/bash
# trigger-build.sh

export GITHUB_TOKEN="ghp_xxxxx"

python api/webhook_trigger.py \
  --image-type fedora-sway-atomic \
  --distro-version 43 \
  --enable-plymouth
```

#### Trigger with Error Handling
```bash
#!/bin/bash
set -euo pipefail

if python api/webhook_trigger.py --token "$GITHUB_TOKEN" --verbose; then
  echo "✓ Build triggered successfully"
  echo "View at: https://github.com/borninthedark/exousia/actions"
else
  echo "✗ Failed to trigger build"
  exit 1
fi
```

## API Reference

### Command-Line Arguments

| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| `--token` | Yes* | `$GITHUB_TOKEN` | GitHub Personal Access Token |
| `--repo` | No | `borninthedark/exousia` | Repository in format `owner/repo` |
| `--image-type` | No | `fedora-sway-atomic` | Image type to build |
| `--distro-version` | No | `43` | Distro version (42, 43, 44, rawhide) |
| `--enable-plymouth` | No | `true` | Enable Plymouth boot splash |
| `--disable-plymouth` | No | - | Disable Plymouth boot splash |
| `--yaml-config` | No | - | YAML config file path (auto-resolved) |
| `--yaml-content-file` | No | - | Local file with YAML content |
| `-v`, `--verbose` | No | - | Enable verbose output |

\* Required unless `GITHUB_TOKEN` environment variable is set

**Note on `--yaml-config` path resolution:**
The `yaml_config` parameter now supports automatic path resolution. When you provide a filename or path, the system will:
1. Try the exact path as specified
2. Look in the `yaml-definitions/` directory
3. Search the entire repository (preferring `yaml-definitions/` matches)

This means you can use any of these formats:
- Just the filename: `sway-bootc.yml` → automatically finds `yaml-definitions/sway-bootc.yml`
- Subdirectory path: `yaml-definitions/sway-bootc.yml` → works as before
- Any path in repo: `configs/custom/my-config.yml` → automatically found via repo search

Path traversal protection is enforced (e.g., `../../../etc/passwd` will be rejected).

### Supported Image Types

**Fedora Variants:**
- `fedora-bootc` - Fedora bootc base image
- `fedora-silverblue` - Fedora Silverblue (GNOME)
- `fedora-kinoite` - Fedora Kinoite (KDE Plasma)
- `fedora-sway-atomic` - Fedora Sway Atomic Desktop
- `fedora-onyx` - Fedora Onyx (Budgie on Wayland)
- `fedora-budgie` - Fedora Budgie Atomic
- `fedora-cinnamon` - Fedora Cinnamon Atomic
- `fedora-cosmic` - Fedora COSMIC Desktop
- `fedora-deepin` - Fedora Deepin Atomic
- `fedora-lxqt` - Fedora LXQt Atomic
- `fedora-mate` - Fedora MATE Atomic
- `fedora-xfce` - Fedora Xfce Atomic

> **Note:** References to non-Fedora bootc distros have been shelved for a future iteration; the webhook now targets Fedora variants exclusively.

### Supported Distro Versions

- `42` - Fedora 42
- `43` - Fedora 43 (current default)
- `44` - Fedora 44
- `rawhide` - Fedora Rawhide (bleeding edge)

### Fedora bootc desktop overrides

When requesting the `fedora-bootc` image type, the `client_payload` accepts either
`window_manager` **or** `desktop_environment` to regenerate the YAML with the requested
desktop before validation. Supplying both fields results in a validation error to avoid
ambiguous desktop selection.

```json
{
  "event_type": "api",
  "client_payload": {
    "image_type": "fedora-bootc",
    "distro_version": "44",
    "enable_plymouth": true,
    "window_manager": "river"
  }
}
```

### Fedora version source precedence

The build workflow resolves Fedora metadata through `tools/resolve_build_config.py` using
these sources, in order of priority:

1. Explicit repository/ workflow dispatch inputs (`image_type`, `distro_version`).
2. `.fedora-version` file in the repository when dispatch inputs are set to `current`.
3. Built-in defaults (`43:fedora-sway-atomic`).

This ensures CI runs stay aligned with repository defaults while still allowing API calls
to override the version and image type at dispatch time.

## Direct API Usage

### Using cURL

```bash
# Simplified: just provide the filename
curl -X POST \
  -H "Accept: application/vnd.github+json" \
  -H "Authorization: Bearer $GITHUB_TOKEN" \
  -H "X-GitHub-Api-Version: 2022-11-28" \
  https://api.github.com/repos/borninthedark/exousia/dispatches \
  -d '{
    "event_type": "api",
    "client_payload": {
      "image_type": "fedora-bootc",
      "distro_version": "44",
      "enable_plymouth": true,
      "yaml_config": "sway-bootc.yml"
    }
  }'

# Or use full path (also works)
curl -X POST \
  -H "Accept: application/vnd.github+json" \
  -H "Authorization: Bearer $GITHUB_TOKEN" \
  -H "X-GitHub-Api-Version: 2022-11-28" \
  https://api.github.com/repos/borninthedark/exousia/dispatches \
  -d '{
    "event_type": "api",
    "client_payload": {
      "image_type": "fedora-sway-atomic",
      "distro_version": "43",
      "enable_plymouth": true,
      "yaml_config": "yaml-definitions/fedora-sway-atomic.yml"
    }
  }'
```

### Using Python Requests

```python
import requests

token = "ghp_your_token_here"
repo = "borninthedark/exousia"

url = f"https://api.github.com/repos/{repo}/dispatches"
headers = {
    "Accept": "application/vnd.github+json",
    "Authorization": f"Bearer {token}",
    "X-GitHub-Api-Version": "2022-11-28",
}

payload = {
    "event_type": "api",
    "client_payload": {
        "image_type": "fedora-bootc",
        "distro_version": "44",
        "enable_plymouth": True,
    }
}

response = requests.post(url, headers=headers, json=payload)
response.raise_for_status()
print("✓ Build triggered successfully")
```

### Using JavaScript/Node.js

```javascript
const fetch = require('node-fetch');

const token = 'ghp_your_token_here';
const repo = 'borninthedark/exousia';

const url = `https://api.github.com/repos/${repo}/dispatches`;
const headers = {
  'Accept': 'application/vnd.github+json',
  'Authorization': `Bearer ${token}`,
  'X-GitHub-Api-Version': '2022-11-28',
};

const payload = {
  event_type: 'api',
  client_payload: {
    image_type: 'fedora-sway-atomic',
    distro_version: '43',
    enable_plymouth: true,
  }
};

fetch(url, {
  method: 'POST',
  headers: headers,
  body: JSON.stringify(payload)
})
.then(response => {
  if (response.ok) {
    console.log('✓ Build triggered successfully');
  } else {
    console.error('✗ Failed to trigger build:', response.statusText);
  }
})
.catch(error => console.error('Error:', error));
```

## Integration Examples

### GitLab CI/CD Pipeline

```yaml
# .gitlab-ci.yml
trigger-exousia-build:
  stage: deploy
  script:
    - pip install requests
    - |
      python3 - <<EOF
      import requests
      response = requests.post(
          "https://api.github.com/repos/borninthedark/exousia/dispatches",
          headers={
              "Accept": "application/vnd.github+json",
              "Authorization": f"Bearer ${GITHUB_TOKEN}",
              "X-GitHub-Api-Version": "2022-11-28",
          },
          json={
              "event_type": "api",
              "client_payload": {
                  "image_type": "fedora-sway-atomic",
                  "distro_version": "43",
                  "enable_plymouth": True,
              }
          }
      )
      response.raise_for_status()
      print("✓ Build triggered")
      EOF
  only:
    - main
```

### Jenkins Pipeline

```groovy
pipeline {
    agent any
    environment {
        GITHUB_TOKEN = credentials('github-token')
    }
    stages {
        stage('Trigger Exousia Build') {
            steps {
                sh '''
                    curl -X POST \
                      -H "Accept: application/vnd.github+json" \
                      -H "Authorization: Bearer $GITHUB_TOKEN" \
                      -H "X-GitHub-Api-Version: 2022-11-28" \
                      https://api.github.com/repos/borninthedark/exousia/dispatches \
                      -d '{
                        "event_type": "api",
                        "client_payload": {
                          "image_type": "fedora-bootc",
                          "distro_version": "43",
                          "enable_plymouth": true
                        }
                      }'
                '''
            }
        }
    }
}
```

### Scheduled Cron Job

```bash
#!/bin/bash
# /etc/cron.daily/exousia-build

export GITHUB_TOKEN="ghp_xxxxx"

python3 /path/to/exousia/api/webhook_trigger.py \
  --image-type fedora-sway-atomic \
  --distro-version 43 \
  >> /var/log/exousia-trigger.log 2>&1
```

## Troubleshooting

### Error: 401 Unauthorized
**Cause:** Invalid or expired GitHub token
**Solution:** Generate a new token with `repo` scope

### Error: 404 Not Found
**Cause:** Repository name is incorrect or token lacks access
**Solution:** Verify repository name and token permissions

### Error: 422 Unprocessable Entity
**Cause:** Invalid payload format
**Solution:** Check payload structure matches the API specification

### Build Doesn't Start
**Cause:** Workflow validation failed
**Solution:**
1. Check workflow runs: https://github.com/borninthedark/exousia/actions
2. Review validation errors in the "Validate webhook inputs" step
3. Verify inputs match allowed values

### Rate Limiting
**Cause:** Too many API requests
**Solution:** GitHub allows 5,000 requests/hour. Wait or use conditional triggers.

## Security Best Practices

### Token Management
- ✅ Store tokens in secure password manager or vault
- ✅ Use environment variables, never hardcode tokens
- ✅ Rotate tokens every 90 days
- ✅ Use separate tokens for different services
- ✅ Revoke tokens immediately if compromised

### Secrets in CI/CD
- ✅ Use your CI/CD system's secret management (GitHub Secrets, GitLab CI/CD Variables, etc.)
- ✅ Never log token values
- ✅ Use masked variables in pipeline logs
- ✅ Restrict secret access to specific branches/environments

### Input Validation
- ✅ All inputs are validated server-side by the workflow
- ✅ Client-side validation is a convenience, not security
- ✅ Path traversal attempts are automatically blocked
- ✅ Only whitelisted image types and versions are accepted

### Network Security
- ✅ All communication uses HTTPS (enforced by GitHub)
- ✅ GitHub's API includes DDoS protection
- ✅ No need to expose additional endpoints
- ✅ No custom webhook servers required

## Monitoring

### View Workflow Runs
https://github.com/borninthedark/exousia/actions

### Check Build Status
```bash
# Using GitHub CLI (gh)
gh run list --repo borninthedark/exousia --limit 5

# Using API
curl -H "Authorization: Bearer $GITHUB_TOKEN" \
  https://api.github.com/repos/borninthedark/exousia/actions/runs
```

## Support

- **Issues:** https://github.com/borninthedark/exousia/issues
- **Discussions:** https://github.com/borninthedark/exousia/discussions
- **Documentation:** https://github.com/borninthedark/exousia/tree/main/docs

## Related Documentation

- [GitHub repository_dispatch API](https://docs.github.com/en/rest/repos/repos#create-a-repository-dispatch-event)
- [GitHub Actions Workflow Triggers](https://docs.github.com/en/actions/using-workflows/events-that-trigger-workflows#repository_dispatch)
- [GitHub Personal Access Tokens](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/creating-a-personal-access-token)
