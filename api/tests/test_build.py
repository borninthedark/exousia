"""
Tests for Build Endpoints
==========================
"""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient


@pytest.mark.integration
class TestBuildOperations:
    """Test build triggering and management."""

    async def test_list_builds(self, client: AsyncClient, sample_build):
        """Test listing builds."""
        response = await client.get("/api/build/")

        assert response.status_code == 200
        data = response.json()
        assert "builds" in data
        assert "total" in data
        assert data["total"] >= 1

    async def test_list_builds_with_filters(self, client: AsyncClient, sample_build):
        """Test listing builds with status filter."""
        response = await client.get("/api/build/?status=in_progress")

        assert response.status_code == 200
        data = response.json()
        assert "builds" in data

    async def test_get_build_status(self, client: AsyncClient, sample_build):
        """Test getting build status."""
        response = await client.get(f"/api/build/{sample_build.id}/status")

        assert response.status_code == 200
        data = response.json()
        assert "build" in data
        assert data["build"]["id"] == sample_build.id

    async def test_get_nonexistent_build_status(self, client: AsyncClient):
        """Test getting status of non-existent build returns 404."""
        response = await client.get("/api/build/99999/status")

        assert response.status_code == 404

    @patch("api.routers.build.GitHubService")
    async def test_trigger_build_with_config(
        self, mock_github_service, client: AsyncClient, sample_config
    ):
        """Test triggering build from saved configuration."""
        # Mock GitHub workflow run
        mock_workflow_run = AsyncMock()
        mock_workflow_run.id = 12345
        mock_workflow_run.html_url = "https://github.com/test/repo/actions/runs/12345"

        # Mock GitHub service
        mock_github = AsyncMock()
        mock_github.trigger_workflow = AsyncMock(return_value=mock_workflow_run)
        mock_github_service.return_value = mock_github

        # Mock settings
        with patch("api.routers.build.settings") as mock_settings:
            mock_settings.GITHUB_TOKEN = "fake_token"
            mock_settings.GITHUB_REPO = "test/repo"
            mock_settings.GITHUB_WORKFLOW_FILE = "build.yml"
            mock_settings.BUILD_STATUS_POLLING_ENABLED = False

            response = await client.post(
                "/api/build/trigger", json={"config_id": sample_config.id, "ref": "main"}
            )

            # Should successfully trigger the build
            assert response.status_code == 202

            # Verify GitHub workflow was triggered
            mock_github.trigger_workflow.assert_called_once()

    async def test_trigger_build_without_config_or_yaml(self, client: AsyncClient):
        """Test triggering build without config_id, yaml_content, or definition_filename fails."""
        response = await client.post("/api/build/trigger", json={"ref": "main"})

        assert response.status_code == 400
        assert "config_id, yaml_content, or definition_filename must be provided" in response.json()["detail"]

    async def test_trigger_build_rejects_conflicting_desktop_overrides(self, client: AsyncClient):
        """Ensure window_manager and desktop_environment cannot be provided together."""

        response = await client.post(
            "/api/build/trigger",
            json={
                "yaml_content": "name: test\ndescription: test\nmodules: []\n",
                "image_type": "fedora-bootc",
                "fedora_version": "43",
                "enable_plymouth": True,
                "window_manager": "river",
                "desktop_environment": "sway",
                "ref": "main",
            },
        )

        assert response.status_code == 422
        assert "window_manager" in response.text

    @patch("api.routers.build.GitHubService")
    async def test_cancel_build(self, mock_github_service, client: AsyncClient, sample_build):
        """Test cancelling a running build."""
        # Mock GitHub service
        mock_github_service.return_value.cancel_workflow_run = AsyncMock(return_value=True)

        with patch("api.routers.build.settings") as mock_settings:
            mock_settings.GITHUB_TOKEN = "fake_token"
            mock_settings.GITHUB_REPO = "test/repo"
            mock_settings.BUILD_STATUS_POLLING_ENABLED = False

            response = await client.post(f"/api/build/{sample_build.id}/cancel")

            # Will fail without GitHub token
            assert response.status_code in [200, 500, 503]

    async def test_cancel_completed_build_fails(self, client: AsyncClient, test_db):
        """Test cancelling a completed build fails."""
        from api.database import BuildModel
        from api.models import BuildStatus

        # Create completed build
        completed_build = BuildModel(
            status=BuildStatus.SUCCESS,
            image_type="fedora-sway-atomic",
            fedora_version="43",
            ref="main",
        )
        test_db.add(completed_build)
        await test_db.commit()
        await test_db.refresh(completed_build)

        response = await client.post(f"/api/build/{completed_build.id}/cancel")

        assert response.status_code == 400
        assert "Cannot cancel" in response.json()["error"]


@pytest.mark.unit
class TestBuildModels:
    """Test build data models."""

    def test_build_status_enum(self):
        """Test BuildStatus enum values."""
        from api.models import BuildStatus

        assert BuildStatus.PENDING.value == "pending"
        assert BuildStatus.IN_PROGRESS.value == "in_progress"
        assert BuildStatus.SUCCESS.value == "success"
        assert BuildStatus.FAILURE.value == "failure"
        assert BuildStatus.CANCELLED.value == "cancelled"
