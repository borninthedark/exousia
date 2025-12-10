"""
Tests for Desktop Environment and Window Manager Installation
==============================================================

Tests to verify that each DE and WM has proper package definitions and can be loaded.
"""

import pytest
from pathlib import Path
import sys

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from tools.package_loader import PackageLoader


class TestWindowManagerPackages:
    """Test window manager package definitions."""

    @pytest.fixture
    def loader(self):
        """Create package loader instance."""
        packages_dir = project_root / "packages"
        return PackageLoader(packages_dir)

    def test_sway_packages_exist(self, loader):
        """Test that Sway WM package definition exists and is valid."""
        # Check that the file exists
        sway_file = loader.wm_dir / "sway.yml"
        assert sway_file.exists(), "sway.yml package definition not found"

        # Load packages
        packages = loader.load_wm("sway")
        assert len(packages) > 0, "Sway package list is empty"

        # Check for essential Sway packages
        essential_packages = ["sway", "swaylock-effects"]
        for pkg in essential_packages:
            assert pkg in packages, f"Essential package '{pkg}' not found in Sway packages"

    def test_sway_installation_verification(self, loader):
        """Test that Sway WM can be verified after installation."""
        packages = loader.load_wm("sway")

        # Verify core components
        core_packages = ["sway", "swaylock-effects", "swayidle"]
        found_core = [pkg for pkg in core_packages if pkg in packages]
        assert len(found_core) >= 2, f"Not enough core Sway packages found: {found_core}"

        # Verify Wayland support
        wayland_packages = ["wlroots", "wayland"]
        found_wayland = [pkg for pkg in wayland_packages if any(wp in pkg for wp in packages)]
        assert len(found_wayland) > 0, "No Wayland support packages found"

    def test_hyprland_packages_exist(self, loader):
        """Test that Hyprland WM package definition exists and is valid."""
        hyprland_file = loader.wm_dir / "hyprland.yml"
        assert hyprland_file.exists(), "hyprland.yml package definition not found"

        # Load packages
        packages = loader.load_wm("hyprland")
        assert len(packages) > 0, "Hyprland package list is empty"

        # Check for essential Hyprland packages
        essential_packages = ["hyprland"]
        for pkg in essential_packages:
            assert pkg in packages, f"Essential package '{pkg}' not found in Hyprland packages"

    def test_hyprland_installation_verification(self, loader):
        """Test that Hyprland WM can be verified after installation."""
        packages = loader.load_wm("hyprland")

        # Verify core Hyprland package
        assert "hyprland" in packages, "Core hyprland package not found"

        # Verify Wayland support (check for packages containing "wayland" or "wlroots")
        found_wayland = [pkg for pkg in packages if "wayland" in pkg.lower() or "wlroots" in pkg.lower()]
        assert len(found_wayland) > 0, f"No Wayland support packages found. Packages: {packages}"


class TestDesktopEnvironmentPackages:
    """Test desktop environment package definitions."""

    @pytest.fixture
    def loader(self):
        """Create package loader instance."""
        packages_dir = project_root / "packages"
        return PackageLoader(packages_dir)

    def test_kde_packages_exist(self, loader):
        """Test that KDE DE package definition exists and is valid."""
        kde_file = loader.de_dir / "kde.yml"
        assert kde_file.exists(), "kde.yml package definition not found"

        # Load packages
        packages = loader.load_de("kde")
        assert len(packages) > 0, "KDE package list is empty"

        # Check for essential KDE packages or groups
        # Note: KDE may use groups like @kde-desktop-environment
        kde_config = loader.load_yaml(kde_file)
        groups = loader.get_groups(kde_config)

        # Either packages or groups should be present
        assert len(packages) > 0 or len(groups) > 0, \
            "No KDE packages or groups found"

    def test_kde_installation_verification(self, loader):
        """Test that KDE DE can be verified after installation."""
        kde_file = loader.de_dir / "kde.yml"
        kde_config = loader.load_yaml(kde_file)

        packages = loader.flatten_packages(kde_config)
        groups = loader.get_groups(kde_config)

        # Verify we have KDE components (either packages or groups)
        total_components = len(packages) + len(groups)
        assert total_components > 0, "No KDE components found"

        # Check for KDE-specific content
        all_content = " ".join(packages + groups).lower()
        assert "kde" in all_content or "plasma" in all_content, \
            "No KDE/Plasma specific content found"

    def test_mate_packages_exist(self, loader):
        """Test that MATE DE package definition exists and is valid."""
        mate_file = loader.de_dir / "mate.yml"
        assert mate_file.exists(), "mate.yml package definition not found"

        # Load packages
        packages = loader.load_de("mate")
        assert len(packages) > 0, "MATE package list is empty"

        # Check for essential MATE packages
        mate_config = loader.load_yaml(mate_file)
        groups = loader.get_groups(mate_config)

        # Either packages or groups should be present
        assert len(packages) > 0 or len(groups) > 0, \
            "No MATE packages or groups found"

    def test_mate_installation_verification(self, loader):
        """Test that MATE DE can be verified after installation."""
        mate_file = loader.de_dir / "mate.yml"
        mate_config = loader.load_yaml(mate_file)

        packages = loader.flatten_packages(mate_config)
        groups = loader.get_groups(mate_config)

        # Verify we have MATE components
        total_components = len(packages) + len(groups)
        assert total_components > 0, "No MATE components found"

        # Check for MATE-specific content
        all_content = " ".join(packages + groups).lower()
        assert "mate" in all_content, "No MATE specific content found"


class TestCommonPackages:
    """Test common package definitions."""

    @pytest.fixture
    def loader(self):
        """Create package loader instance."""
        packages_dir = project_root / "packages"
        return PackageLoader(packages_dir)

    def test_common_base_packages_exist(self, loader):
        """Test that common base packages exist."""
        base_file = loader.common_dir / "base.yml"
        assert base_file.exists(), "base.yml common package definition not found"

        # Load packages
        packages = loader.load_common("base")
        assert len(packages) > 0, "Common base package list is empty"

    def test_remove_packages_exist(self, loader):
        """Test that package removal list exists."""
        remove_file = loader.common_dir / "remove.yml"
        assert remove_file.exists(), "remove.yml package removal list not found"

        # Load removal packages
        packages = loader.load_remove()
        # Note: removal list can be empty, just verify it loads without error
        assert isinstance(packages, list), "Package removal list is not a list"


class TestPackageLoaderIntegration:
    """Test package loader integration with DE/WM selection."""

    @pytest.fixture
    def loader(self):
        """Create package loader instance."""
        packages_dir = project_root / "packages"
        return PackageLoader(packages_dir)

    def test_sway_wm_full_package_list(self, loader):
        """Test getting full package list for Sway WM."""
        result = loader.get_package_list(wm="sway", include_common=True)

        assert "install" in result
        assert "remove" in result
        assert "groups" in result

        assert len(result["install"]) > 0, "No install packages for Sway"
        assert isinstance(result["remove"], list), "Remove list is not a list"

    def test_hyprland_wm_full_package_list(self, loader):
        """Test getting full package list for Hyprland WM."""
        result = loader.get_package_list(wm="hyprland", include_common=True)

        assert "install" in result
        assert "remove" in result
        assert "groups" in result

        assert len(result["install"]) > 0, "No install packages for Hyprland"

    def test_kde_de_full_package_list(self, loader):
        """Test getting full package list for KDE DE."""
        result = loader.get_package_list(de="kde", include_common=True)

        assert "install" in result
        assert "remove" in result
        assert "groups" in result

        # KDE might use groups instead of individual packages
        total_components = len(result["install"]) + len(result["groups"])
        assert total_components > 0, "No packages or groups for KDE"

    def test_mate_de_full_package_list(self, loader):
        """Test getting full package list for MATE DE."""
        result = loader.get_package_list(de="mate", include_common=True)

        assert "install" in result
        assert "remove" in result
        assert "groups" in result

        # MATE might use groups instead of individual packages
        total_components = len(result["install"]) + len(result["groups"])
        assert total_components > 0, "No packages or groups for MATE"

    def test_available_wms_list(self, loader):
        """Test listing available window managers."""
        wms = loader.list_available_wms()
        assert "sway" in wms, "Sway not in available WMs"
        assert "hyprland" in wms, "Hyprland not in available WMs"

    def test_available_des_list(self, loader):
        """Test listing available desktop environments."""
        des = loader.list_available_des()
        assert "kde" in des, "KDE not in available DEs"
        assert "mate" in des, "MATE not in available DEs"


@pytest.mark.integration
class TestPackageDependencyValidation:
    """Test package dependency validation using the cross-distro transpiler."""

    @pytest.fixture
    def loader(self):
        """Create package loader instance."""
        packages_dir = project_root / "packages"
        return PackageLoader(packages_dir)

    def test_dependency_checker_import(self):
        """Test that the dependency checker can be imported."""
        try:
            from tools.package_dependency_checker import PackageDependencyTranspiler
            assert PackageDependencyTranspiler is not None
        except ImportError as e:
            pytest.fail(f"Failed to import PackageDependencyTranspiler: {e}")

    def test_dependency_checker_interface(self):
        """Test the dependency checker interface and basic functionality."""
        try:
            from tools.package_dependency_checker import (
                PackageDependencyTranspiler,
                FedoraDnfChecker,
                ArchPacmanChecker
            )

            # Test that the checkers have the required methods
            for checker_class in [FedoraDnfChecker, ArchPacmanChecker]:
                checker = checker_class()
                assert hasattr(checker, 'get_package_info')
                assert hasattr(checker, 'get_dependencies')
                assert hasattr(checker, 'is_installed')
                assert hasattr(checker, 'check_dependencies_installed')
                assert hasattr(checker, 'is_available')

        except ImportError as e:
            pytest.fail(f"Failed to import dependency checker components: {e}")

    @pytest.mark.skipif(
        not Path('/usr/bin/dnf').exists() and not Path('/usr/bin/pacman').exists(),
        reason="Requires dnf or pacman to be installed"
    )
    def test_hyprland_dependencies_validation(self, loader):
        """
        Test Hyprland dependency validation using native package manager.

        This test will query the actual package manager to verify that
        Hyprland's dependencies are correctly defined.
        """
        try:
            from tools.package_dependency_checker import PackageDependencyTranspiler

            # Skip if no supported package manager is available
            try:
                transpiler = PackageDependencyTranspiler()
            except RuntimeError:
                pytest.skip("No supported package manager found")

            # Load Hyprland packages from our definition
            packages = loader.load_wm("hyprland")
            assert "hyprland" in packages, "Hyprland not in package list"

            # Check that Hyprland package exists in repos
            result = transpiler.check_package("hyprland")

            # The package should be found in repositories
            assert result.found, f"Hyprland not found in {result.distro} repositories"

            # If we're on a system where Hyprland is available, verify it has dependencies
            if result.found and len(result.dependencies) > 0:
                # Hyprland should have Wayland-related dependencies
                dep_names = [dep.name for dep in result.dependencies]
                has_wayland_deps = any(
                    'wayland' in dep.lower() or 'wlroots' in dep.lower()
                    for dep in dep_names
                )
                assert has_wayland_deps, f"Hyprland missing Wayland dependencies on {result.distro}"

        except ImportError as e:
            pytest.skip(f"Dependency checker not available: {e}")

    @pytest.mark.skipif(
        not Path('/usr/bin/dnf').exists() and not Path('/usr/bin/pacman').exists(),
        reason="Requires dnf or pacman to be installed"
    )
    def test_sway_dependencies_validation(self, loader):
        """
        Test Sway dependency validation using native package manager.
        """
        try:
            from tools.package_dependency_checker import PackageDependencyTranspiler

            try:
                transpiler = PackageDependencyTranspiler()
            except RuntimeError:
                pytest.skip("No supported package manager found")

            # Load Sway packages
            packages = loader.load_wm("sway")
            assert "sway" in packages, "Sway not in package list"

            # Check Sway package
            result = transpiler.check_package("sway")
            assert result.found, f"Sway not found in {result.distro} repositories"

        except ImportError as e:
            pytest.skip(f"Dependency checker not available: {e}")

    def test_transpiler_distro_detection(self):
        """Test that the transpiler can detect or use forced distro."""
        try:
            from tools.package_dependency_checker import PackageDependencyTranspiler

            # Test forced distro selection
            for distro in ['fedora', 'arch']:
                transpiler = PackageDependencyTranspiler(distro=distro)
                assert transpiler.get_current_distro() == distro

        except ImportError as e:
            pytest.skip(f"Dependency checker not available: {e}")
        except RuntimeError:
            # Expected if package manager not available
            pass


class TestDistroSpecificDependencyValidation:
    """Mocked distro-specific validation covering multiple package managers."""

    @pytest.fixture
    def loader(self):
        packages_dir = project_root / "packages"
        return PackageLoader(packages_dir)

    def test_debian_checker_marks_missing_dependency(self, monkeypatch, loader):
        from tools.package_dependency_checker import PackageDependency, DebianAptChecker

        checker = DebianAptChecker()

        def fake_get_package_info(name):
            if name == "sway":
                return PackageDependency(name="sway", dependencies=["wlroots"], installed=True, distro="debian")
            if name == "wlroots":
                return PackageDependency(name="wlroots", dependencies=[], installed=False, distro="debian")
            return None

        monkeypatch.setattr(checker, "get_package_info", fake_get_package_info)

        assert "sway" in loader.load_wm("sway")
        result = checker.check_dependencies_installed("sway")

        assert result.distro == "debian"
        assert result.missing_deps == ["wlroots"]

    def test_opensuse_checker_validates_kde_group(self, monkeypatch, loader):
        from tools.package_dependency_checker import PackageDependency, OpenSUSEZypperChecker

        checker = OpenSUSEZypperChecker()

        def fake_get_package_info(name):
            if name == "plasma-desktop":
                return PackageDependency(
                    name="plasma-desktop",
                    dependencies=["plasma-workspace"],
                    installed=True,
                    distro="opensuse",
                )
            if name == "plasma-workspace":
                return PackageDependency(name="plasma-workspace", dependencies=[], installed=True, distro="opensuse")
            return None

        monkeypatch.setattr(checker, "get_package_info", fake_get_package_info)

        kde_packages = loader.load_de("kde")
        assert any("plasma" in pkg for pkg in kde_packages)
        result = checker.check_dependencies_installed("plasma-desktop")

        assert result.found is True
        assert result.missing_deps == []
        assert result.dependencies[0].name == "plasma-workspace"

    def test_gentoo_checker_captures_nested_dependencies(self, monkeypatch, loader):
        from tools.package_dependency_checker import PackageDependency, GentooPortageChecker

        checker = GentooPortageChecker()

        def fake_get_package_info(name):
            if name == "hyprland":
                return PackageDependency(
                    name="hyprland",
                    dependencies=["wayland"],
                    installed=True,
                    distro="gentoo",
                )
            if name == "wayland":
                return PackageDependency(name="wayland", dependencies=[], installed=False, distro="gentoo")
            return None

        monkeypatch.setattr(checker, "get_package_info", fake_get_package_info)

        hyprland_packages = loader.load_wm("hyprland")
        assert "hyprland" in hyprland_packages

        result = checker.check_dependencies_installed("hyprland")

        assert result.found is True
        assert "wayland" in result.missing_deps
        assert any(dep.name == "wayland" for dep in result.dependencies)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
