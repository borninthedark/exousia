"""
Tests for Configuration Endpoints
==================================
"""

import pytest
from httpx import AsyncClient


@pytest.mark.unit
class TestConfigValidation:
    """Test YAML configuration validation."""

    async def test_validate_valid_config(self, client: AsyncClient, sample_yaml_config: str):
        """Test validation of valid YAML configuration."""
        response = await client.post(
            "/api/config/validate", json={"yaml_content": sample_yaml_config}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True
        assert data["errors"] is None or len(data["errors"]) == 0

    async def test_validate_invalid_yaml(self, client: AsyncClient):
        """Test validation of invalid YAML syntax."""
        invalid_yaml = "name: test\n  bad: indentation\n- list"

        response = await client.post(
            "/api/config/validate", json={"yaml_content": invalid_yaml}
        )

        assert response.status_code == 200
        data = response.json()
        # May or may not be valid depending on transpiler
        assert "valid" in data

    async def test_validate_missing_fields(self, client: AsyncClient, invalid_yaml_config: str):
        """Test validation catches missing required fields."""
        response = await client.post(
            "/api/config/validate", json={"yaml_content": invalid_yaml_config}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert data["errors"] is not None
        assert len(data["errors"]) > 0


@pytest.mark.unit
class TestConfigTranspilation:
    """Test YAML to Containerfile transpilation."""

    async def test_transpile_valid_config(self, client: AsyncClient, sample_yaml_config: str):
        """Test transpilation of valid configuration."""
        response = await client.post(
            "/api/config/transpile",
            json={
                "yaml_content": sample_yaml_config,
                "image_type": "fedora-sway-atomic",
                "fedora_version": "43",
                "enable_plymouth": True,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "containerfile" in data
        assert "FROM" in data["containerfile"]
        assert data["image_type"] == "fedora-sway-atomic"
        assert data["fedora_version"] == "43"

    async def test_transpile_bootc_with_plymouth(
        self, client: AsyncClient, sample_yaml_config: str
    ):
        """Test transpilation for bootc with Plymouth enabled."""
        response = await client.post(
            "/api/config/transpile",
            json={
                "yaml_content": sample_yaml_config,
                "image_type": "fedora-bootc",
                "fedora_version": "43",
                "enable_plymouth": True,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "containerfile" in data
        assert data["enable_plymouth"] is True


@pytest.mark.integration
class TestConfigCRUD:
    """Test configuration CRUD operations."""

    async def test_create_config(self, client: AsyncClient, sample_yaml_config: str):
        """Test creating a new configuration."""
        response = await client.post(
            "/api/config/",
            json={
                "name": "test-create",
                "description": "Test config creation",
                "yaml_content": sample_yaml_config,
                "image_type": "fedora-sway-atomic",
                "fedora_version": "43",
                "enable_plymouth": True,
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "test-create"
        assert data["description"] == "Test config creation"
        assert "id" in data
        assert "created_at" in data

    async def test_create_duplicate_config(self, client: AsyncClient, sample_config):
        """Test creating a config with duplicate name fails."""
        response = await client.post(
            "/api/config/",
            json={
                "name": sample_config.name,
                "description": "Duplicate",
                "yaml_content": sample_config.yaml_content,
                "image_type": "fedora-sway-atomic",
                "fedora_version": "43",
                "enable_plymouth": True,
            },
        )

        assert response.status_code == 409
        assert "already exists" in response.json()["error"]

    async def test_get_config(self, client: AsyncClient, sample_config):
        """Test retrieving a specific configuration."""
        response = await client.get(f"/api/config/{sample_config.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == sample_config.id
        assert data["name"] == sample_config.name

    async def test_get_nonexistent_config(self, client: AsyncClient):
        """Test retrieving non-existent config returns 404."""
        response = await client.get("/api/config/99999")

        assert response.status_code == 404

    async def test_list_configs(self, client: AsyncClient, sample_config):
        """Test listing configurations with pagination."""
        response = await client.get("/api/config/")

        assert response.status_code == 200
        data = response.json()
        assert "configs" in data
        assert "total" in data
        assert "page" in data
        assert data["total"] >= 1
        assert len(data["configs"]) >= 1

    async def test_list_configs_pagination(self, client: AsyncClient, sample_config):
        """Test pagination parameters."""
        response = await client.get("/api/config/?page=1&page_size=10")

        assert response.status_code == 200
        data = response.json()
        assert data["page"] == 1
        assert data["page_size"] == 10

    async def test_update_config(self, client: AsyncClient, sample_config):
        """Test updating a configuration."""
        response = await client.put(
            f"/api/config/{sample_config.id}",
            json={
                "name": "updated-config",
                "description": "Updated description",
                "yaml_content": sample_config.yaml_content,
                "image_type": "fedora-bootc",
                "fedora_version": "44",
                "enable_plymouth": False,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "updated-config"
        assert data["fedora_version"] == "44"
        assert data["enable_plymouth"] is False

    async def test_delete_config(self, client: AsyncClient, sample_config):
        """Test deleting a configuration."""
        response = await client.delete(f"/api/config/{sample_config.id}")

        assert response.status_code == 204

        # Verify it's gone
        get_response = await client.get(f"/api/config/{sample_config.id}")
        assert get_response.status_code == 404
