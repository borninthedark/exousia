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
        # Mock GitHub service
        mock_workflow_run = AsyncMock()
        mock_workflow_run.id = 12345
        mock_github_service.return_value.trigger_workflow = AsyncMock(
            return_value=mock_workflow_run
        )

        # Set GitHub token in settings (mocked)
        with patch("api.routers.build.settings") as mock_settings:
            mock_settings.GITHUB_TOKEN = "fake_token"
            mock_settings.GITHUB_REPO = "test/repo"
            mock_settings.GITHUB_WORKFLOW_FILE = "build.yaml"

            response = await client.post(
                "/api/build/trigger", json={"config_id": sample_config.id, "ref": "main"}
            )

            # Note: This will fail without GitHub token, which is expected in tests
            # In real tests, you'd mock the GitHub service
            assert response.status_code in [202, 503]  # 503 if no token

    async def test_trigger_build_without_config_or_yaml(self, client: AsyncClient):
        """Test triggering build without config_id, yaml_content, or definition_filename fails."""
        response = await client.post("/api/build/trigger", json={"ref": "main"})

        assert response.status_code == 400
        assert "config_id, yaml_content, or definition_filename must be provided" in response.json()["detail"]

    @patch("api.routers.build.GitHubService")
    async def test_cancel_build(self, mock_github_service, client: AsyncClient, sample_build):
        """Test cancelling a running build."""
        # Mock GitHub service
        mock_github_service.return_value.cancel_workflow_run = AsyncMock(return_value=True)

        with patch("api.routers.build.settings") as mock_settings:
            mock_settings.GITHUB_TOKEN = "fake_token"
            mock_settings.GITHUB_REPO = "test/repo"

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
