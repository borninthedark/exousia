#!/usr/bin/env python3
"""
Unit tests for generator.cli — covers uncovered branches.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

from generator.cli import determine_base_image, load_yaml_config, main, validate_config
from generator.constants import FEDORA_ATOMIC_VARIANTS


class TestLoadYamlConfig:
    def test_valid_yaml(self, tmp_path):
        cfg = tmp_path / "test.yml"
        cfg.write_text("name: test\ndescription: desc\nmodules: []")
        result = load_yaml_config(cfg)
        assert result["name"] == "test"

    def test_file_not_found(self, tmp_path):
        with pytest.raises(SystemExit) as exc:
            load_yaml_config(tmp_path / "missing.yml")
        assert exc.value.code == 1

    def test_invalid_yaml(self, tmp_path):
        cfg = tmp_path / "bad.yml"
        cfg.write_text("invalid: [unclosed")
        with pytest.raises(SystemExit) as exc:
            load_yaml_config(cfg)
        assert exc.value.code == 1


class TestDetermineBaseImage:
    def test_empty_version_raises(self):
        with pytest.raises(ValueError, match="version must be specified"):
            determine_base_image({}, "fedora-bootc", "")

    def test_preferred_base_with_tag(self):
        result = determine_base_image(
            {"base-image": "quay.io/custom/image:latest"}, "fedora-bootc", "43"
        )
        assert result == "quay.io/custom/image:latest"

    def test_preferred_base_without_tag(self):
        result = determine_base_image({"base-image": "quay.io/custom/image"}, "fedora-bootc", "43")
        assert result == "quay.io/custom/image:43"

    def test_preferred_base_with_digest(self):
        result = determine_base_image(
            {"base-image": "quay.io/custom/image@sha256:abc123"}, "fedora-bootc", "43"
        )
        assert result == "quay.io/custom/image@sha256:abc123"

    def test_fedora_bootc_default(self):
        result = determine_base_image({}, "fedora-bootc", "44")
        assert result == "quay.io/fedora/fedora-bootc:44"

    def test_fedora_sway_atomic(self):
        result = determine_base_image({}, "fedora-sway-atomic", "43")
        assert result == f"{FEDORA_ATOMIC_VARIANTS['fedora-sway-atomic']}:43"

    def test_unknown_type_no_preferred(self):
        result = determine_base_image({}, "unknown-type", "43")
        assert result == "quay.io/fedora/fedora-bootc:43"

    def test_unknown_type_with_preferred(self):
        result = determine_base_image({"base-image": "quay.io/custom/img"}, "unknown-type", "43")
        assert result == "quay.io/custom/img:43"


class TestValidateConfig:
    def test_valid_config(self, capsys):
        assert validate_config({"name": "x", "description": "y", "modules": []}) is True
        assert "passed" in capsys.readouterr().out

    def test_missing_name(self, capsys):
        assert validate_config({"description": "y", "modules": []}) is False
        assert "name" in capsys.readouterr().err

    def test_missing_description(self, capsys):
        assert validate_config({"name": "x", "modules": []}) is False
        assert "description" in capsys.readouterr().err

    def test_missing_modules(self, capsys):
        assert validate_config({"name": "x", "description": "y"}) is False
        assert "modules" in capsys.readouterr().err


class TestMain:
    def test_validate_only(self, monkeypatch, tmp_path, capsys):
        cfg = tmp_path / "test.yml"
        cfg.write_text("name: t\ndescription: d\nmodules: []")
        monkeypatch.setattr(sys, "argv", ["prog", "-c", str(cfg), "--validate"])
        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 0
        assert "valid" in capsys.readouterr().out

    def test_invalid_config_exits(self, monkeypatch, tmp_path):
        cfg = tmp_path / "test.yml"
        cfg.write_text("foo: bar")  # missing required fields
        monkeypatch.setattr(sys, "argv", ["prog", "-c", str(cfg)])
        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 1

    def test_generate_to_stdout(self, monkeypatch, tmp_path, capsys):
        cfg = tmp_path / "test.yml"
        cfg.write_text(
            "name: t\ndescription: d\nimage-type: fedora-bootc\n" "image-version: 43\nmodules: []"
        )
        monkeypatch.setattr(sys, "argv", ["prog", "-c", str(cfg)])
        main()
        output = capsys.readouterr().out
        assert "FROM" in output

    def test_generate_to_file(self, monkeypatch, tmp_path):
        cfg = tmp_path / "test.yml"
        cfg.write_text(
            "name: t\ndescription: d\nimage-type: fedora-sway-atomic\n"
            "image-version: 43\nmodules: []"
        )
        out = tmp_path / "Containerfile"
        monkeypatch.setattr(sys, "argv", ["prog", "-c", str(cfg), "-o", str(out)])
        main()
        assert out.exists()
        assert "FROM" in out.read_text()

    def test_verbose_output(self, monkeypatch, tmp_path, capsys):
        cfg = tmp_path / "test.yml"
        cfg.write_text("name: t\ndescription: d\nmodules: []\nimage-version: 43")
        monkeypatch.setattr(sys, "argv", ["prog", "-c", str(cfg), "-v"])
        main()
        output = capsys.readouterr().out
        assert "Build context" in output

    def test_disable_plymouth(self, monkeypatch, tmp_path, capsys):
        cfg = tmp_path / "test.yml"
        cfg.write_text(
            "name: t\ndescription: d\nimage-type: fedora-bootc\n" "image-version: 43\nmodules: []"
        )
        monkeypatch.setattr(sys, "argv", ["prog", "-c", str(cfg), "--disable-plymouth", "-v"])
        main()
        output = capsys.readouterr().out
        assert "Plymouth: False" in output

    def test_enable_zfs(self, monkeypatch, tmp_path, capsys):
        cfg = tmp_path / "test.yml"
        cfg.write_text(
            "name: t\ndescription: d\nimage-type: fedora-bootc\n" "image-version: 43\nmodules: []"
        )
        monkeypatch.setattr(sys, "argv", ["prog", "-c", str(cfg), "--enable-zfs", "-v"])
        main()
        output = capsys.readouterr().out
        assert "ZFS: True" in output

    def test_resolved_package_plan_output(self, monkeypatch, tmp_path):
        cfg = tmp_path / "test.yml"
        cfg.write_text("name: t\ndescription: d\nmodules: []\nimage-version: 43")
        plan = tmp_path / "plan.json"
        monkeypatch.setattr(
            sys, "argv", ["prog", "-c", str(cfg), "--resolved-package-plan", str(plan)]
        )
        main()
        assert plan.exists()
        import json

        data = json.loads(plan.read_text())
        assert "image" in data
        assert "rpm" in data

    def test_custom_fedora_version(self, monkeypatch, tmp_path, capsys):
        cfg = tmp_path / "test.yml"
        cfg.write_text("name: t\ndescription: d\nmodules: []")
        monkeypatch.setattr(sys, "argv", ["prog", "-c", str(cfg), "--fedora-version", "44", "-v"])
        main()
        output = capsys.readouterr().out
        assert "Fedora version: 44" in output
