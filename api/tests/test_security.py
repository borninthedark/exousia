import pytest

from api.services.yaml_selector_service import YamlSelectorService
from api.webhook_trigger import validate_yaml_content
from api.config import settings


@pytest.mark.anyio
async def test_trigger_build_rejects_traversal(client):
    response = await client.post(
        "/api/build/trigger",
        json={"definition_filename": "../../etc/passwd"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid definition filename"


@pytest.mark.anyio
async def test_trigger_build_rejects_nested_paths(client):
    response = await client.post(
        "/api/build/trigger",
        json={"definition_filename": "yaml-definitions/../etc/passwd"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid definition filename"


def test_yaml_selector_blocks_path_traversal(monkeypatch, tmp_path):
    definitions_dir = tmp_path / "yaml-definitions"
    definitions_dir.mkdir()

    safe_yaml = definitions_dir / "safe.yml"
    safe_yaml.write_text("name: safe")

    monkeypatch.setattr(settings, "YAML_DEFINITIONS_DIR", definitions_dir)

    selector = YamlSelectorService()

    with pytest.raises(ValueError):
        selector.load_and_customize_yaml("../etc/passwd")

    with pytest.raises(FileNotFoundError):
        selector.load_and_customize_yaml("missing.yml")

    rendered_yaml = selector.load_and_customize_yaml("safe.yml")
    assert "name: safe" in rendered_yaml


def test_yaml_content_validation_rejects_shell_injection():
    assert not validate_yaml_content("os.system('rm -rf /')")
    assert validate_yaml_content("name: safe-config")
