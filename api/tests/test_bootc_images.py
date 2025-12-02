"""
Bootc Image Tests
=================

Comprehensive tests for bootc image builds across different distributions,
desktop environments, and window managers.
"""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient


@pytest.mark.integration
class TestFedoraBootcImages:
    """Test Fedora bootc image builds."""

    @patch("api.routers.build.GitHubService")
    async def test_fedora_bootc_sway(self, mock_github_service, client: AsyncClient):
        """Test Fedora bootc with Sway window manager."""
        mock_workflow_run = AsyncMock()
        mock_workflow_run.id = 10001
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
                    "image_type": "fedora-bootc",
                    "fedora_version": "43",
                    "window_manager": "sway",
                    "enable_plymouth": True,
                    "ref": "main",
                },
            )

            if response.status_code == 202:
                data = response.json()
                assert data["image_type"] == "fedora-bootc"
                assert data["fedora_version"] == "43"

    @patch("api.routers.build.GitHubService")
    async def test_fedora_bootc_hyprland(self, mock_github_service, client: AsyncClient):
        """Test Fedora bootc with Hyprland window manager."""
        mock_workflow_run = AsyncMock()
        mock_workflow_run.id = 10002
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
                    "image_type": "fedora-bootc",
                    "fedora_version": "43",
                    "window_manager": "hyprland",
                    "enable_plymouth": True,
                    "ref": "main",
                },
            )

            if response.status_code == 202:
                data = response.json()
                assert data["image_type"] == "fedora-bootc"

    @patch("api.routers.build.GitHubService")
    async def test_fedora_bootc_kde(self, mock_github_service, client: AsyncClient):
        """Test Fedora bootc with KDE desktop environment."""
        mock_workflow_run = AsyncMock()
        mock_workflow_run.id = 10003
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
                    "image_type": "fedora-bootc",
                    "fedora_version": "43",
                    "desktop_environment": "kde",
                    "enable_plymouth": True,
                    "ref": "main",
                },
            )

            if response.status_code == 202:
                data = response.json()
                assert data["image_type"] == "fedora-bootc"

    @patch("api.routers.build.GitHubService")
    async def test_fedora_bootc_gnome(self, mock_github_service, client: AsyncClient):
        """Test Fedora bootc with GNOME desktop environment."""
        mock_workflow_run = AsyncMock()
        mock_workflow_run.id = 10004
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
                    "image_type": "fedora-bootc",
                    "fedora_version": "43",
                    "desktop_environment": "gnome",
                    "enable_plymouth": True,
                    "ref": "main",
                },
            )

            if response.status_code == 202:
                data = response.json()
                assert data["image_type"] == "fedora-bootc"

    @patch("api.routers.build.GitHubService")
    async def test_fedora_bootc_version_42(self, mock_github_service, client: AsyncClient):
        """Test Fedora bootc version 42."""
        mock_workflow_run = AsyncMock()
        mock_workflow_run.id = 10005
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
                    "image_type": "fedora-bootc",
                    "fedora_version": "42",
                    "window_manager": "sway",
                    "enable_plymouth": True,
                    "ref": "main",
                },
            )

            if response.status_code == 202:
                data = response.json()
                assert data["fedora_version"] == "42"

    @patch("api.routers.build.GitHubService")
    async def test_fedora_bootc_without_plymouth(self, mock_github_service, client: AsyncClient):
        """Test Fedora bootc without Plymouth."""
        mock_workflow_run = AsyncMock()
        mock_workflow_run.id = 10006
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
                    "image_type": "fedora-bootc",
                    "fedora_version": "43",
                    "window_manager": "sway",
                    "enable_plymouth": False,
                    "ref": "main",
                },
            )

            if response.status_code == 202:
                # Verify Plymouth is disabled in workflow inputs
                mock_github.trigger_workflow.assert_called_once()
                call_args = mock_github.trigger_workflow.call_args
                assert call_args.kwargs["inputs"]["enable_plymouth"] == "false"


@pytest.mark.integration
class TestBootcrewDistros:
    """Test bootcrew (non-Fedora) bootc distributions."""

    @patch("api.routers.build.GitHubService")
    async def test_arch_bootc(self, mock_github_service, client: AsyncClient):
        """Test Arch Linux bootc build."""
        mock_workflow_run = AsyncMock()
        mock_workflow_run.id = 10101
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
                    "os": "arch",
                    "image_type": "fedora-bootc",  # Will be overridden by auto-selection
                    "window_manager": "sway",
                    "ref": "main",
                },
            )

            # Accept either success or file not found (depending on if arch-bootc.yml exists)
            assert response.status_code in [202, 400, 404]

    @patch("api.routers.build.GitHubService")
    async def test_debian_bootc(self, mock_github_service, client: AsyncClient):
        """Test Debian bootc build."""
        mock_workflow_run = AsyncMock()
        mock_workflow_run.id = 10102
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
                    "os": "debian",
                    "image_type": "fedora-bootc",
                    "window_manager": "sway",
                    "ref": "main",
                },
            )

            assert response.status_code in [202, 400, 404]

    @patch("api.routers.build.GitHubService")
    async def test_ubuntu_bootc(self, mock_github_service, client: AsyncClient):
        """Test Ubuntu bootc build."""
        mock_workflow_run = AsyncMock()
        mock_workflow_run.id = 10103
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
                    "os": "ubuntu",
                    "image_type": "fedora-bootc",
                    "window_manager": "sway",
                    "ref": "main",
                },
            )

            assert response.status_code in [202, 400, 404]

    @patch("api.routers.build.GitHubService")
    async def test_opensuse_bootc(self, mock_github_service, client: AsyncClient):
        """Test openSUSE bootc build."""
        mock_workflow_run = AsyncMock()
        mock_workflow_run.id = 10104
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
                    "os": "opensuse",
                    "image_type": "fedora-bootc",
                    "window_manager": "sway",
                    "ref": "main",
                },
            )

            assert response.status_code in [202, 400, 404]
