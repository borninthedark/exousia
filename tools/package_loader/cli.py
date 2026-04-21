import argparse
import json
import sys
from pathlib import Path

from .loader import PackageLoader


def main(argv: list[str] | None = None, loader: PackageLoader | None = None):
    """CLI entry point for package loader."""
    parser = argparse.ArgumentParser(
        description="Load and manage package definitions for Exousia builds"
    )
    parser.add_argument("--wm", help="Window manager to load")
    parser.add_argument("--de", help="Desktop environment to load")
    parser.add_argument("--list-wms", action="store_true", help="List available window managers")
    parser.add_argument(
        "--list-des", action="store_true", help="List available desktop environments"
    )
    parser.add_argument(
        "--export", action="store_true", help="Export to text files (legacy format)"
    )
    parser.add_argument("--output-dir", type=Path, help="Output directory for exported files")
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print normalized resolved package plan as JSON",
    )
    parser.add_argument(
        "--common",
        action="append",
        dest="common_bundles",
        help="Explicit common package set to include (repeatable)",
    )
    parser.add_argument(
        "--feature",
        action="append",
        dest="feature_bundles",
        help="Explicit feature package set to include (repeatable)",
    )
    parser.add_argument(
        "--common-bundle", action="append", dest="common_bundles", help=argparse.SUPPRESS
    )
    parser.add_argument(
        "--feature-bundle", action="append", dest="feature_bundles", help=argparse.SUPPRESS
    )

    args = parser.parse_args(argv if argv is not None else sys.argv[1:])

    if loader is None:
        loader = PackageLoader()

    if args.list_wms:
        wms = loader.list_available_wms()
        print("Available window managers:")
        for wm in wms:
            print(f"  - {wm}")
        return

    if args.list_des:
        des = loader.list_available_des()
        print("Available desktop environments:")
        for de in des:
            print(f"  - {de}")
        return

    if args.export:
        loader.export_to_text_files(wm=args.wm, de=args.de, output_dir=args.output_dir)
        print(f"✓ Exported package lists to {args.output_dir or 'custom-pkgs/'}")
        return

    # Default: print package list
    if args.json:
        print(
            json.dumps(
                loader.get_package_plan(
                    wm=args.wm,
                    de=args.de,
                    include_common=args.common_bundles is None,
                    common_bundles=args.common_bundles,
                    feature_bundles=args.feature_bundles,
                ),
                indent=2,
            )
        )
        return

    packages = loader.get_package_list(
        wm=args.wm,
        de=args.de,
        include_common=args.common_bundles is None,
        extras=args.feature_bundles,
    )

    print("Packages to install:")
    for pkg in packages["install"]:
        print(f"  {pkg}")

    print("\nPackages to remove:")
    for pkg in packages["remove"]:
        print(f"  {pkg}")
