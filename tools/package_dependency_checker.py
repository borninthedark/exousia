#!/usr/bin/env python3
"""
Package Dependency Checker (Transpiler)
========================================

Cross-distro package dependency validation system that queries native package
managers to verify package installation and dependencies.

This acts as a "transpiler" for package management, translating package queries
across different distros (Fedora/dnf, Arch/pacman) and returning standardized
dependency information.
"""

import subprocess
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Set, Optional
from pathlib import Path
import shlex


@dataclass
class PackageDependency:
    """Represents a package and its dependencies."""
    name: str
    version: Optional[str] = None
    dependencies: List[str] = field(default_factory=list)
    provides: List[str] = field(default_factory=list)
    installed: bool = False
    distro: str = ""


@dataclass
class DependencyCheckResult:
    """Result of a dependency check operation."""
    package: str
    found: bool
    installed: bool
    dependencies: List[PackageDependency] = field(default_factory=list)
    missing_deps: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
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
    def get_package_info(self, package_name: str) -> Optional[PackageDependency]:
        """Get information about a package."""
        pass

    @abstractmethod
    def get_dependencies(self, package_name: str, recursive: bool = False) -> List[str]:
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

    def run_command(self, cmd: List[str], check: bool = False) -> tuple[int, str, str]:
        """Run a shell command and return (returncode, stdout, stderr)."""
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )
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

    def get_package_info(self, package_name: str) -> Optional[PackageDependency]:
        """Get package info using dnf repoquery."""
        # Query package information
        returncode, stdout, stderr = self.run_command([
            "dnf", "repoquery", "--quiet",
            "--queryformat", "%{name}|%{version}|%{provides}",
            package_name
        ])

        if returncode != 0 or not stdout.strip():
            return None

        lines = stdout.strip().split('\n')
        if not lines:
            return None

        # Parse first result
        parts = lines[0].split('|')
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
            distro=self.distro_name
        )

    def get_dependencies(self, package_name: str, recursive: bool = False) -> List[str]:
        """Get dependencies using dnf repoquery."""
        cmd = ["dnf", "repoquery", "--quiet", "--requires", package_name]

        if recursive:
            cmd.append("--recursive")

        returncode, stdout, stderr = self.run_command(cmd)

        if returncode != 0:
            return []

        # Parse dependencies, filtering out rpmlib and other special deps
        deps = []
        for line in stdout.strip().split('\n'):
            line = line.strip()
            if not line or line.startswith('rpmlib(') or line.startswith('/'):
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
            package=package_name,
            found=False,
            installed=False,
            distro=self.distro_name
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


class ArchPacmanChecker(PackageManagerInterface):
    """Package dependency checker for Arch Linux using pacman."""

    def get_distro_name(self) -> str:
        return "arch"

    def is_available(self) -> bool:
        """Check if pacman is available."""
        returncode, _, _ = self.run_command(["which", "pacman"])
        return returncode == 0

    def get_package_info(self, package_name: str) -> Optional[PackageDependency]:
        """Get package info using pacman -Si."""
        # Try sync db first
        returncode, stdout, stderr = self.run_command([
            "pacman", "-Si", package_name
        ])

        if returncode != 0:
            # Try query local db
            returncode, stdout, stderr = self.run_command([
                "pacman", "-Qi", package_name
            ])
            if returncode != 0:
                return None

        # Parse pacman output
        name = package_name
        version = None
        deps = []
        provides = []
        installed = False

        for line in stdout.split('\n'):
            line = line.strip()
            if line.startswith('Name'):
                name = line.split(':', 1)[1].strip()
            elif line.startswith('Version'):
                version = line.split(':', 1)[1].strip()
            elif line.startswith('Depends On'):
                deps_str = line.split(':', 1)[1].strip()
                if deps_str != 'None':
                    # Remove version constraints
                    deps = [d.split('>=')[0].split('=')[0].split('<')[0].strip()
                           for d in deps_str.split()]
            elif line.startswith('Provides'):
                provides_str = line.split(':', 1)[1].strip()
                if provides_str != 'None':
                    provides = [p.strip() for p in provides_str.split()]

        # Check if installed
        installed = self.is_installed(package_name)

        return PackageDependency(
            name=name,
            version=version,
            dependencies=deps,
            provides=provides,
            installed=installed,
            distro=self.distro_name
        )

    def get_dependencies(self, package_name: str, recursive: bool = False) -> List[str]:
        """Get dependencies using pacman."""
        if recursive:
            # Use pactree for recursive deps
            returncode, stdout, stderr = self.run_command([
                "pactree", "-u", package_name
            ])
            if returncode == 0:
                deps = []
                for line in stdout.split('\n'):
                    line = line.strip()
                    if line and line != package_name:
                        # Remove tree characters and extract package name
                        pkg = line.replace('├─', '').replace('└─', '').replace('│', '').strip()
                        if pkg and pkg not in deps:
                            deps.append(pkg)
                return deps

        # Non-recursive: use pacman -Si
        pkg_info = self.get_package_info(package_name)
        return pkg_info.dependencies if pkg_info else []

    def is_installed(self, package_name: str) -> bool:
        """Check if package is installed."""
        returncode, _, _ = self.run_command(["pacman", "-Q", package_name])
        return returncode == 0

    def check_dependencies_installed(self, package_name: str) -> DependencyCheckResult:
        """Check if package and dependencies are installed."""
        result = DependencyCheckResult(
            package=package_name,
            found=False,
            installed=False,
            distro=self.distro_name
        )

        # Get package info
        pkg_info = self.get_package_info(package_name)
        if not pkg_info:
            result.errors.append(f"Package {package_name} not found")
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


class DebianAptChecker(PackageManagerInterface):
    """Package dependency checker for Debian/Ubuntu using APT."""

    def get_distro_name(self) -> str:
        return "debian"

    def is_available(self) -> bool:
        """Check if apt is available."""
        returncode, _, _ = self.run_command(["which", "apt-cache"])
        return returncode == 0

    def get_package_info(self, package_name: str) -> Optional[PackageDependency]:
        """Get package info using apt-cache."""
        # Use apt-cache show for package information
        returncode, stdout, stderr = self.run_command([
            "apt-cache", "show", package_name
        ])

        if returncode != 0 or not stdout.strip():
            return None

        # Parse apt-cache output
        name = package_name
        version = None
        deps = []
        provides = []

        for line in stdout.split('\n'):
            line = line.strip()
            if line.startswith('Package:'):
                name = line.split(':', 1)[1].strip()
            elif line.startswith('Version:'):
                version = line.split(':', 1)[1].strip()
            elif line.startswith('Depends:'):
                deps_str = line.split(':', 1)[1].strip()
                # Parse dependencies (format: pkg1 (>= version), pkg2 | pkg3)
                for dep_group in deps_str.split(','):
                    # Take first alternative if there are pipes
                    first_alt = dep_group.split('|')[0].strip()
                    # Remove version constraints
                    pkg = first_alt.split('(')[0].strip()
                    if pkg and pkg not in deps:
                        deps.append(pkg)
            elif line.startswith('Provides:'):
                provides_str = line.split(':', 1)[1].strip()
                provides = [p.strip() for p in provides_str.split(',')]

        # Check if installed
        installed = self.is_installed(package_name)

        return PackageDependency(
            name=name,
            version=version,
            dependencies=deps,
            provides=provides,
            installed=installed,
            distro=self.distro_name
        )

    def get_dependencies(self, package_name: str, recursive: bool = False) -> List[str]:
        """Get dependencies using apt-cache."""
        if recursive:
            # Use apt-rdepends for recursive
            returncode, stdout, stderr = self.run_command([
                "apt-cache", "depends", "--recurse", "--no-recommends",
                "--no-suggests", "--no-conflicts", "--no-breaks",
                "--no-replaces", "--no-enhances", package_name
            ])
        else:
            returncode, stdout, stderr = self.run_command([
                "apt-cache", "depends", "--no-recommends", "--no-suggests",
                package_name
            ])

        if returncode != 0:
            return []

        deps = []
        for line in stdout.split('\n'):
            line = line.strip()
            if line.startswith('Depends:'):
                dep = line.split(':', 1)[1].strip()
                # Remove version and alternatives
                dep = dep.split('|')[0].split('(')[0].strip()
                if dep and dep not in deps:
                    deps.append(dep)

        return deps

    def is_installed(self, package_name: str) -> bool:
        """Check if package is installed using dpkg."""
        returncode, stdout, _ = self.run_command([
            "dpkg-query", "-W", "-f=${Status}", package_name
        ])
        return returncode == 0 and "install ok installed" in stdout

    def check_dependencies_installed(self, package_name: str) -> DependencyCheckResult:
        """Check if package and dependencies are installed."""
        result = DependencyCheckResult(
            package=package_name,
            found=False,
            installed=False,
            distro=self.distro_name
        )

        # Get package info
        pkg_info = self.get_package_info(package_name)
        if not pkg_info:
            result.errors.append(f"Package {package_name} not found")
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

        return result


class OpenSUSEZypperChecker(PackageManagerInterface):
    """Package dependency checker for OpenSUSE using Zypper."""

    def get_distro_name(self) -> str:
        return "opensuse"

    def is_available(self) -> bool:
        """Check if zypper is available."""
        returncode, _, _ = self.run_command(["which", "zypper"])
        return returncode == 0

    def get_package_info(self, package_name: str) -> Optional[PackageDependency]:
        """Get package info using zypper."""
        returncode, stdout, stderr = self.run_command([
            "zypper", "--non-interactive", "info", package_name
        ])

        if returncode != 0 or not stdout.strip():
            return None

        # Parse zypper output
        name = package_name
        version = None
        deps = []
        provides = []

        for line in stdout.split('\n'):
            line = line.strip()
            if line.startswith('Name'):
                name = line.split(':', 1)[1].strip()
            elif line.startswith('Version'):
                version = line.split(':', 1)[1].strip()
            elif line.startswith('Requires'):
                deps_str = line.split(':', 1)[1].strip()
                for dep in deps_str.split():
                    dep = dep.split('>=')[0].split('=')[0].strip()
                    if dep and dep not in deps and not dep.startswith('rpmlib'):
                        deps.append(dep)

        # Check if installed
        installed = self.is_installed(package_name)

        return PackageDependency(
            name=name,
            version=version,
            dependencies=deps,
            provides=provides,
            installed=installed,
            distro=self.distro_name
        )

    def get_dependencies(self, package_name: str, recursive: bool = False) -> List[str]:
        """Get dependencies using zypper."""
        pkg_info = self.get_package_info(package_name)
        return pkg_info.dependencies if pkg_info else []

    def is_installed(self, package_name: str) -> bool:
        """Check if package is installed."""
        returncode, stdout, _ = self.run_command([
            "rpm", "-q", package_name
        ])
        return returncode == 0

    def check_dependencies_installed(self, package_name: str) -> DependencyCheckResult:
        """Check if package and dependencies are installed."""
        result = DependencyCheckResult(
            package=package_name,
            found=False,
            installed=False,
            distro=self.distro_name
        )

        pkg_info = self.get_package_info(package_name)
        if not pkg_info:
            result.errors.append(f"Package {package_name} not found")
            return result

        result.found = True
        result.installed = pkg_info.installed

        for dep in pkg_info.dependencies:
            dep_info = self.get_package_info(dep)
            if dep_info:
                result.dependencies.append(dep_info)
                if not dep_info.installed:
                    result.missing_deps.append(dep)
            else:
                result.missing_deps.append(dep)

        return result


class GentooPortageChecker(PackageManagerInterface):
    """Package dependency checker for Gentoo using Portage (emerge)."""

    def get_distro_name(self) -> str:
        return "gentoo"

    def is_available(self) -> bool:
        """Check if emerge is available."""
        returncode, _, _ = self.run_command(["which", "emerge"])
        return returncode == 0

    def get_package_info(self, package_name: str) -> Optional[PackageDependency]:
        """Get package info using equery."""
        # Try to find the full package atom
        returncode, stdout, stderr = self.run_command([
            "equery", "list", "-F", "$cp", package_name
        ])

        if returncode != 0 or not stdout.strip():
            return None

        full_name = stdout.strip().split('\n')[0]

        # Get dependencies
        returncode, stdout, stderr = self.run_command([
            "equery", "depends", full_name
        ])

        deps = []
        if returncode == 0:
            for line in stdout.split('\n'):
                line = line.strip()
                if line and not line.startswith('['):
                    deps.append(line)

        # Check if installed
        installed = self.is_installed(package_name)

        return PackageDependency(
            name=full_name,
            version=None,
            dependencies=deps,
            provides=[],
            installed=installed,
            distro=self.distro_name
        )

    def get_dependencies(self, package_name: str, recursive: bool = False) -> List[str]:
        """Get dependencies using equery."""
        pkg_info = self.get_package_info(package_name)
        return pkg_info.dependencies if pkg_info else []

    def is_installed(self, package_name: str) -> bool:
        """Check if package is installed."""
        returncode, _, _ = self.run_command([
            "equery", "list", package_name
        ])
        return returncode == 0

    def check_dependencies_installed(self, package_name: str) -> DependencyCheckResult:
        """Check if package and dependencies are installed."""
        result = DependencyCheckResult(
            package=package_name,
            found=False,
            installed=False,
            distro=self.distro_name
        )

        pkg_info = self.get_package_info(package_name)
        if not pkg_info:
            result.errors.append(f"Package {package_name} not found")
            return result

        result.found = True
        result.installed = pkg_info.installed

        for dep in pkg_info.dependencies:
            dep_info = self.get_package_info(dep)
            if dep_info:
                result.dependencies.append(dep_info)
                if not dep_info.installed:
                    result.missing_deps.append(dep)
            else:
                result.missing_deps.append(dep)

        return result


class FreeBSDPkgChecker(PackageManagerInterface):
    """Package dependency checker for FreeBSD using pkg."""

    def get_distro_name(self) -> str:
        return "freebsd"

    def is_available(self) -> bool:
        """Check if pkg is available."""
        returncode, _, _ = self.run_command(["which", "pkg"])
        return returncode == 0

    def get_package_info(self, package_name: str) -> Optional[PackageDependency]:
        """Get package info using pkg."""
        returncode, stdout, stderr = self.run_command([
            "pkg", "info", package_name
        ])

        if returncode != 0 or not stdout.strip():
            return None

        # Parse pkg output
        name = package_name
        version = None
        deps = []

        for line in stdout.split('\n'):
            line = line.strip()
            if line.startswith('Name'):
                name = line.split(':', 1)[1].strip()
            elif line.startswith('Version'):
                version = line.split(':', 1)[1].strip()

        # Get dependencies separately
        returncode, stdout, stderr = self.run_command([
            "pkg", "info", "-d", package_name
        ])

        if returncode == 0:
            in_deps_section = False
            for line in stdout.split('\n'):
                line = line.strip()
                if 'depends on:' in line.lower():
                    in_deps_section = True
                    continue
                if in_deps_section and line:
                    # Extract package name (before version)
                    dep = line.split('-')[0]
                    if dep and dep not in deps:
                        deps.append(dep)

        # Check if installed
        installed = self.is_installed(package_name)

        return PackageDependency(
            name=name,
            version=version,
            dependencies=deps,
            provides=[],
            installed=installed,
            distro=self.distro_name
        )

    def get_dependencies(self, package_name: str, recursive: bool = False) -> List[str]:
        """Get dependencies using pkg."""
        pkg_info = self.get_package_info(package_name)
        return pkg_info.dependencies if pkg_info else []

    def is_installed(self, package_name: str) -> bool:
        """Check if package is installed."""
        returncode, _, _ = self.run_command([
            "pkg", "info", package_name
        ])
        return returncode == 0

    def check_dependencies_installed(self, package_name: str) -> DependencyCheckResult:
        """Check if package and dependencies are installed."""
        result = DependencyCheckResult(
            package=package_name,
            found=False,
            installed=False,
            distro=self.distro_name
        )

        pkg_info = self.get_package_info(package_name)
        if not pkg_info:
            result.errors.append(f"Package {package_name} not found")
            return result

        result.found = True
        result.installed = pkg_info.installed

        for dep in pkg_info.dependencies:
            dep_info = self.get_package_info(dep)
            if dep_info:
                result.dependencies.append(dep_info)
                if not dep_info.installed:
                    result.missing_deps.append(dep)
            else:
                result.missing_deps.append(dep)

        return result


class PackageDependencyTranspiler:
    """
    Main transpiler class that detects the distro and delegates to appropriate checker.

    This acts as a unified interface for package dependency checking across distros.
    """

    def __init__(self, distro: Optional[str] = None):
        """
        Initialize the transpiler.

        Args:
            distro: Force a specific distro checker (fedora, arch). If None, auto-detect.
        """
        self.checkers: Dict[str, PackageManagerInterface] = {
            'fedora': FedoraDnfChecker(),
            'arch': ArchPacmanChecker(),
            'debian': DebianAptChecker(),
            'ubuntu': DebianAptChecker(),  # Ubuntu uses apt too
            'opensuse': OpenSUSEZypperChecker(),
            'gentoo': GentooPortageChecker(),
            'freebsd': FreeBSDPkgChecker(),
        }

        if distro:
            if distro not in self.checkers:
                raise ValueError(f"Unknown distro: {distro}. Supported: {list(self.checkers.keys())}")
            self.checker = self.checkers[distro]
        else:
            self.checker = self._detect_distro()

    def _detect_distro(self) -> PackageManagerInterface:
        """Auto-detect the current distribution."""
        # Try to read /etc/os-release
        try:
            with open('/etc/os-release', 'r') as f:
                content = f.read().lower()
                if 'fedora' in content or 'rhel' in content or 'centos' in content:
                    return self.checkers['fedora']
                elif 'arch' in content:
                    return self.checkers['arch']
                elif 'debian' in content:
                    return self.checkers['debian']
                elif 'ubuntu' in content:
                    return self.checkers['ubuntu']
                elif 'opensuse' in content or 'suse' in content:
                    return self.checkers['opensuse']
                elif 'gentoo' in content:
                    return self.checkers['gentoo']
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

    def check_packages(self, package_names: List[str]) -> Dict[str, DependencyCheckResult]:
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

    def verify_installation(self, package_names: List[str]) -> tuple[bool, List[str]]:
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
        description="Cross-distro package dependency checker",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Check multiple packages
  python3 package_dependency_checker.py sway waybar

  # Force a specific distro
  python3 package_dependency_checker.py --distro fedora sway

  # Output as JSON
  python3 package_dependency_checker.py --json sway
        """
    )

    parser.add_argument("packages", nargs="+", help="Package names to check")
    parser.add_argument("--distro", choices=["fedora", "arch", "debian", "ubuntu", "opensuse", "gentoo", "freebsd"],
                       help="Force specific distro (auto-detect if not specified)")
    parser.add_argument("--json", action="store_true",
                       help="Output results as JSON")
    parser.add_argument("--verify-only", action="store_true",
                       help="Only verify if packages are installed (exit 0 if all installed)")

    args = parser.parse_args()

    try:
        transpiler = PackageDependencyTranspiler(distro=args.distro)

        if args.verify_only:
            all_installed, missing = transpiler.verify_installation(args.packages)
            if all_installed:
                print(f"✓ All packages installed on {transpiler.get_current_distro()}")
                return 0
            else:
                print(f"✗ Missing packages on {transpiler.get_current_distro()}: {', '.join(missing)}")
                return 1

        results = transpiler.check_packages(args.packages)

        if args.json:
            # Convert to JSON-serializable format
            json_results = {}
            for pkg, result in results.items():
                json_results[pkg] = {
                    'found': result.found,
                    'installed': result.installed,
                    'distro': result.distro,
                    'dependencies': [
                        {
                            'name': dep.name,
                            'installed': dep.installed,
                            'version': dep.version
                        } for dep in result.dependencies
                    ],
                    'missing_deps': result.missing_deps,
                    'errors': result.errors
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
                        status = '✓' if dep.installed else '✗'
                        print(f"      {status} {dep.name}")
                    if len(result.dependencies) > 10:
                        print(f"      ... and {len(result.dependencies) - 10} more")

                if result.missing_deps:
                    print(f"   Missing: {', '.join(result.missing_deps[:5])}")

                if result.errors:
                    print(f"   Errors: {', '.join(result.errors)}")

        return 0

    except Exception as e:
        print(f"Error: {e}", file=__import__('sys').stderr)
        return 1


if __name__ == "__main__":
    exit(main())
