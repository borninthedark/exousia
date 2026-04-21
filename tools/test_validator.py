#!/usr/bin/env python3
"""
Unit tests for package_loader.validator — covers uncovered branches.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

from package_loader.exceptions import PackageValidationError
from package_loader.validator import is_typed_bundle, normalize_package_item, validate_config


class TestIsTypedBundle:
    def test_apiversion_present(self):
        assert is_typed_bundle({"apiVersion": "exousia.packages/v1alpha1"}) is True

    def test_kind_present(self):
        assert is_typed_bundle({"kind": "PackageBundle"}) is True

    def test_spec_present(self):
        assert is_typed_bundle({"spec": {}}) is True

    def test_legacy_format(self):
        assert is_typed_bundle({"packages": ["vim"]}) is False

    def test_empty_dict(self):
        assert is_typed_bundle({}) is False


class TestNormalizePackageItem:
    def test_string_item(self):
        assert normalize_package_item("vim", Path("f"), "k") == "vim"

    def test_string_with_whitespace(self):
        assert normalize_package_item("  git  ", Path("f"), "k") == "git"

    def test_empty_string_raises(self):
        with pytest.raises(PackageValidationError, match="Invalid empty package"):
            normalize_package_item("", Path("f"), "k")

    def test_whitespace_only_raises(self):
        with pytest.raises(PackageValidationError, match="Invalid empty package"):
            normalize_package_item("   ", Path("f"), "k")

    def test_dict_with_name(self):
        assert normalize_package_item({"name": "htop"}, Path("f"), "k") == "htop"

    def test_dict_name_with_whitespace(self):
        assert normalize_package_item({"name": " btop "}, Path("f"), "k") == "btop"

    def test_dict_empty_name_raises(self):
        with pytest.raises(PackageValidationError, match="non-empty 'name'"):
            normalize_package_item({"name": ""}, Path("f"), "k")

    def test_dict_missing_name_raises(self):
        with pytest.raises(PackageValidationError, match="non-empty 'name'"):
            normalize_package_item({"version": "1.0"}, Path("f"), "k")

    def test_dict_none_name_raises(self):
        with pytest.raises(PackageValidationError, match="non-empty 'name'"):
            normalize_package_item({"name": None}, Path("f"), "k")

    def test_unsupported_type_int(self):
        with pytest.raises(PackageValidationError, match="Unsupported package entry type"):
            normalize_package_item(123, Path("f"), "k")

    def test_unsupported_type_list(self):
        with pytest.raises(PackageValidationError, match="Unsupported package entry type"):
            normalize_package_item(["a"], Path("f"), "k")


class TestValidateConfig:
    def test_non_dict_raises(self):
        with pytest.raises(PackageValidationError, match="must be a mapping"):
            validate_config([], Path("f"))

    def test_legacy_simple_packages(self):
        # Legacy format: top-level keys with lists of package strings
        validate_config({"core": ["vim", "git"]}, Path("f"))

    def test_typed_bundle_valid(self):
        config = {
            "apiVersion": "exousia.packages/v1alpha1",
            "kind": "PackageBundle",
            "spec": {"packages": ["vim", {"name": "git"}]},
        }
        validate_config(config, Path("f"))

    def test_typed_bundle_bad_api_version(self):
        with pytest.raises(PackageValidationError, match="Unsupported or missing 'apiVersion'"):
            validate_config({"apiVersion": "v99", "kind": "PackageBundle", "spec": {}}, Path("f"))

    def test_typed_bundle_bad_kind(self):
        with pytest.raises(PackageValidationError, match="Unsupported or missing 'kind'"):
            validate_config(
                {"apiVersion": "exousia.packages/v1alpha1", "kind": "BadKind", "spec": {}},
                Path("f"),
            )

    def test_metadata_not_dict_raises(self):
        with pytest.raises(PackageValidationError, match="'metadata' must be a mapping"):
            validate_config({"metadata": "bad"}, Path("f"))

    def test_metadata_empty_name_raises(self):
        with pytest.raises(PackageValidationError, match="'metadata.name' must be a non-empty"):
            validate_config({"metadata": {"name": ""}}, Path("f"))

    def test_metadata_type_empty_raises(self):
        with pytest.raises(PackageValidationError, match="'metadata.type' must be a non-empty"):
            validate_config({"metadata": {"type": "  "}}, Path("f"))

    def test_metadata_valid(self):
        validate_config(
            {"metadata": {"name": "core", "type": "common"}, "packages": ["vim"]}, Path("f")
        )

    def test_groups_list_valid(self):
        validate_config({"groups": ["Core", "Multimedia"]}, Path("f"))

    def test_groups_list_non_strings_raises(self):
        with pytest.raises(PackageValidationError, match="'groups' must be a list of strings"):
            validate_config({"groups": [123]}, Path("f"))

    def test_groups_dict_valid(self):
        validate_config({"groups": {"install": ["Core"], "remove": ["Base"]}}, Path("f"))

    def test_groups_dict_bad_install_raises(self):
        with pytest.raises(PackageValidationError, match="'groups.install' must be a list"):
            validate_config({"groups": {"install": "not a list"}}, Path("f"))

    def test_groups_dict_bad_remove_raises(self):
        with pytest.raises(PackageValidationError, match="'groups.remove' must be a list"):
            validate_config({"groups": {"remove": [123]}}, Path("f"))

    def test_groups_invalid_type_raises(self):
        with pytest.raises(PackageValidationError, match="'groups' must be a list or"):
            validate_config({"groups": 42}, Path("f"))

    def test_typed_spec_not_dict_raises(self):
        base = {"apiVersion": "exousia.packages/v1alpha1", "kind": "PackageBundle"}
        with pytest.raises(PackageValidationError, match="'spec' must be a mapping"):
            validate_config({**base, "spec": "bad"}, Path("f"))

    def test_typed_spec_packages_not_list_raises(self):
        base = {"apiVersion": "exousia.packages/v1alpha1", "kind": "PackageBundle"}
        with pytest.raises(PackageValidationError, match="'spec.packages' must be a list"):
            validate_config({**base, "spec": {"packages": "bad"}}, Path("f"))

    def test_typed_spec_packages_invalid_item_raises(self):
        base = {"apiVersion": "exousia.packages/v1alpha1", "kind": "PackageBundle"}
        with pytest.raises(PackageValidationError, match="Unsupported package entry type"):
            validate_config({**base, "spec": {"packages": [123]}}, Path("f"))

    def test_typed_spec_groups_invalid_type_raises(self):
        base = {"apiVersion": "exousia.packages/v1alpha1", "kind": "PackageBundle"}
        with pytest.raises(
            PackageValidationError, match="'spec.groups' must be a list or install/remove"
        ):
            validate_config({**base, "spec": {"groups": 42}}, Path("f"))

    def test_typed_spec_groups_list_non_strings_raises(self):
        base = {"apiVersion": "exousia.packages/v1alpha1", "kind": "PackageBundle"}
        with pytest.raises(PackageValidationError, match="'spec.groups' must be a list of strings"):
            validate_config({**base, "spec": {"groups": [1, 2]}}, Path("f"))

    def test_typed_spec_groups_dict_bad_install(self):
        base = {"apiVersion": "exousia.packages/v1alpha1", "kind": "PackageBundle"}
        with pytest.raises(
            PackageValidationError, match="'spec.groups.install' must be a list of strings"
        ):
            validate_config({**base, "spec": {"groups": {"install": [123]}}}, Path("f"))

    def test_typed_spec_conflicts_not_dict_raises(self):
        base = {"apiVersion": "exousia.packages/v1alpha1", "kind": "PackageBundle"}
        with pytest.raises(PackageValidationError, match="'spec.conflicts' must be a mapping"):
            validate_config({**base, "spec": {"conflicts": []}}, Path("f"))

    def test_typed_spec_conflicts_bad_packages(self):
        base = {"apiVersion": "exousia.packages/v1alpha1", "kind": "PackageBundle"}
        with pytest.raises(
            PackageValidationError, match="'spec.conflicts.packages' must be a list of strings"
        ):
            validate_config({**base, "spec": {"conflicts": {"packages": [1]}}}, Path("f"))

    def test_typed_spec_conflicts_bad_features(self):
        base = {"apiVersion": "exousia.packages/v1alpha1", "kind": "PackageBundle"}
        with pytest.raises(
            PackageValidationError, match="'spec.conflicts.features' must be a list of strings"
        ):
            validate_config({**base, "spec": {"conflicts": {"features": [1]}}}, Path("f"))

    def test_typed_spec_replaces_not_list_raises(self):
        base = {"apiVersion": "exousia.packages/v1alpha1", "kind": "PackageBundle"}
        with pytest.raises(PackageValidationError, match="'spec.replaces' must be a list"):
            validate_config({**base, "spec": {"replaces": "bad"}}, Path("f"))

    def test_typed_spec_replaces_non_strings_raises(self):
        base = {"apiVersion": "exousia.packages/v1alpha1", "kind": "PackageBundle"}
        with pytest.raises(PackageValidationError, match="'spec.replaces' must be a list"):
            validate_config({**base, "spec": {"replaces": [1, 2]}}, Path("f"))

    def test_typed_spec_requires_not_dict_raises(self):
        base = {"apiVersion": "exousia.packages/v1alpha1", "kind": "PackageBundle"}
        with pytest.raises(PackageValidationError, match="'spec.requires' must be a mapping"):
            validate_config({**base, "spec": {"requires": []}}, Path("f"))

    def test_typed_spec_requires_bad_features(self):
        base = {"apiVersion": "exousia.packages/v1alpha1", "kind": "PackageBundle"}
        with pytest.raises(
            PackageValidationError, match="'spec.requires.features' must be a list of strings"
        ):
            validate_config({**base, "spec": {"requires": {"features": [1]}}}, Path("f"))

    def test_typed_spec_full_valid(self):
        config = {
            "apiVersion": "exousia.packages/v1alpha1",
            "kind": "PackageBundle",
            "metadata": {"name": "test", "type": "feature"},
            "spec": {
                "packages": ["vim", {"name": "git"}],
                "groups": {"install": ["Core"], "remove": []},
                "conflicts": {"packages": ["emacs"], "features": ["minimal"]},
                "replaces": ["nano"],
                "requires": {"features": ["desktop"]},
            },
        }
        validate_config(config, Path("f"))

    def test_legacy_walk_nested_dict(self):
        # Legacy format with nested keys
        validate_config({"core": ["vim"], "extras": ["htop"]}, Path("f"))

    def test_legacy_walk_unsupported_value_type(self):
        with pytest.raises(PackageValidationError, match="Unsupported value type"):
            validate_config({"core": 42}, Path("f"))
