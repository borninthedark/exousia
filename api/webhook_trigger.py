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
from pathlib import Path
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
    yaml: Optional[str] = None,
    os: Optional[str] = None,
    window_manager: Optional[str] = None,
    desktop_environment: Optional[str] = None,
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
        yaml: YAML config - can be:
            - Filename only (e.g., 'sway-bootc.yml') - will look in yaml-definitions/
            - Any path (e.g., 'custom/my-config.yml', 'yaml-definitions/sway-bootc.yml')
            - Full YAML content (will be base64 encoded)
            - If None, auto-selected based on OS/DE/WM inputs
        os: Operating system (fedora only) for auto-selection
        window_manager: Window manager (e.g., 'sway') - can be combined with desktop_environment
        desktop_environment: Desktop environment (e.g., 'kde', 'mate', 'lxqt') - can be combined with window_manager
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

    # Add OS/DE/WM selection if provided
    if os:
        client_payload["os"] = os
    if window_manager:
        client_payload["window_manager"] = window_manager
    if desktop_environment:
        client_payload["desktop_environment"] = desktop_environment

    # Handle YAML parameter (unified yaml_config and yaml_content)
    yaml_config = None
    yaml_content = None

    if yaml:
        # Detect if it's a file reference or actual YAML content
        # If it contains newlines or starts with typical YAML markers, treat as content
        if '\n' in yaml or yaml.strip().startswith(('name:', 'description:', 'modules:', 'base-image:')):
            yaml_content = yaml
        else:
            # It's a filename or path
            yaml_filename = yaml

            # Only auto-prepend yaml-definitions/ if it's a simple filename (no path separators)
            if '/' not in yaml_filename and yaml_filename != 'adnyeus.yml':
                yaml_filename = f'yaml-definitions/{yaml_filename}'

            yaml_path = Path(yaml_filename)

            if yaml_path.is_absolute() or any(part == ".." for part in yaml_path.parts):
                raise ValueError("YAML config path must be relative and cannot traverse directories")

            allowed_roots = {Path("yaml-definitions"), Path("custom-configs")}
            if len(yaml_path.parts) > 1 and yaml_path.parts[0] not in {root.parts[0] for root in allowed_roots}:
                raise ValueError("YAML config path must stay within allowed directories (yaml-definitions/, custom-configs/)")

            yaml_config = yaml_path.as_posix()
    # If no YAML specified, allow auto-selection based on OS/DE/WM
    # Don't default to adnyeus.yml - let the workflow auto-select

    # Add YAML content or config to payload
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
        # Read the YAML file and send its content
        yaml_file_path = Path(yaml_config)

        if not yaml_file_path.exists():
            raise ValueError(f"YAML config file not found: {yaml_config}")

        try:
            with open(yaml_file_path, 'r', encoding='utf-8') as f:
                file_content = f.read()

            if not validate_yaml_content(file_content):
                raise ValueError("YAML file validation failed: contains potentially dangerous patterns")

            # Base64 encode for safe transmission
            encoded = base64.b64encode(file_content.encode()).decode()
            client_payload["yaml_content"] = encoded
            client_payload["yaml_encoding"] = "base64"

            if verbose:
                print(f"YAML file: {yaml_config}")
                print(f"YAML content size: {len(file_content)} bytes")
                print(f"Base64 encoded size: {len(encoded)} bytes")

        except Exception as e:
            raise ValueError(f"Error reading YAML config file '{yaml_config}': {e}")

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
  # Trigger build with default configuration (uses adnyeus.yml)
  python webhook_trigger.py --token ghp_xxxxx

  # Trigger build with specific YAML definition (auto-prepends yaml-definitions/)
  python webhook_trigger.py --token ghp_xxxxx --yaml sway-bootc.yml

  # Trigger build with custom path
  python webhook_trigger.py --token ghp_xxxxx --yaml custom/my-config.yml

  # Trigger build with specific window manager
  python webhook_trigger.py --token ghp_xxxxx --wm sway

  # Trigger build with specific desktop environment
  python webhook_trigger.py --token ghp_xxxxx --de kde

  # Trigger build with local YAML file
  python webhook_trigger.py --token ghp_xxxxx --yaml /path/to/my-config.yml

  # Combine options
  python webhook_trigger.py --token ghp_xxxxx --yaml sway-bootc.yml --wm sway --distro-version 44

  # Use environment variable for token
  export GITHUB_TOKEN=ghp_xxxxx
  python webhook_trigger.py --wm sway

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
            'fedora-bootc', 'fedora-kinoite',
            'fedora-sway-atomic', 'fedora-onyx', 'fedora-budgie',
            'fedora-cinnamon', 'fedora-cosmic', 'fedora-deepin',
            'fedora-lxqt', 'fedora-mate', 'fedora-xfce',
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
        "--yaml",
        help=(
            "YAML configuration - can be a filename (e.g., 'sway-bootc.yml'), "
            "any path (e.g., 'custom/config.yml', 'yaml-definitions/sway-bootc.yml'), or local file path. "
            "If not provided, defaults to 'adnyeus.yml'"
        )
    )
    parser.add_argument(
        "--os",
        help="Operating system for auto-selection (fedora only)"
    )
    parser.add_argument(
        "--window-manager",
        "--wm",
        dest="window_manager",
        choices=['sway'],
        help="Window manager (e.g., 'sway') - can be combined with --de"
    )
    parser.add_argument(
        "--desktop-environment",
        "--de",
        dest="desktop_environment",
        choices=['kde', 'mate', 'lxqt'],
        help="Desktop environment (e.g., 'kde', 'mate', 'lxqt') - can be combined with --wm"
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

    # Handle YAML parameter - could be filename or file path
    yaml_param = args.yaml
    if yaml_param:
        # Check if it's a local file path
        from pathlib import Path
        yaml_path = Path(yaml_param)
        if yaml_path.exists() and yaml_path.is_file():
            try:
                with open(yaml_path, 'r', encoding='utf-8') as f:
                    yaml_param = f.read()

                if args.verbose:
                    print(f"Loaded YAML content from local file: {yaml_param}")
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

    if args.os:
        print(f"OS:               {args.os}")
    if args.desktop_environment:
        print(f"Desktop Env:      {args.desktop_environment}")
    if args.window_manager:
        print(f"Window Manager:   {args.window_manager}")

    if yaml_param:
        if '\n' in yaml_param:
            print(f"YAML Content:     {len(yaml_param)} bytes (from file)")
        else:
            print(f"YAML Config:      {yaml_param}")
    else:
        print("YAML Config:      auto (based on OS/DE/WM)")

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
            yaml=yaml_param,
            os=args.os,
            window_manager=args.window_manager,
            desktop_environment=args.desktop_environment,
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
