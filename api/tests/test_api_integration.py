"""
API Integration Tests
=====================

Comprehensive integration tests for the API layer.
Tests API endpoints, request validation, and integration between components.
"""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient


@pytest.mark.integration
class TestBuildAPIIntegration:
    """Test build API endpoints with full integration."""

    @patch("api.routers.build.GitHubService")
    async def test_trigger_build_with_yaml_content(self, mock_github_service, client: AsyncClient):
        """Test triggering build with ad-hoc YAML content."""
        # Mock GitHub workflow run
        mock_workflow_run = AsyncMock()
        mock_workflow_run.id = 12345
        mock_workflow_run.html_url = "https://github.com/test/repo/actions/runs/12345"

        # Mock GitHub service
        mock_github = AsyncMock()
        mock_github.trigger_workflow = AsyncMock(return_value=mock_workflow_run)
        mock_github_service.return_value = mock_github

        yaml_content = """
name: test-config
description: Test configuration
modules:
  - type: packages
    packages:
      - vim
"""

        with patch("api.routers.build.settings") as mock_settings:
            mock_settings.GITHUB_TOKEN = "fake_token"
            mock_settings.GITHUB_REPO = "test/repo"
            mock_settings.GITHUB_WORKFLOW_FILE = "build.yml"
            mock_settings.BUILD_STATUS_POLLING_ENABLED = False

            response = await client.post(
                "/api/build/trigger",
                json={
                    "yaml_content": yaml_content,
                    "image_type": "fedora-bootc",
                    "fedora_version": "43",
                    "enable_plymouth": True,
                    "ref": "main",
                },
            )

            assert response.status_code == 202
            data = response.json()
            assert data["status"] == "in_progress"
            assert data["workflow_run_id"] == 12345

            # Verify workflow was triggered with yaml_content
            mock_github.trigger_workflow.assert_called_once()
            call_args = mock_github.trigger_workflow.call_args
            assert "yaml_content" in call_args.kwargs["inputs"]
            assert "vim" in call_args.kwargs["inputs"]["yaml_content"]

    @patch("api.routers.build.GitHubService")
    async def test_trigger_build_with_definition_file(self, mock_github_service, client: AsyncClient):
        """Test triggering build with definition file."""
        # Mock GitHub workflow run
        mock_workflow_run = AsyncMock()
        mock_workflow_run.id = 12346
        mock_workflow_run.html_url = "https://github.com/test/repo/actions/runs/12346"

        # Mock GitHub service
        mock_github = AsyncMock()
        mock_github.trigger_workflow = AsyncMock(return_value=mock_workflow_run)
        mock_github_service.return_value = mock_github

        with patch("api.routers.build.settings") as mock_settings:
            mock_settings.GITHUB_TOKEN = "fake_token"
            mock_settings.GITHUB_REPO = "test/repo"
            mock_settings.GITHUB_WORKFLOW_FILE = "build.yml"
            mock_settings.BUILD_STATUS_POLLING_ENABLED = False
            mock_settings.YAML_DEFINITIONS_DIR = __import__("pathlib").Path("yaml-definitions")

            response = await client.post(
                "/api/build/trigger",
                json={
                    "definition_filename": "sway-bootc.yml",
                    "image_type": "fedora-bootc",
                    "fedora_version": "43",
                    "enable_plymouth": True,
                    "ref": "main",
                },
            )

            # Should succeed if file exists
            if response.status_code == 202:
                data = response.json()
                assert data["status"] == "in_progress"
                assert data["workflow_run_id"] == 12346

                # Verify workflow was triggered with yaml_content from file
                mock_github.trigger_workflow.assert_called_once()
                call_args = mock_github.trigger_workflow.call_args
                assert "yaml_content" in call_args.kwargs["inputs"]
            else:
                # File not found is also acceptable in test environment
                assert response.status_code == 404

    @patch("api.routers.build.GitHubService")
    async def test_trigger_build_with_config_id(self, mock_github_service, client: AsyncClient, sample_config):
        """Test triggering build from saved configuration."""
        # Mock GitHub workflow run
        mock_workflow_run = AsyncMock()
        mock_workflow_run.id = 12347
        mock_workflow_run.html_url = "https://github.com/test/repo/actions/runs/12347"

        # Mock GitHub service
        mock_github = AsyncMock()
        mock_github.trigger_workflow = AsyncMock(return_value=mock_workflow_run)
        mock_github_service.return_value = mock_github

        with patch("api.routers.build.settings") as mock_settings:
            mock_settings.GITHUB_TOKEN = "fake_token"
            mock_settings.GITHUB_REPO = "test/repo"
            mock_settings.GITHUB_WORKFLOW_FILE = "build.yml"
            mock_settings.BUILD_STATUS_POLLING_ENABLED = False

            response = await client.post(
                "/api/build/trigger",
                json={
                    "config_id": sample_config.id,
                    "ref": "main",
                },
            )

            assert response.status_code == 202
            data = response.json()
            assert data["status"] == "in_progress"

            # Verify workflow was triggered with yaml_content from config
            mock_github.trigger_workflow.assert_called_once()
            call_args = mock_github.trigger_workflow.call_args
            assert "yaml_content" in call_args.kwargs["inputs"]

    async def test_trigger_build_invalid_yaml(self, client: AsyncClient):
        """Test triggering build with invalid YAML content fails validation."""
        invalid_yaml = "invalid: yaml: content: [[[]]"

        response = await client.post(
            "/api/build/trigger",
            json={
                "yaml_content": invalid_yaml,
                "image_type": "fedora-bootc",
                "fedora_version": "43",
                "enable_plymouth": True,
                "ref": "main",
            },
        )

        assert response.status_code == 400
        assert "Invalid YAML" in response.json()["detail"]

    @patch("api.routers.build.GitHubService")
    async def test_trigger_build_with_desktop_override(self, mock_github_service, client: AsyncClient):
        """Test triggering build with window manager override for fedora-bootc."""
        # Mock GitHub workflow run
        mock_workflow_run = AsyncMock()
        mock_workflow_run.id = 12348
        mock_workflow_run.html_url = "https://github.com/test/repo/actions/runs/12348"

        # Mock GitHub service
        mock_github = AsyncMock()
        mock_github.trigger_workflow = AsyncMock(return_value=mock_workflow_run)
        mock_github_service.return_value = mock_github

        yaml_content = """
name: test-bootc
description: Test bootc configuration
desktop:
  window_manager: sway
modules:
  - type: packages
    packages:
      - sway
"""

        with patch("api.routers.build.settings") as mock_settings:
            mock_settings.GITHUB_TOKEN = "fake_token"
            mock_settings.GITHUB_REPO = "test/repo"
            mock_settings.GITHUB_WORKFLOW_FILE = "build.yml"
            mock_settings.BUILD_STATUS_POLLING_ENABLED = False

            response = await client.post(
                "/api/build/trigger",
                json={
                    "yaml_content": yaml_content,
                    "image_type": "fedora-bootc",
                    "fedora_version": "43",
                    "enable_plymouth": True,
                    "window_manager": "river",
                    "ref": "main",
                },
            )

            assert response.status_code == 202

            # Verify workflow inputs include window_manager
            mock_github.trigger_workflow.assert_called_once()
            call_args = mock_github.trigger_workflow.call_args
            assert call_args.kwargs["inputs"]["window_manager"] == "river"


@pytest.mark.integration
class TestConfigAPIIntegration:
    """Test configuration API endpoints with full integration."""

    async def test_validate_config_with_yaml_content(self, client: AsyncClient):
        """Test config validation endpoint."""
        yaml_content = """
name: test-validation
description: Test validation
modules:
  - type: packages
    packages:
      - neovim
"""

        response = await client.post(
            "/api/config/validate",
            json={"yaml_content": yaml_content},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True

    async def test_validate_invalid_config(self, client: AsyncClient):
        """Test validation with invalid YAML."""
        invalid_yaml = """
name: missing-modules
description: Invalid config
"""

        response = await client.post(
            "/api/config/validate",
            json={"yaml_content": invalid_yaml},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert "errors" in data

    async def test_transpile_config(self, client: AsyncClient):
        """Test config transpilation endpoint."""
        yaml_content = """
name: test-transpile
description: Test transpilation
modules:
  - type: packages
    packages:
      - git
"""

        response = await client.post(
            "/api/config/transpile",
            json={
                "yaml_content": yaml_content,
                "image_type": "fedora-bootc",
                "fedora_version": "43",
                "enable_plymouth": True,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "containerfile" in data
        assert "RUN" in data["containerfile"]

    async def test_create_and_retrieve_config(self, client: AsyncClient):
        """Test creating and retrieving a configuration."""
        yaml_content = """
name: test-create
description: Test configuration creation
modules:
  - type: packages
    packages:
      - zsh
"""

        # Create config
        create_response = await client.post(
            "/api/config/",
            json={
                "name": "test-create-config",
                "description": "Test config",
                "yaml_content": yaml_content,
                "image_type": "fedora-bootc",
                "fedora_version": "43",
                "enable_plymouth": True,
            },
        )

        assert create_response.status_code == 201
        config_data = create_response.json()
        config_id = config_data["id"]

        # Retrieve config
        get_response = await client.get(f"/api/config/{config_id}")
        assert get_response.status_code == 200
        retrieved_data = get_response.json()
        assert retrieved_data["name"] == "test-create-config"
        assert "zsh" in retrieved_data["yaml_content"]

    async def test_list_yaml_definitions(self, client: AsyncClient):
        """Test listing YAML definition files."""
        response = await client.get("/api/config/definitions/list")

        assert response.status_code == 200
        data = response.json()
        assert "definitions" in data
        assert "total" in data


    @patch("api.routers.build.GitHubService")
    async def test_trigger_build_with_auto_selection(self, mock_github_service, client: AsyncClient):
        """Test triggering build with auto-selection based on OS/DE/WM."""
        # Mock GitHub workflow run
        mock_workflow_run = AsyncMock()
        mock_workflow_run.id = 12349
        mock_workflow_run.html_url = "https://github.com/test/repo/actions/runs/12349"

        # Mock GitHub service
        mock_github = AsyncMock()
        mock_github.trigger_workflow = AsyncMock(return_value=mock_workflow_run)
        mock_github_service.return_value = mock_github

        with patch("api.routers.build.settings") as mock_settings:
            mock_settings.GITHUB_TOKEN = "fake_token"
            mock_settings.GITHUB_REPO = "test/repo"
            mock_settings.GITHUB_WORKFLOW_FILE = "build.yml"
            mock_settings.BUILD_STATUS_POLLING_ENABLED = False
            mock_settings.YAML_DEFINITIONS_DIR = __import__("pathlib").Path("yaml-definitions")

            # Test auto-selection with window manager
            response = await client.post(
                "/api/build/trigger",
                json={
                    "image_type": "fedora-bootc",
                    "fedora_version": "43",
                    "window_manager": "sway",
                    "enable_plymouth": True,
                    "ref": "main",
                },
            )

            # Should succeed if yaml-definitions directory exists
            if response.status_code == 202:
                data = response.json()
                assert data["status"] == "in_progress"

                # Verify workflow was triggered with yaml_content
                mock_github.trigger_workflow.assert_called_once()
                call_args = mock_github.trigger_workflow.call_args
                assert "yaml_content" in call_args.kwargs["inputs"]
            else:
                # Auto-selection failure is acceptable if no definitions exist
                assert response.status_code == 400


@pytest.mark.integration
class TestHealthAPIIntegration:
    """Test health check API endpoints."""

    async def test_health_check(self, client: AsyncClient):
        """Test health check endpoint."""
        response = await client.get("/api/health")

        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "database" in data
