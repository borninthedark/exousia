#!/usr/bin/env python3
"""
Validate Installed Packages
============================

This script validates that packages from a YAML definition are actually installed
in the container. It uses the package dependency checker to verify installation
across different distros.

This is intended to be run inside the built container as part of the build workflow.
"""

import sys
import yaml
from pathlib import Path
from typing import List, Dict, Set, Optional
import argparse
import json

# Import distro mapper for image type → distro resolution
try:
    from distro_mapper import get_distro_for_image_type
except ImportError:
    # Fallback if distro_mapper not in path
    def get_distro_for_image_type(image_type: str) -> Optional[str]:
        """Fallback distro mapper."""
        if 'fedora' in image_type.lower():
            return 'fedora'
        elif 'arch' in image_type.lower():
            return 'arch'
        elif 'debian' in image_type.lower() or 'proxmox' in image_type.lower():
            return 'debian'
        elif 'ubuntu' in image_type.lower():
            return 'ubuntu'
        elif 'opensuse' in image_type.lower():
            return 'opensuse'
        elif 'gentoo' in image_type.lower():
            return 'gentoo'
        return None


def load_yaml_config(yaml_path: Path) -> Dict:
    """Load and parse YAML configuration."""
    try:
        with open(yaml_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    except Exception as e:
        print(f"Error loading YAML: {e}", file=sys.stderr)
        sys.exit(1)


def extract_packages_from_yaml(config: Dict) -> Set[str]:
    """
    Extract all package names from YAML configuration.

    Handles both direct package lists and packages from DE/WM definitions.
    """
    packages = set()

    # Look for modules in the config
    modules = config.get('modules', [])
    for module in modules:
        if not isinstance(module, dict):
            continue

        module_type = module.get('type', '')

        # Handle rpm-ostree packages
        if module_type == 'rpm-ostree':
            pkg_list = module.get('packages', [])
            if isinstance(pkg_list, list):
                packages.update(pkg_list)

        # Handle other package types
        elif module_type == 'packages':
            pkg_list = module.get('packages', [])
            if isinstance(pkg_list, list):
                packages.update(pkg_list)

    return packages


def validate_packages(packages: List[str], distro: Optional[str] = None, verbose: bool = False) -> tuple[bool, Dict]:
    """
    Validate that packages are installed.

    Returns:
        Tuple of (all_installed: bool, results: Dict)
    """
    try:
        # Import here so the script can run even if dependency checker isn't available
        from package_dependency_checker import PackageDependencyTranspiler

        transpiler = PackageDependencyTranspiler(distro=distro)

        if verbose:
            print(f"Checking packages on {transpiler.get_current_distro()}...")

        # Verify installation
        all_installed, missing = transpiler.verify_installation(packages)

        results = {
            'distro': transpiler.get_current_distro(),
            'total_packages': len(packages),
            'installed': len(packages) - len(missing),
            'missing': missing,
            'all_installed': all_installed
        }

        if verbose:
            print(f"  Total packages: {results['total_packages']}")
            print(f"  Installed: {results['installed']}")
            print(f"  Missing: {len(missing)}")

        return all_installed, results

    except ImportError:
        print("Error: package_dependency_checker not available", file=sys.stderr)
        print("Make sure tools/package_dependency_checker.py is in your path", file=sys.stderr)
        sys.exit(1)
    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def validate_de_wm_packages(de_name: Optional[str] = None, wm_name: Optional[str] = None,
                           distro: Optional[str] = None, verbose: bool = False) -> tuple[bool, Dict]:
    """
    Validate desktop environment or window manager packages.

    Returns:
        Tuple of (all_installed: bool, results: Dict)
    """
    try:
        from package_loader import PackageLoader

        # Get package directory
        script_dir = Path(__file__).parent
        packages_dir = script_dir.parent / "packages"
        loader = PackageLoader(packages_dir)

        # Load packages
        packages = []
        if de_name:
            if verbose:
                print(f"Loading packages for DE: {de_name}")
            packages = loader.load_de(de_name)
        elif wm_name:
            if verbose:
                print(f"Loading packages for WM: {wm_name}")
            packages = loader.load_wm(wm_name)
        else:
            print("Error: Must specify either --de or --wm", file=sys.stderr)
            sys.exit(1)

        if not packages:
            print(f"Error: No packages found for {'DE' if de_name else 'WM'}", file=sys.stderr)
            sys.exit(1)

        return validate_packages(packages, distro=distro, verbose=verbose)

    except Exception as e:
        print(f"Error loading packages: {e}", file=sys.stderr)
        sys.exit(1)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Validate installed packages in built container",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Validate packages from YAML config
  python3 validate_installed_packages.py --yaml adnyeus.yml

  # Validate specific DE packages
  python3 validate_installed_packages.py --de kde

  # Validate specific WM packages
  python3 validate_installed_packages.py --wm sway

  # Force specific distro and output JSON
  python3 validate_installed_packages.py --yaml adnyeus.yml --distro fedora --json

  # Verbose output
  python3 validate_installed_packages.py --wm hyprland --verbose
        """
    )

    parser.add_argument("--yaml", type=Path,
                       help="YAML configuration file to validate")
    parser.add_argument("--de", type=str,
                       help="Desktop environment name to validate")
    parser.add_argument("--wm", type=str,
                       help="Window manager name to validate")
    parser.add_argument("--image-type", type=str,
                       help="Image type (e.g., fedora-bootc, arch) - auto-maps to distro")
    parser.add_argument("--distro", choices=["fedora", "arch", "debian", "ubuntu", "opensuse", "gentoo", "freebsd"],
                       help="Force specific distro (overrides --image-type)")
    parser.add_argument("--json", action="store_true",
                       help="Output results as JSON")
    parser.add_argument("--verbose", "-v", action="store_true",
                       help="Verbose output")
    parser.add_argument("--fail-on-missing", action="store_true", default=True,
                       help="Exit with error if any packages are missing (default: true)")

    args = parser.parse_args()

    # Resolve distro from image type if provided
    distro = args.distro
    if not distro and args.image_type:
        distro = get_distro_for_image_type(args.image_type)
        if distro and args.verbose:
            print(f"Mapped image type '{args.image_type}' to distro '{distro}'")
        elif not distro:
            print(f"Warning: Unknown image type '{args.image_type}', will auto-detect distro", file=sys.stderr)

    # Validate arguments
    if not any([args.yaml, args.de, args.wm]):
        parser.error("Must specify one of: --yaml, --de, or --wm")

    # Run validation
    if args.yaml:
        if not args.yaml.exists():
            print(f"Error: YAML file not found: {args.yaml}", file=sys.stderr)
            sys.exit(1)

        if args.verbose:
            print(f"Loading configuration from {args.yaml}")

        config = load_yaml_config(args.yaml)
        packages = extract_packages_from_yaml(config)

        if not packages:
            print("Warning: No packages found in YAML configuration", file=sys.stderr)
            sys.exit(0)

        if args.verbose:
            print(f"Found {len(packages)} packages in configuration")

        all_installed, results = validate_packages(list(packages), distro=distro, verbose=args.verbose)

    else:
        all_installed, results = validate_de_wm_packages(
            de_name=args.de,
            wm_name=args.wm,
            distro=distro,
            verbose=args.verbose
        )

    # Output results
    if args.json:
        print(json.dumps(results, indent=2))
    else:
        if all_installed:
            print(f"\n✅ SUCCESS: All {results['installed']} packages are installed on {results['distro']}")
        else:
            print(f"\n❌ FAILURE: {len(results['missing'])} packages are missing on {results['distro']}")
            print("\nMissing packages:")
            for pkg in results['missing']:
                print(f"  - {pkg}")

    # Exit with appropriate code
    if args.fail_on_missing and not all_installed:
        sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()
