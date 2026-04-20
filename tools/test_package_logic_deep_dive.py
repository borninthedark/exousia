#!/usr/bin/env python3
"""
Tests specifically designed to cover previously uncovered code branches.
"""

import importlib.util
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add tools directory to path
tools_dir = Path(__file__).parent
sys.path.insert(0, str(tools_dir))

import generator.cli as yaml_to_containerfile  # noqa: E402
import package_dependency_checker  # noqa: E402
from package_loader import PackageLoader, PackageValidationError  # noqa: E402


def load_hyphenated_module(name: str, path: Path):
    """Load a hyphenated legacy module path for compatibility tests."""

    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load module from {path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# --- package_dependency_checker.py coverage ---


def test_pdc_detect_distro_failure(monkeypatch):
    """Test _detect_distro when no supported manager is found."""
    monkeypatch.setattr(
        "builtins.open", lambda *a, **kw: (_ for _ in ()).throw(FileNotFoundError())
    )

    with patch("package_dependency_checker.FedoraDnfChecker") as mock_fedora:
        mock_fedora.return_value.is_available.return_value = False
        with pytest.raises(RuntimeError, match="No supported package manager found"):
            package_dependency_checker.PackageDependencyTranspiler()


def test_pdc_main_verify_only_success(monkeypatch, capsys):
    """Test main() with --verify-only and all packages installed."""
    monkeypatch.setattr(sys, "argv", ["prog", "--verify-only", "--distro", "fedora", "pkg1"])

    transpiler_mock = MagicMock()
    transpiler_mock.verify_installation.return_value = (True, [])
    transpiler_mock.get_current_distro.return_value = "fedora"

    with patch(
        "package_dependency_checker.PackageDependencyTranspiler", return_value=transpiler_mock
    ):
        rc = package_dependency_checker.main()
        assert rc == 0
        assert "All packages installed" in capsys.readouterr().out


def test_pdc_main_verify_only_failure(monkeypatch, capsys):
    """Test main() with --verify-only and missing packages."""
    monkeypatch.setattr(sys, "argv", ["prog", "--verify-only", "pkg1"])

    transpiler_mock = MagicMock()
    transpiler_mock.verify_installation.return_value = (False, ["pkg1"])
    transpiler_mock.get_current_distro.return_value = "fedora"

    with patch(
        "package_dependency_checker.PackageDependencyTranspiler", return_value=transpiler_mock
    ):
        rc = package_dependency_checker.main()
        assert rc == 1
        assert "Missing packages" in capsys.readouterr().out


def test_pdc_main_json_output(monkeypatch, capsys):
    """Test main() with --json output."""
    monkeypatch.setattr(sys, "argv", ["prog", "--json", "pkg1"])

    result = package_dependency_checker.DependencyCheckResult(
        "pkg1", found=True, installed=True, distro="fedora"
    )
    dep = package_dependency_checker.PackageDependency("dep1", installed=True, version="1.0")
    result.dependencies = [dep]

    transpiler_mock = MagicMock()
    transpiler_mock.check_packages.return_value = {"pkg1": result}

    with patch(
        "package_dependency_checker.PackageDependencyTranspiler", return_value=transpiler_mock
    ):
        rc = package_dependency_checker.main()
        assert rc == 0
        output = json.loads(capsys.readouterr().out)
        assert "pkg1" in output
        assert output["pkg1"]["found"] is True


def test_pdc_main_error_handling(monkeypatch, capsys):
    """Test main() exception handling."""
    monkeypatch.setattr(sys, "argv", ["prog", "pkg1"])

    with patch(
        "package_dependency_checker.PackageDependencyTranspiler",
        side_effect=Exception("Test Error"),
    ):
        rc = package_dependency_checker.main()
        assert rc == 1
        assert "Error: Test Error" in capsys.readouterr().err


# --- yaml-to-containerfile.py coverage ---


def test_ytc_determine_base_image_errors():
    """Test error conditions in determine_base_image."""
    # Missing version
    with pytest.raises(ValueError, match="version must be specified"):
        yaml_to_containerfile.determine_base_image({}, "fedora-sway-atomic", "")


def test_ytc_evaluate_condition_complex():
    """Test complex conditions in _evaluate_condition."""
    context = yaml_to_containerfile.BuildContext(
        image_type="fedora-bootc",
        fedora_version="43",
        enable_plymouth=True,
        use_upstream_sway_config=False,
        base_image="test",
        distro="fedora",
    )
    generator = yaml_to_containerfile.ContainerfileGenerator({}, context)

    assert generator._evaluate_condition('distro == "fedora" && enable_plymouth == true') is True
    assert generator._evaluate_condition('distro == "ubuntu" || enable_plymouth == true') is True
    assert generator._evaluate_condition('distro == "fedora" && enable_plymouth == false') is False


def test_ytc_main_validate_only(monkeypatch, tmp_path, capsys):
    """Test main() with --validate flag."""
    cfg_file = tmp_path / "test.yml"
    cfg_file.write_text("name: test\ndescription: testing\nmodules: []")

    monkeypatch.setattr(sys, "argv", ["prog", "-c", str(cfg_file), "--validate"])

    with pytest.raises(SystemExit) as exc:
        yaml_to_containerfile.main()
    assert exc.value.code == 0
    assert "Configuration is valid" in capsys.readouterr().out


def test_ytc_main_invalid_config(monkeypatch, tmp_path):
    """Test main() with invalid configuration."""
    cfg_file = tmp_path / "test.yml"
    cfg_file.write_text("invalid: [")  # Bad YAML

    monkeypatch.setattr(sys, "argv", ["prog", "-c", str(cfg_file)])

    with pytest.raises(SystemExit) as exc:
        yaml_to_containerfile.main()
    assert exc.value.code == 1


def test_ytc_main_verbose_and_output(monkeypatch, tmp_path, capsys):
    """Test main() with verbose output and resolved package plan."""
    cfg_file = tmp_path / "test.yml"
    cfg_file.write_text("name: test\ndescription: testing\nimage-type: fedora-bootc\nmodules: []")
    plan_file = tmp_path / "plan.json"
    out_file = tmp_path / "Containerfile"

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "prog",
            "-c",
            str(cfg_file),
            "-v",
            "-o",
            str(out_file),
            "--resolved-package-plan",
            str(plan_file),
        ],
    )

    with patch.object(
        yaml_to_containerfile.ContainerfileGenerator, "generate", return_value="FROM base"
    ):
        yaml_to_containerfile.main()

    assert out_file.exists()
    assert plan_file.exists()
    assert "Build context" in capsys.readouterr().out


def test_ytc_render_script_lines_complex():
    """Test _render_script_lines with compound statements and heredocs."""
    generator = yaml_to_containerfile.ContainerfileGenerator({}, MagicMock())
    generator.lines = []

    lines = [
        "if [ -f /test ]; then",
        "  echo exists",
        "fi",
        "cat <<EOF",
        "hello",
        "EOF",
        "echo done",
    ]
    generator._render_script_lines(lines, "set -e")
    output = "\n".join(generator.lines)

    assert "if [ -f /test ]; then \\" in output
    assert "fi; \\" in output
    assert "cat <<EOF" in output
    assert "    hello" in output
    assert "    EOF" in output
    assert "echo done" in output


def test_ytc_process_script_module_single_line():
    """Test _process_script_module with single line script."""
    generator = yaml_to_containerfile.ContainerfileGenerator({}, MagicMock())
    generator.lines = []
    generator._process_script_module({"scripts": ["echo single"]})
    assert "RUN echo single" in generator.lines


def test_ytc_process_files_module_directory():
    """Test _process_files_module with directory source."""
    generator = yaml_to_containerfile.ContainerfileGenerator({}, MagicMock())
    generator.lines = []
    generator._process_files_module({"files": [{"src": "dir/", "dst": "/dst/"}]})
    assert "COPY --chmod=0644 dir/ /dst/" in generator.lines


# --- package_loader.py coverage ---


def test_loader_infer_bundle_type():
    """Test _infer_bundle_type for different directories."""
    loader = PackageLoader()
    assert loader._infer_bundle_type(loader.wm_dir / "test.yml") == "window-manager"
    assert loader._infer_bundle_type(loader.de_dir / "test.yml") == "desktop-environment"
    assert loader._infer_bundle_type(loader.common_dir / "test.yml") == "common"
    assert loader._infer_bundle_type(loader.kernels_dir / "test.yml") == "kernel-profile"
    assert loader._infer_bundle_type(Path("/tmp/unknown.yml")) == "unknown"  # nosec B108
    assert loader._infer_bundle_type(Path("/dev/null/unknown.yml")) == "unknown"


def test_loader_validate_config_errors():
    """Test various validation errors in _validate_config."""
    loader = PackageLoader()

    with pytest.raises(PackageValidationError, match="must be a mapping"):
        loader._validate_config(123, Path("test.yml"))

    with pytest.raises(PackageValidationError, match="Unsupported or missing 'apiVersion'"):
        loader._validate_config({"apiVersion": "v2", "kind": "PackageBundle"}, Path("test.yml"))

    with pytest.raises(PackageValidationError, match="Unsupported or missing 'kind'"):
        loader._validate_config(
            {"apiVersion": "exousia.packages/v1alpha1", "kind": "BadKind"}, Path("test.yml")
        )

    with pytest.raises(PackageValidationError, match="'metadata' must be a mapping"):
        loader._validate_config(
            {"apiVersion": "exousia.packages/v1alpha1", "kind": "PackageBundle", "metadata": []},
            Path("test.yml"),
        )


def test_loader_validate_config_groups_errors():
    """Test groups validation errors."""
    loader = PackageLoader()
    with pytest.raises(PackageValidationError, match="'groups.install' must be a list of strings"):
        loader._validate_config({"groups": {"install": "not a list"}}, Path("test.yml"))


def test_loader_validate_config_spec_errors():
    """Test spec validation errors."""
    loader = PackageLoader()
    base = {"apiVersion": "exousia.packages/v1alpha1", "kind": "PackageBundle"}

    with pytest.raises(PackageValidationError, match="'spec' must be a mapping"):
        loader._validate_config({**base, "spec": []}, Path("test.yml"))

    with pytest.raises(PackageValidationError, match="'spec.packages' must be a list"):
        loader._validate_config({**base, "spec": {"packages": "not a list"}}, Path("test.yml"))

    with pytest.raises(
        PackageValidationError, match="'spec.groups' must be a list or install/remove mapping"
    ):
        loader._validate_config({**base, "spec": {"groups": 123}}, Path("test.yml"))

    with pytest.raises(PackageValidationError, match="'spec.conflicts' must be a mapping"):
        loader._validate_config({**base, "spec": {"conflicts": []}}, Path("test.yml"))


def test_loader_get_group_actions_more():
    """Test get_group_actions additional cases."""
    loader = PackageLoader()
    assert loader.get_group_actions({"groups": ["a"]}) == {"install": ["a"], "remove": []}
    typed = {
        "apiVersion": "exousia.packages/v1alpha1",
        "kind": "PackageBundle",
        "spec": {"groups": ["b"]},
    }
    assert loader.get_group_actions(typed) == {"install": ["b"], "remove": []}


def test_loader_normalize_package_item_more():
    """Test _normalize_package_item more cases."""
    loader = PackageLoader()
    with pytest.raises(
        PackageValidationError, match="Package object must contain non-empty 'name'"
    ):
        loader._normalize_package_item({"name": ""}, Path("f"), "k")
    with pytest.raises(PackageValidationError, match="Unsupported package entry type"):
        loader._normalize_package_item(123, Path("f"), "k")


def test_loader_validate_selected_bundles_errors():
    """Test _validate_selected_bundles conflict detection."""
    loader = PackageLoader()

    bundles = [{"name": "A", "packages": [], "requires": {"features": ["B"]}}]
    with pytest.raises(PackageValidationError, match="requires missing feature 'B'"):
        loader._validate_selected_bundles(bundles)

    bundles = [
        {"name": "A", "packages": [], "conflicts": {"features": ["B"]}},
        {"name": "B", "packages": []},
    ]
    with pytest.raises(PackageValidationError, match="conflicts with selected feature 'B'"):
        loader._validate_selected_bundles(bundles)


def test_loader_get_package_plan_errors():
    """Test get_package_plan validation logic."""
    loader = PackageLoader()

    with pytest.raises(PackageValidationError, match="Use either 'extras' or 'feature_bundles'"):
        loader.get_package_plan(extras=["a"], feature_bundles=["b"])

    with pytest.raises(
        PackageValidationError, match="Use either explicit 'common_bundles' or 'include_common'"
    ):
        loader.get_package_plan(common_bundles=["a"], include_common=True)
