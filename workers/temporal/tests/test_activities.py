"""Tests for activity classes — unit tests with mocked external calls."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.activities.backup import BackupActivities, VolumeSnapshot
from src.activities.container_lifecycle import ContainerLifecycleActivities
from src.activities.cve_check import CVECheckActivities
from src.activities.health import HealthActivities, ServiceTarget
from src.activities.incident import IncidentActivities, IncidentContext
from src.activities.llm import Agent, AgentConfig, AgentTask, LLMActivities
from src.activities.miniflux import MinifluxActivities
from src.activities.observe import ObserveActivities
from src.activities.operations import OperationsActivities
from src.activities.paperless import DocSyncConfig, PaperlessActivities
from src.clients.forgejo import ForgejoClient
from src.clients.podman import PodmanClient
from src.clients.systemd import SystemdClient


def make_httpx_response(status_code=200, json_data=None, text="", elapsed_s=0.05):
    """Create a mock httpx response with sync json() and proper elapsed."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    resp.text = text
    resp.raise_for_status = MagicMock()
    elapsed = MagicMock()
    elapsed.total_seconds.return_value = elapsed_s
    resp.elapsed = elapsed
    return resp


def make_async_client(**kwargs):
    """Create a mock async httpx client context manager."""
    resp = make_httpx_response(**kwargs)
    client = AsyncMock()
    client.get = AsyncMock(return_value=resp)
    client.post = AsyncMock(return_value=resp)
    client.put = AsyncMock(return_value=resp)
    client.request = AsyncMock(return_value=resp)
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    return client


# --- Backup Activities ---


class TestBackupActivities:
    @pytest.fixture
    def activities(self):
        act = BackupActivities()
        act.podman = MagicMock(spec=PodmanClient)
        return act

    @pytest.mark.asyncio
    async def test_list_volumes(self, activities):
        activities.podman.list_volumes = AsyncMock(
            return_value=["forgejo-data", "paperless-data"]
        )
        volumes = await activities.list_volumes()
        assert volumes == ["forgejo-data", "paperless-data"]

    @pytest.mark.asyncio
    async def test_list_volumes_empty(self, activities):
        activities.podman.list_volumes = AsyncMock(return_value=[])
        volumes = await activities.list_volumes()
        assert volumes == []

    @pytest.mark.asyncio
    async def test_snapshot_volume(self, activities, tmp_path):
        activities.backup_dir = str(tmp_path)
        activities.podman.export_volume = AsyncMock(return_value=b"fake-tar-data")

        result = await activities.snapshot_volume("test-vol")
        assert isinstance(result, VolumeSnapshot)
        assert result.volume == "test-vol"
        assert result.size_bytes > 0

    @pytest.mark.asyncio
    async def test_prune_old_backups(self, tmp_path):
        act = BackupActivities()
        act.backup_dir = str(tmp_path)

        for i in range(10):
            (tmp_path / f"test-vol-2026010{i}-030000.tar.zst").write_bytes(b"x")

        pruned = await act.prune_old_backups("test-vol", keep=3)
        assert len(pruned) == 7

        import glob

        remaining = glob.glob(str(tmp_path / "test-vol-*.tar.zst"))
        assert len(remaining) == 3


# --- Health Activities ---


class TestHealthActivities:
    @pytest.fixture
    def activities(self):
        return HealthActivities()

    @pytest.mark.asyncio
    async def test_check_service_healthy(self, activities):
        target = ServiceTarget(name="test", url="http://test:8000")
        client = make_async_client(status_code=200, elapsed_s=0.05)

        with patch("httpx.AsyncClient", return_value=client):
            result = await activities.check_service(target)

        assert result.healthy is True
        assert result.status_code == 200

    @pytest.mark.asyncio
    async def test_check_service_unhealthy(self, activities):
        target = ServiceTarget(name="test", url="http://test:8000")
        client = make_async_client(status_code=500, elapsed_s=0.1)

        with patch("httpx.AsyncClient", return_value=client):
            result = await activities.check_service(target)

        assert result.healthy is False

    @pytest.mark.asyncio
    async def test_check_service_connection_error(self, activities):
        target = ServiceTarget(name="test", url="http://unreachable:9999")
        client = AsyncMock()
        client.request.side_effect = ConnectionError("refused")
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=client):
            result = await activities.check_service(target)

        assert result.healthy is False
        assert "refused" in result.error

    @pytest.mark.asyncio
    async def test_check_ollama_models_all_present(self, activities):
        client = make_async_client(
            json_data={"models": [{"name": "qwen3:8b"}, {"name": "llama3.2:1b"}]}
        )
        with patch("httpx.AsyncClient", return_value=client):
            result = await activities.check_ollama_models()
        assert result.healthy is True

    @pytest.mark.asyncio
    async def test_check_ollama_models_missing(self, activities):
        client = make_async_client(json_data={"models": [{"name": "qwen3:8b"}]})
        with patch("httpx.AsyncClient", return_value=client):
            result = await activities.check_ollama_models()
        assert result.healthy is False
        assert "llama3.2:1b" in result.error


# --- Container Lifecycle Activities ---


class TestContainerLifecycleActivities:
    @pytest.fixture
    def activities(self):
        act = ContainerLifecycleActivities()
        act.podman = MagicMock(spec=PodmanClient)
        act.systemd = MagicMock(spec=SystemdClient)
        return act

    @pytest.mark.asyncio
    async def test_check_updates(self, activities):
        activities.podman.check_image_updates = AsyncMock(
            return_value=[
                {"container": "forgejo", "image": "codeberg.org/forgejo/forgejo:latest", "local_digest": "abc"},
            ]
        )
        updates = await activities.check_updates()
        assert len(updates) == 1
        assert updates[0].container == "forgejo"
        assert updates[0].updated is True

    @pytest.mark.asyncio
    async def test_pull_image(self, activities):
        activities.podman.pull_image = AsyncMock(return_value="sha256:abc123")
        result = await activities.pull_image("alpine:latest")
        assert result == "sha256:abc123"

    @pytest.mark.asyncio
    async def test_restart_service_healthy(self, activities):
        activities.systemd.restart_container = AsyncMock(return_value=True)
        activities.podman.healthcheck_run = AsyncMock(return_value=True)

        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await activities.restart_service("forgejo")

        assert result.healthy is True
        assert result.container == "forgejo"

    @pytest.mark.asyncio
    async def test_restart_service_unhealthy(self, activities):
        activities.systemd.restart_container = AsyncMock(return_value=True)
        activities.podman.healthcheck_run = AsyncMock(return_value=False)

        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await activities.restart_service("bad-service")

        assert result.healthy is False

    @pytest.mark.asyncio
    async def test_restart_service_fails(self, activities):
        activities.systemd.restart_container = AsyncMock(return_value=False)

        result = await activities.restart_service("dead-service")
        assert result.healthy is False
        assert "restart failed" in result.error

    @pytest.mark.asyncio
    async def test_prune_images(self, activities):
        activities.podman.prune_images = AsyncMock(return_value=["img1", "img2"])
        result = await activities.prune_images()
        assert "2 images pruned" in result


# --- CVE Check Activities ---


class TestCVECheckActivities:
    @pytest.fixture
    def activities(self):
        act = CVECheckActivities()
        act.forgejo = MagicMock(spec=ForgejoClient)
        return act

    @pytest.mark.asyncio
    async def test_check_upstream_releases_fixed(self, activities):
        client = make_async_client(
            json_data=[{"tag_name": "v1.80.0"}]
        )
        with patch("httpx.AsyncClient", return_value=client):
            results = await activities.check_upstream_releases()

        assert len(results) == 1
        assert results[0].fixed_upstream is True

    @pytest.mark.asyncio
    async def test_check_upstream_releases_not_fixed(self, activities):
        client = make_async_client(
            json_data=[{"tag_name": "v1.72.2"}]
        )
        with patch("httpx.AsyncClient", return_value=client):
            results = await activities.check_upstream_releases()

        assert len(results) == 1
        assert results[0].fixed_upstream is False

    @pytest.mark.asyncio
    async def test_create_cve_issue(self, activities):
        activities.forgejo.create_issue = AsyncMock(return_value="http://issue/1")
        url = await activities.create_cve_issue("CVE title", "body")
        assert url == "http://issue/1"


# --- Incident Activities ---


class TestIncidentActivities:
    @pytest.fixture
    def activities(self):
        act = IncidentActivities()
        act.systemd = MagicMock(spec=SystemdClient)
        act.forgejo = MagicMock(spec=ForgejoClient)
        return act

    @pytest.mark.asyncio
    async def test_query_recent_logs(self, activities):
        client = make_async_client(
            json_data={"hits": [
                {"message": "error: something broke"},
                {"message": "warn: disk full"},
            ]}
        )
        with patch("httpx.AsyncClient", return_value=client):
            logs = await activities.query_recent_logs("immich", 5)
        assert len(logs) == 2
        assert "something broke" in logs[0]

    @pytest.mark.asyncio
    async def test_diagnose_with_llm(self, activities):
        client = make_async_client(
            json_data={"response": "DIAGNOSIS: OOM kill. ACTION: restart"}
        )
        context = IncidentContext(
            container="immich", trigger="unhealthy", logs=["OOM killed"]
        )
        with patch("httpx.AsyncClient", return_value=client):
            result = await activities.diagnose_with_llm(context)
        assert "restart" in result.lower()

    @pytest.mark.asyncio
    async def test_restart_container_success(self, activities):
        activities.systemd.restart_container = AsyncMock(return_value=True)
        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await activities.restart_container("immich")
        assert result.success is True
        assert result.action == "restarted"

    @pytest.mark.asyncio
    async def test_restart_container_failure(self, activities):
        activities.systemd.restart_container = AsyncMock(return_value=False)
        result = await activities.restart_container("dead")
        assert result.success is False

    @pytest.mark.asyncio
    async def test_create_incident_issue(self, activities):
        activities.forgejo.create_issue = AsyncMock(return_value="http://issue/5")
        context = IncidentContext(
            container="immich",
            trigger="error_spike",
            logs=["err1"],
            diagnosis="needs investigation",
        )
        result = await activities.create_incident_issue(context)
        assert result.success is True
        assert result.action == "issue_created"


# --- Operations Activities ---


class TestOperationsActivities:
    @pytest.fixture
    def activities(self):
        act = OperationsActivities()
        act.podman = MagicMock(spec=PodmanClient)
        act.forgejo = MagicMock(spec=ForgejoClient)
        return act

    @pytest.mark.asyncio
    async def test_scan_running_images_delegation(self, activities):
        activities.podman.list_containers = AsyncMock(
            return_value=[{"name": "test", "image": "test:latest"}]
        )
        results = await activities.scan_running_images()
        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_scan_running_images(self, activities):
        activities.podman.list_containers = AsyncMock(
            return_value=[
                {"name": "forgejo", "image": "codeberg.org/forgejo/forgejo:14"},
            ]
        )
        results = await activities.scan_running_images()
        assert len(results) == 1
        assert results[0].container == "forgejo"

    @pytest.mark.asyncio
    async def test_get_open_prs(self, activities):
        activities.forgejo.get_open_prs = AsyncMock(
            return_value=[{"number": "1", "title": "fix", "url": "http://x"}]
        )
        prs = await activities.get_open_prs()
        assert len(prs) == 1

    @pytest.mark.asyncio
    async def test_check_python_deps(self, activities):
        mock_proc = AsyncMock()
        mock_proc.communicate.return_value = (
            b'[{"name":"httpx","version":"0.27.0","latest_version":"0.28.0"}]',
            b"",
        )
        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            deps = await activities.check_python_deps()
        assert len(deps) == 1
        assert deps[0].package == "httpx"


# --- Miniflux Activities ---


class TestMinifluxActivities:
    @pytest.fixture
    def activities(self):
        return MinifluxActivities()

    @pytest.mark.asyncio
    async def test_fetch_unread_entries(self, activities):
        client = make_async_client(
            json_data={
                "entries": [
                    {
                        "id": 1,
                        "title": "Test Article",
                        "url": "http://example.com",
                        "feed": {"title": "Test Feed"},
                        "content": "body",
                    }
                ]
            }
        )
        with patch("httpx.AsyncClient", return_value=client):
            entries = await activities.fetch_unread_entries(10)
        assert len(entries) == 1
        assert entries[0]["title"] == "Test Article"


# --- Observe Activities ---


class TestObserveActivities:
    @pytest.fixture
    def activities(self):
        return ObserveActivities()

    @pytest.mark.asyncio
    async def test_check_error_rate(self, activities):
        client = make_async_client(
            json_data={"hits": [
                {"container": "k3s", "count": 5000},
                {"container": "forgejo", "count": 100},
            ]}
        )
        with patch("httpx.AsyncClient", return_value=client):
            rates = await activities.check_error_rate(15)
        assert rates["k3s"] == 5000
        assert rates["forgejo"] == 100


# --- Paperless Activities ---


class TestPaperlessActivities:
    @pytest.fixture
    def activities(self):
        act = PaperlessActivities(
            DocSyncConfig(
                api_url="http://paperless:8000/api",
                token="test-token",
                host="paperless.exousia.local",
                watch_dir="/tmp/test-docs",
            )
        )
        act.forgejo = MagicMock(spec=ForgejoClient)
        return act

    @pytest.mark.asyncio
    async def test_scan_docs_dir(self, activities, tmp_path):
        activities.config.watch_dir = str(tmp_path)
        (tmp_path / "readme.md").write_text("# Hello")
        (tmp_path / "report.pdf").write_bytes(b"%PDF")
        (tmp_path / "image.png").write_bytes(b"PNG")

        files = await activities.scan_docs_dir()
        assert len(files) == 2
        assert not any("image.png" in f for f in files)

    @pytest.mark.asyncio
    async def test_list_tags(self, activities):
        client = make_async_client(
            json_data={"results": [{"name": "exousia", "id": 1}, {"name": "witness", "id": 2}]}
        )
        with patch("httpx.AsyncClient", return_value=client):
            tags = await activities.list_tags()
        assert tags == {"exousia": 1, "witness": 2}

    @pytest.mark.asyncio
    async def test_create_forgejo_issue_from_doc(self, activities):
        activities.forgejo.create_issue = AsyncMock(return_value="http://issue/3")
        doc = {"id": "42", "title": "Invoice", "url": "http://x", "created": "2026-01-01"}
        url = await activities.create_forgejo_issue_from_doc(doc)
        assert url == "http://issue/3"

    @pytest.mark.asyncio
    async def test_check_closed_issues_for_docs(self, activities):
        activities.forgejo.get_closed_issues = AsyncMock(
            return_value=[
                {
                    "number": "5",
                    "title": "done",
                    "body": "Paperless ID: 42",
                    "html_url": "http://x/5",
                }
            ]
        )
        closed = await activities.check_closed_issues_for_docs()
        assert len(closed) == 1
        assert closed[0]["doc_id"] == "42"


# --- LLM Activities ---


class TestLLMActivities:
    @pytest.fixture
    def activities(self):
        return LLMActivities(
            AgentConfig(
                anthropic_api_key="test-key",
                openai_api_key="test-key",
                google_api_key="test-key",
            )
        )

    @pytest.mark.asyncio
    async def test_dispatch_ollama(self, activities):
        client = make_async_client(
            json_data={
                "response": "4",
                "model": "llama3.2:1b",
                "prompt_eval_count": 10,
                "eval_count": 1,
            }
        )
        task = AgentTask(agent=Agent.OLLAMA, prompt="2+2")
        with patch("httpx.AsyncClient", return_value=client):
            result = await activities.dispatch_ollama(task)
        assert result.content == "4"
        assert result.model == "llama3.2:1b"

    @pytest.mark.asyncio
    async def test_dispatch_claude(self, activities):
        client = make_async_client(
            json_data={
                "content": [{"text": "4"}],
                "model": "claude-sonnet-4-20250514",
                "usage": {"input_tokens": 10, "output_tokens": 1},
            }
        )
        task = AgentTask(agent=Agent.CLAUDE, prompt="2+2")
        with patch("httpx.AsyncClient", return_value=client):
            result = await activities.dispatch_claude(task)
        assert result.content == "4"
        assert result.agent == Agent.CLAUDE
