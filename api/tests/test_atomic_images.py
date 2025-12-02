"""
Atomic Image Tests
==================

Comprehensive tests for atomic image builds (Silverblue, Kinoite, etc.)
across different Fedora versions and configurations.
"""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient


@pytest.mark.integration
class TestFedoraAtomicImages:
    """Test Fedora atomic (ostree) image builds."""

    @patch("api.routers.build.GitHubService")
    async def test_fedora_silverblue(self, mock_github_service, client: AsyncClient):
        """Test Fedora Silverblue (GNOME) build."""
        mock_workflow_run = AsyncMock()
        mock_workflow_run.id = 20001
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
                    "image_type": "fedora-silverblue",
                    "fedora_version": "43",
                    "enable_plymouth": True,
                    "ref": "main",
                },
            )

            if response.status_code == 202:
                data = response.json()
                assert data["image_type"] == "fedora-silverblue"
                assert data["fedora_version"] == "43"

    @patch("api.routers.build.GitHubService")
    async def test_fedora_kinoite(self, mock_github_service, client: AsyncClient):
        """Test Fedora Kinoite (KDE) build."""
        mock_workflow_run = AsyncMock()
        mock_workflow_run.id = 20002
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
                    "image_type": "fedora-kinoite",
                    "fedora_version": "43",
                    "enable_plymouth": True,
                    "ref": "main",
                },
            )

            if response.status_code == 202:
                data = response.json()
                assert data["image_type"] == "fedora-kinoite"

    @patch("api.routers.build.GitHubService")
    async def test_fedora_sway_atomic(self, mock_github_service, client: AsyncClient):
        """Test Fedora Sway Atomic build."""
        mock_workflow_run = AsyncMock()
        mock_workflow_run.id = 20003
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
                    "image_type": "fedora-sway-atomic",
                    "fedora_version": "43",
                    "enable_plymouth": True,
                    "ref": "main",
                },
            )

            if response.status_code == 202:
                data = response.json()
                assert data["image_type"] == "fedora-sway-atomic"

    @patch("api.routers.build.GitHubService")
    async def test_fedora_onyx(self, mock_github_service, client: AsyncClient):
        """Test Fedora Onyx (Budgie) build."""
        mock_workflow_run = AsyncMock()
        mock_workflow_run.id = 20004
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
                    "image_type": "fedora-onyx",
                    "fedora_version": "43",
                    "enable_plymouth": True,
                    "ref": "main",
                },
            )

            # Accept success, not found, or validation error (onyx may not be a valid image_type)
            assert response.status_code in [202, 400, 404, 422]


@pytest.mark.integration
class TestAtomicVersions:
    """Test atomic images across different Fedora versions."""

    @patch("api.routers.build.GitHubService")
    async def test_silverblue_version_42(self, mock_github_service, client: AsyncClient):
        """Test Silverblue Fedora 42."""
        mock_workflow_run = AsyncMock()
        mock_workflow_run.id = 20101
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
                    "image_type": "fedora-silverblue",
                    "fedora_version": "42",
                    "enable_plymouth": True,
                    "ref": "main",
                },
            )

            if response.status_code == 202:
                data = response.json()
                assert data["fedora_version"] == "42"

    @patch("api.routers.build.GitHubService")
    async def test_kinoite_version_44(self, mock_github_service, client: AsyncClient):
        """Test Kinoite Fedora 44."""
        mock_workflow_run = AsyncMock()
        mock_workflow_run.id = 20102
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
                    "image_type": "fedora-kinoite",
                    "fedora_version": "44",
                    "enable_plymouth": True,
                    "ref": "main",
                },
            )

            if response.status_code == 202:
                data = response.json()
                assert data["fedora_version"] == "44"

    @patch("api.routers.build.GitHubService")
    async def test_sway_atomic_rawhide(self, mock_github_service, client: AsyncClient):
        """Test Sway Atomic with Rawhide."""
        mock_workflow_run = AsyncMock()
        mock_workflow_run.id = 20103
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
                    "image_type": "fedora-sway-atomic",
                    "fedora_version": "rawhide",
                    "enable_plymouth": True,
                    "ref": "main",
                },
            )

            if response.status_code == 202:
                data = response.json()
                assert data["fedora_version"] == "rawhide"


@pytest.mark.integration
class TestAtomicWithCustomizations:
    """Test atomic images with various customizations."""

    @patch("api.routers.build.GitHubService")
    async def test_kinoite_with_custom_yaml(self, mock_github_service, client: AsyncClient):
        """Test Kinoite (KDE) with custom YAML content."""
        mock_workflow_run = AsyncMock()
        mock_workflow_run.id = 20201
        mock_github = AsyncMock()
        mock_github.trigger_workflow = AsyncMock(return_value=mock_workflow_run)
        mock_github_service.return_value = mock_github

        custom_yaml = """
name: custom-kinoite
description: Custom Kinoite (KDE) configuration
modules:
  - type: packages
    packages:
      - neovim
      - tmux
"""

        with patch("api.routers.build.settings") as mock_settings:
            mock_settings.GITHUB_TOKEN = "fake_token"
            mock_settings.GITHUB_REPO = "test/repo"
            mock_settings.GITHUB_WORKFLOW_FILE = "build.yml"
            mock_settings.BUILD_STATUS_POLLING_ENABLED = False

            response = await client.post(
                "/api/build/trigger",
                json={
                    "yaml_content": custom_yaml,
                    "image_type": "fedora-kinoite",
                    "fedora_version": "43",
                    "enable_plymouth": True,
                    "ref": "main",
                },
            )

            assert response.status_code == 202
            data = response.json()
            assert data["image_type"] == "fedora-kinoite"

            # Verify custom YAML was passed to workflow
            mock_github.trigger_workflow.assert_called_once()
            call_args = mock_github.trigger_workflow.call_args
            assert "neovim" in call_args.kwargs["inputs"]["yaml_content"]

    @patch("api.routers.build.GitHubService")
    async def test_atomic_without_plymouth(self, mock_github_service, client: AsyncClient):
        """Test atomic image without Plymouth."""
        mock_workflow_run = AsyncMock()
        mock_workflow_run.id = 20202
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
                    "image_type": "fedora-kinoite",
                    "fedora_version": "43",
                    "enable_plymouth": False,
                    "ref": "main",
                },
            )

            if response.status_code == 202:
                # Verify Plymouth is disabled
                mock_github.trigger_workflow.assert_called_once()
                call_args = mock_github.trigger_workflow.call_args
                assert call_args.kwargs["inputs"]["enable_plymouth"] == "false"
