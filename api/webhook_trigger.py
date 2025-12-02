#!/usr/bin/env python3
"""
Secure webhook trigger for GitHub repository_dispatch events.
Triggers the build.yml workflow with custom configuration via webhook.
"""
import os
import sys
import base64
import json
import argparse
from typing import Optional

from dotenv import load_dotenv

try:
    import requests
except ImportError:
    print("Error: requests library not installed")
    print("Install with: pip install requests")
    sys.exit(1)


def validate_yaml_content(yaml_content: str) -> bool:
    """
    Validate YAML content doesn't contain malicious patterns.

    Args:
        yaml_content: YAML content to validate

    Returns:
        True if safe, False otherwise
    """
    dangerous_patterns = [
        'eval(',
        'exec(',
        '__import__',
        'subprocess.call',
        'subprocess.run',
        'os.system',
        '$(',
        '`',
        '${',
    ]

    yaml_lower = yaml_content.lower()
    for pattern in dangerous_patterns:
        if pattern in yaml_lower:
            print(f"Warning: Potentially dangerous pattern detected: {pattern}")
            return False
    return True


def trigger_build(
    token: str,
    repo: str,
    image_type: str = "fedora-sway-atomic",
    distro_version: str = "43",
    enable_plymouth: bool = True,
    yaml_config: Optional[str] = None,
    yaml_content: Optional[str] = None,
    verbose: bool = False
) -> requests.Response:
    """
    Trigger GitHub repository_dispatch webhook to start a build.

    Args:
        token: GitHub Personal Access Token (needs repo scope)
        repo: Repository in format "owner/repo"
        image_type: Image type to build (default: fedora-sway-atomic)
        distro_version: Distro version (default: 43)
        enable_plymouth: Enable Plymouth boot splash (default: True)
        yaml_config: Path to YAML config file in repo (alternative to yaml_content)
        yaml_content: YAML content to use (will be base64 encoded)
        verbose: Print detailed information

    Returns:
        Response object from GitHub API

    Raises:
        ValueError: If YAML content validation fails
        requests.HTTPError: If GitHub API request fails
    """

    url = f"https://api.github.com/repos/{repo}/dispatches"

    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "exousia-webhook-trigger/1.0"
    }

    # Build client_payload
    client_payload = {
        "image_type": image_type,
        "distro_version": distro_version,
        "enable_plymouth": enable_plymouth,
    }

    # Add YAML content if provided
    if yaml_content:
        if not validate_yaml_content(yaml_content):
            raise ValueError("YAML content validation failed: contains potentially dangerous patterns")

        # Base64 encode for safe transmission
        encoded = base64.b64encode(yaml_content.encode()).decode()
        client_payload["yaml_content"] = encoded
        client_payload["yaml_encoding"] = "base64"

        if verbose:
            print(f"YAML content size: {len(yaml_content)} bytes")
            print(f"Base64 encoded size: {len(encoded)} bytes")

    elif yaml_config:
        client_payload["yaml_config"] = yaml_config

    payload = {
        "event_type": "api",
        "client_payload": client_payload
    }

    if verbose:
        print(f"\nRequest URL: {url}")
        print(f"Payload: {json.dumps(payload, indent=2)}\n")

    response = requests.post(url, headers=headers, json=payload, timeout=30)
    response.raise_for_status()

    return response


def main():
    """Main entry point for CLI usage."""
    parser = argparse.ArgumentParser(
        description="Trigger Exousia bootc build via GitHub webhook",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Trigger build with default configuration
  python webhook_trigger.py --token ghp_xxxxx

  # Trigger build with specific image type and version
  python webhook_trigger.py --token ghp_xxxxx --image-type fedora-bootc --distro-version 44

  # Trigger build with custom YAML config from repo
  python webhook_trigger.py --token ghp_xxxxx --yaml-config yaml-definitions/fedora-bootc.yml

  # Trigger build with YAML content from file
  python webhook_trigger.py --token ghp_xxxxx --yaml-content-file my-custom-config.yml

  # Use environment variable for token
  export GITHUB_TOKEN=ghp_xxxxx
  python webhook_trigger.py --image-type fedora-sway-atomic

Security Notes:
  - Token requires 'repo' scope for private repos or 'public_repo' for public repos
  - YAML content is validated before sending to prevent code injection
  - All inputs are validated server-side by the GitHub Actions workflow
  - Store tokens securely and never commit them to git
        """
    )

    parser.add_argument(
        "--token",
        help="GitHub Personal Access Token (or use GITHUB_TOKEN env var)"
    )
    parser.add_argument(
        "--repo",
        default="borninthedark/exousia",
        help="Repository in format owner/repo (default: borninthedark/exousia)"
    )
    parser.add_argument(
        "--image-type",
        default="fedora-sway-atomic",
        choices=[
            'fedora-bootc', 'fedora-silverblue', 'fedora-kinoite',
            'fedora-sway-atomic', 'fedora-onyx', 'fedora-budgie',
            'fedora-cinnamon', 'fedora-cosmic', 'fedora-deepin',
            'fedora-lxqt', 'fedora-mate', 'fedora-xfce',
            'arch', 'gentoo', 'debian', 'ubuntu', 'opensuse', 'proxmox'
        ],
        help="Image type to build (default: fedora-sway-atomic)"
    )
    parser.add_argument(
        "--distro-version",
        default="43",
        choices=['42', '43', '44', 'rawhide'],
        help="Distro version (default: 43)"
    )
    parser.add_argument(
        "--enable-plymouth",
        action="store_true",
        default=True,
        help="Enable Plymouth boot splash (default: enabled)"
    )
    parser.add_argument(
        "--disable-plymouth",
        action="store_true",
        help="Disable Plymouth boot splash"
    )
    parser.add_argument(
        "--yaml-config",
        help="Path to YAML config file in repository (e.g., yaml-definitions/fedora-bootc.yml)"
    )
    parser.add_argument(
        "--yaml-content-file",
        help="Local file containing YAML content to send"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose output"
    )

    load_dotenv()

    args = parser.parse_args()

    # Get token from args or environment
    token = args.token or os.getenv("GITHUB_TOKEN")
    if not token:
        print("Error: GitHub token required")
        print("Provide via --token argument or GITHUB_TOKEN environment variable")
        print("\nTo create a token:")
        print("1. Go to https://github.com/settings/tokens")
        print("2. Click 'Generate new token (classic)'")
        print("3. Select 'repo' scope")
        print("4. Copy the token")
        sys.exit(1)

    # Handle Plymouth flag
    enable_plymouth = not args.disable_plymouth if args.disable_plymouth else args.enable_plymouth

    # Read YAML content from file if provided
    yaml_content = None
    if args.yaml_content_file:
        try:
            with open(args.yaml_content_file, 'r', encoding='utf-8') as f:
                yaml_content = f.read()

            if args.verbose:
                print(f"Loaded YAML content from: {args.yaml_content_file}")
        except FileNotFoundError:
            print(f"Error: File not found: {args.yaml_content_file}")
            sys.exit(1)
        except Exception as e:
            print(f"Error reading file: {e}")
            sys.exit(1)

    # Display configuration
    print("=" * 60)
    print("Exousia Webhook Trigger")
    print("=" * 60)
    print(f"Repository:       {args.repo}")
    print(f"Image Type:       {args.image_type}")
    print(f"Distro Version:   {args.distro_version}")
    print(f"Plymouth:         {'Enabled' if enable_plymouth else 'Disabled'}")

    if args.yaml_config:
        print(f"YAML Config:      {args.yaml_config}")
    elif yaml_content:
        print(f"YAML Content:     {len(yaml_content)} bytes from {args.yaml_content_file}")
    else:
        print("YAML Config:      Auto-detect")

    print("=" * 60)

    # Trigger the webhook
    try:
        print("\nTriggering webhook...")
        response = trigger_build(
            token=token,
            repo=args.repo,
            image_type=args.image_type,
            distro_version=args.distro_version,
            enable_plymouth=enable_plymouth,
            yaml_config=args.yaml_config,
            yaml_content=yaml_content,
            verbose=args.verbose
        )

        print(f"✓ Webhook triggered successfully!")
        print(f"  Status Code: {response.status_code}")
        print(f"\nView workflow runs at:")
        print(f"  https://github.com/{args.repo}/actions")

    except ValueError as e:
        print(f"✗ Validation Error: {e}")
        sys.exit(1)
    except requests.exceptions.HTTPError as e:
        print(f"✗ GitHub API Error: {e}")
        if e.response.status_code == 401:
            print("  Check that your token is valid and has 'repo' scope")
        elif e.response.status_code == 404:
            print("  Check that the repository name is correct")
        elif e.response.status_code == 422:
            print("  Check that the payload format is correct")
        sys.exit(1)
    except requests.exceptions.RequestException as e:
        print(f"✗ Network Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"✗ Unexpected Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
