#!/usr/bin/env python3
"""
COPR Repository Manager
=======================

Manages Fedora COPR repositories for package installations.
Automatically aligns repo URLs with the Fedora version being built.
"""

from pathlib import Path
from typing import List, Dict, Optional
import subprocess


# COPR repositories needed for specific packages
COPR_REPOS = {
    'hyprland': {
        'owner': 'solopasha',
        'repo': 'hyprland',
        'packages': ['hyprland', 'hyprlock', 'hypridle', 'hyprpaper', 'hyprsunset', 'hyprpolkitagent'],
        'description': 'Hyprland compositor and utilities'
    },
    'swaync': {
        'owner': 'erikreider',
        'repo': 'SwayNotificationCenter',
        'packages': ['swaync'],
        'description': 'Sway Notification Center'
    },
    'nwg-shell': {
        'owner': 'tofik',
        'repo': 'nwg-shell',
        'packages': ['nwg-displays', 'nwg-look'],
        'description': 'nwg-shell utilities for Wayland'
    },
    'wallust': {
        'owner': 'errornointernet',
        'repo': 'packages',
        'packages': ['wallust'],
        'description': 'Wallpaper color scheme generator'
    },
}


def get_fedora_version() -> Optional[str]:
    """
    Get the current Fedora version.

    Returns:
        Version string (e.g., "43", "42") or None if not Fedora
    """
    try:
        with open('/etc/os-release', 'r') as f:
            for line in f:
                if line.startswith('VERSION_ID='):
                    version = line.split('=')[1].strip().strip('"')
                    return version
    except FileNotFoundError:
        pass

    return None


def get_copr_repo_url(owner: str, repo: str, fedora_version: str) -> str:
    """
    Generate COPR repo file URL for a specific Fedora version.

    Args:
        owner: COPR repo owner
        repo: COPR repo name
        fedora_version: Fedora version (e.g., "43")

    Returns:
        URL to the .repo file
    """
    return f"https://copr.fedorainfracloud.org/coprs/{owner}/{repo}/repo/fedora-{fedora_version}/{owner}-{repo}-fedora-{fedora_version}.repo"


def get_copr_repo_name(owner: str, repo: str) -> str:
    """
    Get the COPR repo name as it appears in dnf.

    Args:
        owner: COPR repo owner
        repo: COPR repo name

    Returns:
        Repo name for dnf
    """
    return f"copr:copr.fedorainfracloud.org:{owner}:{repo}"


def is_copr_enabled(owner: str, repo: str) -> bool:
    """
    Check if a COPR repo is already enabled.

    Args:
        owner: COPR repo owner
        repo: COPR repo name

    Returns:
        True if repo is enabled
    """
    try:
        result = subprocess.run(
            ['dnf', 'repolist', '--enabled'],
            capture_output=True,
            text=True,
            timeout=10
        )
        repo_name = get_copr_repo_name(owner, repo)
        return repo_name in result.stdout
    except Exception:
        return False


def enable_copr_repo(owner: str, repo: str, fedora_version: Optional[str] = None) -> tuple[bool, str]:
    """
    Enable a COPR repository using dnf copr enable.

    Args:
        owner: COPR repo owner
        repo: COPR repo name
        fedora_version: Fedora version (for reporting only, dnf uses $releasever)

    Returns:
        Tuple of (success: bool, message: str)
    """
    if not fedora_version:
        fedora_version = get_fedora_version()

    # Check if already enabled
    if is_copr_enabled(owner, repo):
        return True, f"COPR repo {owner}/{repo} already enabled"

    try:
        # Use dnf copr enable - it handles $releasever automatically
        result = subprocess.run(
            ['dnf', 'copr', 'enable', '-y', f'{owner}/{repo}'],
            capture_output=True,
            text=True,
            timeout=60
        )

        if result.returncode != 0:
            return False, f"Failed to enable COPR {owner}/{repo}: {result.stderr}"

        version_info = f" (Fedora {fedora_version})" if fedora_version else ""
        return True, f"COPR repo {owner}/{repo} enabled{version_info}"

    except Exception as e:
        return False, f"Error enabling COPR repo: {e}"


def get_required_coprs_for_packages(packages: List[str]) -> List[Dict]:
    """
    Get list of COPR repos needed for a set of packages.

    Args:
        packages: List of package names

    Returns:
        List of COPR repo info dicts
    """
    required_coprs = []
    seen = set()

    for pkg in packages:
        for copr_name, copr_info in COPR_REPOS.items():
            if pkg in copr_info['packages']:
                key = f"{copr_info['owner']}/{copr_info['repo']}"
                if key not in seen:
                    required_coprs.append({
                        'name': copr_name,
                        'owner': copr_info['owner'],
                        'repo': copr_info['repo'],
                        'description': copr_info['description']
                    })
                    seen.add(key)

    return required_coprs


def setup_coprs_for_packages(packages: List[str], fedora_version: Optional[str] = None,
                            dry_run: bool = False) -> Dict:
    """
    Setup all required COPR repos for a list of packages.

    Args:
        packages: List of package names
        fedora_version: Fedora version (auto-detect if None)
        dry_run: If True, don't actually enable repos

    Returns:
        Dict with results: {'success': bool, 'enabled': [], 'failed': [], 'messages': []}
    """
    if not fedora_version:
        fedora_version = get_fedora_version()

    result = {
        'success': True,
        'fedora_version': fedora_version,
        'enabled': [],
        'failed': [],
        'skipped': [],
        'messages': []
    }

    if not fedora_version:
        result['success'] = False
        result['messages'].append("Could not determine Fedora version")
        return result

    required_coprs = get_required_coprs_for_packages(packages)

    if not required_coprs:
        result['messages'].append("No COPR repos required for these packages")
        return result

    result['messages'].append(f"Found {len(required_coprs)} COPR repo(s) needed")

    for copr in required_coprs:
        owner = copr['owner']
        repo = copr['repo']

        if dry_run:
            result['messages'].append(f"[DRY RUN] Would enable {owner}/{repo}")
            result['skipped'].append(f"{owner}/{repo}")
            continue

        success, message = enable_copr_repo(owner, repo, fedora_version)
        result['messages'].append(message)

        if success:
            result['enabled'].append(f"{owner}/{repo}")
        else:
            result['failed'].append(f"{owner}/{repo}")
            result['success'] = False

    return result


def main():
    """CLI for COPR repository management."""
    import argparse
    import json

    parser = argparse.ArgumentParser(
        description="Manage Fedora COPR repositories for package installations",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Check Fedora version
  python3 copr_manager.py --check-version

  # List COPR repos needed for Hyprland
  python3 copr_manager.py --packages hyprland hyprlock hypridle

  # Enable COPR repos for packages
  sudo python3 copr_manager.py --packages hyprland swaync --enable

  # Enable specific COPR
  sudo python3 copr_manager.py --enable-copr solopasha hyprland

  # Dry run (don't actually enable)
  python3 copr_manager.py --packages hyprland --enable --dry-run
        """
    )

    parser.add_argument('--check-version', action='store_true',
                       help='Check current Fedora version')
    parser.add_argument('--packages', nargs='+',
                       help='Package names to check COPR requirements')
    parser.add_argument('--enable', action='store_true',
                       help='Enable required COPR repos (requires root)')
    parser.add_argument('--enable-copr', nargs=2, metavar=('OWNER', 'REPO'),
                       help='Enable specific COPR repo (requires root)')
    parser.add_argument('--fedora-version', type=str,
                       help='Override Fedora version detection')
    parser.add_argument('--dry-run', action='store_true',
                       help='Show what would be done without doing it')
    parser.add_argument('--json', action='store_true',
                       help='Output as JSON')

    args = parser.parse_args()

    if args.check_version:
        version = args.fedora_version or get_fedora_version()
        if args.json:
            print(json.dumps({'fedora_version': version}))
        else:
            if version:
                print(f"Fedora version: {version}")
            else:
                print("Not running on Fedora or could not detect version")
        return 0

    if args.enable_copr:
        owner, repo = args.enable_copr
        if args.dry_run:
            print(f"[DRY RUN] Would enable COPR repo: {owner}/{repo}")
            return 0

        success, message = enable_copr_repo(owner, repo, args.fedora_version)
        print(message)
        return 0 if success else 1

    if args.packages:
        required_coprs = get_required_coprs_for_packages(args.packages)

        if args.json and not args.enable:
            print(json.dumps({
                'packages': args.packages,
                'required_coprs': required_coprs,
                'fedora_version': args.fedora_version or get_fedora_version()
            }, indent=2))
            return 0

        if not required_coprs:
            print("No COPR repos required for specified packages")
            return 0

        if not args.enable:
            print(f"COPR repos needed for {len(args.packages)} package(s):")
            for copr in required_coprs:
                print(f"  - {copr['owner']}/{copr['repo']}: {copr['description']}")
            print("\nUse --enable to enable these repos (requires root)")
            return 0

        # Enable repos
        result = setup_coprs_for_packages(args.packages, args.fedora_version, args.dry_run)

        if args.json:
            print(json.dumps(result, indent=2))
        else:
            for msg in result['messages']:
                print(msg)

        return 0 if result['success'] else 1

    parser.print_help()
    return 1


if __name__ == '__main__':
    exit(main())
