"""Tests for API client classes — PodmanClient, ForgejoClient, SystemdClient."""

from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from src.clients.forgejo import ForgejoClient
from src.clients.podman import PodmanClient
from src.clients.systemd import SystemdClient


def mock_response(status_code=200, json_data=None, text="", content=b""):
    """Create a mock httpx response."""
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    resp.text = text
    resp.content = content
    resp.raise_for_status = MagicMock()
    if status_code >= 400:
        resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "error", request=MagicMock(), response=resp
        )
    return resp


def make_mock_client(response):
    """Create a mock async client that returns the given response."""
    client = AsyncMock()
    client.get = AsyncMock(return_value=response)
    client.post = AsyncMock(return_value=response)
    client.patch = AsyncMock(return_value=response)
    client.delete = AsyncMock(return_value=response)
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    return client


# --- PodmanClient ---


class TestPodmanClient:
    @pytest.fixture
    def client(self):
        return PodmanClient(socket_path="/tmp/fake.sock")

    @pytest.mark.asyncio
    async def test_list_containers(self, client, monkeypatch):
        resp = mock_response(json_data=[
            {"Names": ["forgejo"], "Image": "codeberg.org/forgejo/forgejo:14"},
            {"Names": ["caddy"], "Image": "docker.io/library/caddy:2-alpine"},
        ])
        mock = make_mock_client(resp)
        monkeypatch.setattr(client, "_client", lambda: mock)

        containers = await client.list_containers()
        assert len(containers) == 2
        assert containers[0]["name"] == "forgejo"
        assert containers[1]["image"] == "docker.io/library/caddy:2-alpine"

    @pytest.mark.asyncio
    async def test_healthcheck_run_healthy(self, client, monkeypatch):
        resp = mock_response(json_data={"Status": "healthy"})
        mock = make_mock_client(resp)
        monkeypatch.setattr(client, "_client", lambda: mock)

        assert await client.healthcheck_run("forgejo") is True

    @pytest.mark.asyncio
    async def test_healthcheck_run_unhealthy(self, client, monkeypatch):
        resp = mock_response(json_data={"Status": "unhealthy"})
        mock = make_mock_client(resp)
        monkeypatch.setattr(client, "_client", lambda: mock)

        assert await client.healthcheck_run("forgejo") is False

    @pytest.mark.asyncio
    async def test_healthcheck_run_not_found(self, client, monkeypatch):
        resp = mock_response(status_code=404)
        mock = make_mock_client(resp)
        monkeypatch.setattr(client, "_client", lambda: mock)

        assert await client.healthcheck_run("nonexistent") is False

    @pytest.mark.asyncio
    async def test_pull_image(self, client, monkeypatch):
        resp = mock_response(text='{"id":"abc123"}\n')
        mock = make_mock_client(resp)
        monkeypatch.setattr(client, "_client", lambda: mock)

        image_id = await client.pull_image("docker.io/library/alpine:3")
        assert image_id == "abc123"

    @pytest.mark.asyncio
    async def test_prune_images(self, client, monkeypatch):
        resp = mock_response(json_data=[
            {"Id": "abc123"},
            {"Id": "def456"},
        ])
        mock = make_mock_client(resp)
        monkeypatch.setattr(client, "_client", lambda: mock)

        pruned = await client.prune_images()
        assert pruned == ["abc123", "def456"]

    @pytest.mark.asyncio
    async def test_list_volumes(self, client, monkeypatch):
        resp = mock_response(json_data=[
            {"Name": "forgejo-data"},
            {"Name": "paperless-data"},
        ])
        mock = make_mock_client(resp)
        monkeypatch.setattr(client, "_client", lambda: mock)

        volumes = await client.list_volumes()
        assert volumes == ["forgejo-data", "paperless-data"]

    @pytest.mark.asyncio
    async def test_export_volume(self, client, monkeypatch):
        resp = mock_response(content=b"tar-archive-data")
        mock = make_mock_client(resp)
        monkeypatch.setattr(client, "_client", lambda: mock)

        data = await client.export_volume("forgejo-data")
        assert data == b"tar-archive-data"


# --- ForgejoClient ---


class TestForgejoClient:
    @pytest.fixture
    def client(self):
        return ForgejoClient(
            api_url="http://forgejo:3000/api/v1",
            token="test-token",
            repo="uryu/exousia",
        )

    @pytest.mark.asyncio
    async def test_create_issue(self, client, monkeypatch):
        resp = mock_response(
            status_code=201,
            json_data={"html_url": "http://forgejo:3000/uryu/exousia/issues/42"},
        )
        mock = make_mock_client(resp)
        monkeypatch.setattr(client, "_client", lambda: mock)

        url = await client.create_issue("test title", "test body")
        assert "issues/42" in url

    @pytest.mark.asyncio
    async def test_create_issue_failure(self, client, monkeypatch):
        resp = mock_response(status_code=500)
        mock = make_mock_client(resp)
        monkeypatch.setattr(client, "_client", lambda: mock)

        with pytest.raises(RuntimeError, match="Failed to create issue"):
            await client.create_issue("test", "body")

    @pytest.mark.asyncio
    async def test_get_latest_tag(self, client, monkeypatch):
        resp = mock_response(json_data=[{"tag_name": "v0.5.0"}])
        mock = make_mock_client(resp)
        monkeypatch.setattr(client, "_client", lambda: mock)

        tag = await client.get_latest_tag()
        assert tag == "v0.5.0"

    @pytest.mark.asyncio
    async def test_get_latest_tag_none(self, client, monkeypatch):
        resp = mock_response(json_data=[])
        mock = make_mock_client(resp)
        monkeypatch.setattr(client, "_client", lambda: mock)

        tag = await client.get_latest_tag()
        assert tag == ""

    @pytest.mark.asyncio
    async def test_get_open_prs(self, client, monkeypatch):
        resp = mock_response(json_data=[
            {"number": 1, "title": "fix: thing", "html_url": "http://x/1"},
            {"number": 2, "title": "feat: other", "html_url": "http://x/2"},
        ])
        mock = make_mock_client(resp)
        monkeypatch.setattr(client, "_client", lambda: mock)

        prs = await client.get_open_prs()
        assert len(prs) == 2
        assert prs[0]["number"] == "1"
        assert prs[1]["title"] == "feat: other"

    @pytest.mark.asyncio
    async def test_get_pr_diff(self, client, monkeypatch):
        resp = mock_response(text="diff --git a/file.py b/file.py\n+new line")
        mock = make_mock_client(resp)
        monkeypatch.setattr(client, "_client", lambda: mock)

        diff = await client.get_pr_diff("1")
        assert "diff --git" in diff

    @pytest.mark.asyncio
    async def test_get_closed_issues(self, client, monkeypatch):
        resp = mock_response(json_data=[
            {"number": 5, "title": "done", "body": "Paperless ID: 42", "html_url": "http://x/5"},
        ])
        mock = make_mock_client(resp)
        monkeypatch.setattr(client, "_client", lambda: mock)

        issues = await client.get_closed_issues()
        assert len(issues) == 1
        assert "Paperless ID: 42" in issues[0]["body"]


# --- SystemdClient ---


class TestSystemdClient:
    @pytest.fixture
    def client(self):
        return SystemdClient(socket_path="/tmp/fake.sock")

    @pytest.mark.asyncio
    async def test_restart_container_success(self, client, monkeypatch):
        resp = mock_response(status_code=204)
        mock = make_mock_client(resp)
        monkeypatch.setattr(client, "_client", lambda: mock)

        assert await client.restart_container("forgejo") is True

    @pytest.mark.asyncio
    async def test_restart_container_failure(self, client, monkeypatch):
        resp = mock_response(status_code=500)
        mock = make_mock_client(resp)
        monkeypatch.setattr(client, "_client", lambda: mock)

        assert await client.restart_container("bad") is False

    @pytest.mark.asyncio
    async def test_stop_container(self, client, monkeypatch):
        resp = mock_response(status_code=204)
        mock = make_mock_client(resp)
        monkeypatch.setattr(client, "_client", lambda: mock)

        assert await client.stop_container("forgejo") is True

    @pytest.mark.asyncio
    async def test_start_container(self, client, monkeypatch):
        resp = mock_response(status_code=204)
        mock = make_mock_client(resp)
        monkeypatch.setattr(client, "_client", lambda: mock)

        assert await client.start_container("forgejo") is True
