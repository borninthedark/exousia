#!/usr/bin/env python3
"""
Package Dependency Checker (Transpiler)
========================================

Fedora-focused package dependency validation system that queries the native
package manager to verify package installation and dependencies.

This acts as a "transpiler" for package management, translating package queries
on Fedora (dnf) into standardized dependency information.
"""

import json
import subprocess
from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class PackageDependency:
    """Represents a package and its dependencies."""

    name: str
    version: str | None = None
    dependencies: list[str] = field(default_factory=list)
    provides: list[str] = field(default_factory=list)
    installed: bool = False
    distro: str = ""


@dataclass
class DependencyCheckResult:
    """Result of a dependency check operation."""

    package: str
    found: bool
    installed: bool
    dependencies: list[PackageDependency] = field(default_factory=list)
    missing_deps: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    distro: str = ""


class PackageManagerInterface(ABC):
    """Abstract interface for package manager operations."""

    def __init__(self):
        self.distro_name = self.get_distro_name()

    @abstractmethod
    def get_distro_name(self) -> str:
        """Return the distribution name."""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if this package manager is available on the system."""
        pass

    @abstractmethod
    def get_package_info(self, package_name: str) -> PackageDependency | None:
        """Get information about a package."""
        pass

    @abstractmethod
    def get_dependencies(self, package_name: str, recursive: bool = False) -> list[str]:
        """Get dependencies for a package."""
        pass

    @abstractmethod
    def is_installed(self, package_name: str) -> bool:
        """Check if a package is installed."""
        pass

    @abstractmethod
    def check_dependencies_installed(self, package_name: str) -> DependencyCheckResult:
        """Check if a package and all its dependencies are installed."""
        pass

    def run_command(self, cmd: list[str], check: bool = False) -> tuple[int, str, str]:
        """Run a shell command and return (returncode, stdout, stderr)."""
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            return result.returncode, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return -1, "", "Command timed out"
        except Exception as e:
            return -1, "", str(e)


class FedoraDnfChecker(PackageManagerInterface):
    """Package dependency checker for Fedora using DNF."""

    def get_distro_name(self) -> str:
        return "fedora"

    def is_available(self) -> bool:
        """Check if dnf is available."""
        returncode, _, _ = self.run_command(["which", "dnf"])
        return returncode == 0

    def get_package_info(self, package_name: str) -> PackageDependency | None:
        """Get package info using dnf repoquery."""
        # Query package information
        returncode, stdout, stderr = self.run_command(
            [
                "dnf",
                "repoquery",
                "--quiet",
                "--queryformat",
                "%{name}|%{version}|%{provides}",
                package_name,
            ]
        )

        if returncode != 0 or not stdout.strip():
            return None

        lines = stdout.strip().split("\n")
        if not lines:
            return None

        # Parse first result
        parts = lines[0].split("|")
        name = parts[0] if len(parts) > 0 else package_name
        version = parts[1] if len(parts) > 1 else None
        provides = parts[2].split() if len(parts) > 2 else []

        # Get dependencies
        deps = self.get_dependencies(package_name, recursive=False)

        # Check if installed
        installed = self.is_installed(package_name)

        return PackageDependency(
            name=name,
            version=version,
            dependencies=deps,
            provides=provides,
            installed=installed,
            distro=self.distro_name,
        )

    def get_dependencies(self, package_name: str, recursive: bool = False) -> list[str]:
        """Get dependencies using dnf repoquery."""
        cmd = ["dnf", "repoquery", "--quiet", "--requires", package_name]

        if recursive:
            cmd.append("--recursive")

        returncode, stdout, stderr = self.run_command(cmd)

        if returncode != 0:
            return []

        # Parse dependencies, filtering out rpmlib and other special deps
        deps = []
        for line in stdout.strip().split("\n"):
            line = line.strip()
            if not line or line.startswith("rpmlib(") or line.startswith("/"):
                continue
            # Extract package name (remove version constraints)
            pkg = line.split()[0] if line else ""
            if pkg and pkg not in deps:
                deps.append(pkg)

        return deps

    def is_installed(self, package_name: str) -> bool:
        """Check if package is installed using rpm."""
        returncode, _, _ = self.run_command(["rpm", "-q", package_name])
        return returncode == 0

    def check_dependencies_installed(self, package_name: str) -> DependencyCheckResult:
        """Check if package and dependencies are installed."""
        result = DependencyCheckResult(
            package=package_name, found=False, installed=False, distro=self.distro_name
        )

        # Get package info
        pkg_info = self.get_package_info(package_name)
        if not pkg_info:
            result.errors.append(f"Package {package_name} not found in repositories")
            return result

        result.found = True
        result.installed = pkg_info.installed

        # Check each dependency
        for dep in pkg_info.dependencies:
            dep_info = self.get_package_info(dep)
            if dep_info:
                result.dependencies.append(dep_info)
                if not dep_info.installed:
                    result.missing_deps.append(dep)
            else:
                result.missing_deps.append(dep)
                result.errors.append(f"Dependency {dep} not found")

        return result


class PackageDependencyTranspiler:
    """
    Fedora-only package dependency transpiler using DNF.

    Detects and delegates to the Fedora DNF checker for package dependency
    verification.
    """

    def __init__(self, distro: str | None = None):
        """
        Initialize the transpiler.

        Args:
            distro: Force a specific distro checker. Only "fedora" is supported.
                    If None, auto-detect.
        """
        self.checkers: dict[str, PackageManagerInterface] = {
            "fedora": FedoraDnfChecker(),
        }

        if distro:
            if distro not in self.checkers:
                raise ValueError(
                    f"Unknown distro: {distro}. Supported: {list(self.checkers.keys())}"
                )
            self.checker = self.checkers[distro]
        else:
            self.checker = self._detect_distro()

    def _detect_distro(self) -> PackageManagerInterface:
        """Auto-detect the current distribution."""
        # Try to read /etc/os-release
        try:
            with open("/etc/os-release") as f:
                content = f.read().lower()
                if "fedora" in content or "rhel" in content or "centos" in content:
                    return self.checkers["fedora"]
        except FileNotFoundError:
            pass

        # Fall back to checking which package manager is available
        for checker in self.checkers.values():
            if checker.is_available():
                return checker

        raise RuntimeError("No supported package manager found")

    def get_current_distro(self) -> str:
        """Get the current distro name."""
        return self.checker.distro_name

    def check_package(self, package_name: str) -> DependencyCheckResult:
        """
        Check a package and its dependencies.

        Args:
            package_name: Name of the package to check

        Returns:
            DependencyCheckResult with package and dependency information
        """
        return self.checker.check_dependencies_installed(package_name)

    def check_packages(self, package_names: list[str]) -> dict[str, DependencyCheckResult]:
        """
        Check multiple packages.

        Args:
            package_names: List of package names to check

        Returns:
            Dictionary mapping package name to DependencyCheckResult
        """
        results = {}
        for pkg in package_names:
            results[pkg] = self.check_package(pkg)
        return results

    def verify_installation(self, package_names: list[str]) -> tuple[bool, list[str]]:
        """
        Verify that all packages in the list are installed.

        Args:
            package_names: List of package names to verify

        Returns:
            Tuple of (all_installed: bool, missing_packages: List[str])
        """
        missing = []
        for pkg in package_names:
            if not self.checker.is_installed(pkg):
                missing.append(pkg)

        return len(missing) == 0, missing


def main():
    """CLI interface for package dependency checking."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Fedora package dependency checker",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Check multiple packages
  python3 package_dependency_checker.py sway waybar

  # Force a specific distro
  python3 package_dependency_checker.py --distro fedora sway

  # Output as JSON
  python3 package_dependency_checker.py --json sway
        """,
    )

    parser.add_argument("packages", nargs="+", help="Package names to check")
    parser.add_argument(
        "--distro", choices=["fedora"], help="Force specific distro (auto-detect if not specified)"
    )
    parser.add_argument("--json", action="store_true", help="Output results as JSON")
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Only verify if packages are installed (exit 0 if all installed)",
    )

    args = parser.parse_args()

    try:
        transpiler = PackageDependencyTranspiler(distro=args.distro)

        if args.verify_only:
            all_installed, missing = transpiler.verify_installation(args.packages)
            if all_installed:
                print(f"✓ All packages installed on {transpiler.get_current_distro()}")
                return 0
            else:
                print(
                    f"✗ Missing packages on {transpiler.get_current_distro()}: {', '.join(missing)}"
                )
                return 1

        results = transpiler.check_packages(args.packages)

        if args.json:
            # Convert to JSON-serializable format
            json_results = {}
            for pkg, result in results.items():
                json_results[pkg] = {
                    "found": result.found,
                    "installed": result.installed,
                    "distro": result.distro,
                    "dependencies": [
                        {"name": dep.name, "installed": dep.installed, "version": dep.version}
                        for dep in result.dependencies
                    ],
                    "missing_deps": result.missing_deps,
                    "errors": result.errors,
                }
            print(json.dumps(json_results, indent=2))
        else:
            # Human-readable output
            print(f"Package Dependency Check ({transpiler.get_current_distro()})")
            print("=" * 70)
            for pkg, result in results.items():
                print(f"\n📦 {pkg}")
                print(f"   Found: {'✓' if result.found else '✗'}")
                print(f"   Installed: {'✓' if result.installed else '✗'}")

                if result.dependencies:
                    print(f"   Dependencies ({len(result.dependencies)}):")
                    for dep in result.dependencies[:10]:  # Show first 10
                        status = "✓" if dep.installed else "✗"
                        print(f"      {status} {dep.name}")
                    if len(result.dependencies) > 10:
                        print(f"      ... and {len(result.dependencies) - 10} more")

                if result.missing_deps:
                    print(f"   Missing: {', '.join(result.missing_deps[:5])}")

                if result.errors:
                    print(f"   Errors: {', '.join(result.errors)}")

        return 0

    except Exception as e:
        print(f"Error: {e}", file=__import__("sys").stderr)
        return 1


if __name__ == "__main__":
    exit(main())
