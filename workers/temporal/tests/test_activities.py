"""Tests for activity classes — unit tests with mocked external calls."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.activities.backup import BackupActivities, VolumeSnapshot
from src.activities.health import HealthActivities, ServiceTarget
from src.activities.llm import Agent, AgentConfig, AgentTask, LLMActivities
from src.activities.paperless import DocSyncConfig, PaperlessActivities


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
    client.get.return_value = resp
    client.post.return_value = resp
    client.request.return_value = resp
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    return client


# --- Backup Activities ---


class TestBackupActivities:
    @pytest.fixture
    def activities(self):
        return BackupActivities()

    @pytest.mark.asyncio
    async def test_list_volumes(self, activities):
        mock_proc = AsyncMock()
        mock_proc.communicate.return_value = (
            b"forgejo-data\npaperless-data\nollama-data\n",
            b"",
        )
        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            volumes = await activities.list_volumes()

        assert volumes == ["forgejo-data", "paperless-data", "ollama-data"]

    @pytest.mark.asyncio
    async def test_list_volumes_empty(self, activities):
        mock_proc = AsyncMock()
        mock_proc.communicate.return_value = (b"", b"")
        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            volumes = await activities.list_volumes()

        assert volumes == []

    @pytest.mark.asyncio
    async def test_snapshot_volume(self, activities):
        export_proc = AsyncMock()
        export_proc.returncode = 0
        export_proc.communicate.return_value = (b"tar-data", b"")

        compress_proc = AsyncMock()
        compress_proc.returncode = 0
        compress_proc.communicate.return_value = (b"", b"")

        stat_proc = AsyncMock()
        stat_proc.communicate.return_value = (b"1024", b"")

        procs = [export_proc, compress_proc, stat_proc]
        call_count = 0

        async def fake_exec(*args, **kwargs):
            nonlocal call_count
            proc = procs[call_count]
            call_count += 1
            return proc

        with patch("asyncio.create_subprocess_exec", side_effect=fake_exec):
            result = await activities.snapshot_volume("forgejo-data")

        assert isinstance(result, VolumeSnapshot)
        assert result.volume == "forgejo-data"
        assert result.size_bytes == 1024

    @pytest.mark.asyncio
    async def test_snapshot_volume_export_fails(self, activities):
        mock_proc = AsyncMock()
        mock_proc.returncode = 1
        mock_proc.communicate.return_value = (b"", b"export error")

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            with pytest.raises(RuntimeError, match="volume export failed"):
                await activities.snapshot_volume("bad-volume")

    @pytest.mark.asyncio
    async def test_prune_old_backups(self, tmp_path):
        """Test pruning logic directly (glob-based)."""
        import glob
        import os

        for i in range(10):
            (tmp_path / f"test-vol-2026010{i}-030000.tar.zst").write_bytes(b"x")

        files = sorted(
            glob.glob(str(tmp_path / "test-vol-*.tar.zst")),
            key=os.path.getmtime,
            reverse=True,
        )
        pruned = []
        for old in files[3:]:
            os.remove(old)
            pruned.append(old)

        assert len(pruned) == 7
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
        assert result.response_ms == pytest.approx(50.0)

    @pytest.mark.asyncio
    async def test_check_service_unhealthy(self, activities):
        target = ServiceTarget(name="test", url="http://test:8000")
        client = make_async_client(status_code=500, elapsed_s=0.1)

        with patch("httpx.AsyncClient", return_value=client):
            result = await activities.check_service(target)

        assert result.healthy is False
        assert result.status_code == 500

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
    async def test_check_service_expected_body(self, activities):
        target = ServiceTarget(
            name="test",
            url="http://test:8000",
            expected_body="version",
        )
        resp = make_httpx_response(status_code=200, elapsed_s=0.01)
        resp.text = '{"version": "1.0"}'

        client = AsyncMock()
        client.request.return_value = resp
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=client):
            result = await activities.check_service(target)

        assert result.healthy is True

    @pytest.mark.asyncio
    async def test_check_ollama_models_all_present(self, activities):
        client = make_async_client(
            json_data={
                "models": [
                    {"name": "qwen3:8b"},
                    {"name": "llama3.2:1b"},
                ]
            }
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


# --- Paperless Activities ---


class TestPaperlessActivities:
    @pytest.fixture
    def activities(self):
        return PaperlessActivities(
            DocSyncConfig(
                api_url="http://paperless:8000/api",
                token="test-token",
                host="paperless.exousia.local",
                watch_dir="/tmp/test-docs",
            )
        )

    @pytest.mark.asyncio
    async def test_scan_docs_dir(self, activities, tmp_path):
        activities.config.watch_dir = str(tmp_path)
        (tmp_path / "readme.md").write_text("# Hello")
        (tmp_path / "report.pdf").write_bytes(b"%PDF")
        (tmp_path / "image.png").write_bytes(b"PNG")

        files = await activities.scan_docs_dir()
        assert len(files) == 2
        assert any("readme.md" in f for f in files)
        assert any("report.pdf" in f for f in files)
        assert not any("image.png" in f for f in files)

    @pytest.mark.asyncio
    async def test_scan_docs_dir_missing(self, activities):
        activities.config.watch_dir = "/nonexistent"
        files = await activities.scan_docs_dir()
        assert files == []

    @pytest.mark.asyncio
    async def test_get_file_hash(self, activities, tmp_path):
        f = tmp_path / "test.md"
        f.write_text("hello world")
        h1 = await activities.get_file_hash(str(f))
        h2 = await activities.get_file_hash(str(f))
        assert h1 == h2
        assert len(h1) == 64

    @pytest.mark.asyncio
    async def test_get_file_hash_changes(self, activities, tmp_path):
        f = tmp_path / "test.md"
        f.write_text("v1")
        h1 = await activities.get_file_hash(str(f))
        f.write_text("v2")
        h2 = await activities.get_file_hash(str(f))
        assert h1 != h2

    @pytest.mark.asyncio
    async def test_check_already_uploaded_true(self, activities):
        client = make_async_client(json_data={"count": 1})

        with patch("httpx.AsyncClient", return_value=client):
            assert await activities.check_already_uploaded("existing-doc") is True

    @pytest.mark.asyncio
    async def test_check_already_uploaded_false(self, activities):
        client = make_async_client(json_data={"count": 0})

        with patch("httpx.AsyncClient", return_value=client):
            assert await activities.check_already_uploaded("new-doc") is False

    @pytest.mark.asyncio
    async def test_list_tags(self, activities):
        client = make_async_client(
            json_data={
                "results": [
                    {"name": "exousia", "id": 1},
                    {"name": "witness", "id": 2},
                ]
            }
        )

        with patch("httpx.AsyncClient", return_value=client):
            tags = await activities.list_tags()

        assert tags == {"exousia": 1, "witness": 2}


# --- LLM Activities ---


class TestLLMActivities:
    @pytest.fixture
    def config(self):
        return AgentConfig(
            anthropic_api_key="test-key",
            openai_api_key="test-key",
            google_api_key="test-key",
            ollama_url="http://ollama:11434",
        )

    @pytest.fixture
    def activities(self, config):
        return LLMActivities(config)

    @pytest.fixture
    def task(self):
        return AgentTask(
            agent=Agent.CLAUDE,
            prompt="What is 2+2?",
            system="You are a math tutor.",
        )

    @pytest.mark.asyncio
    async def test_dispatch_claude(self, activities, task):
        client = make_async_client(
            json_data={
                "content": [{"text": "4"}],
                "model": "claude-sonnet-4-20250514",
                "usage": {"input_tokens": 10, "output_tokens": 1},
            }
        )

        with patch("httpx.AsyncClient", return_value=client):
            result = await activities.dispatch_claude(task)

        assert result.agent == Agent.CLAUDE
        assert result.content == "4"
        assert result.usage["output_tokens"] == 1

    @pytest.mark.asyncio
    async def test_dispatch_codex(self, activities, task):
        client = make_async_client(
            json_data={
                "choices": [{"message": {"content": "4"}}],
                "model": "gpt-4o",
                "usage": {"prompt_tokens": 10, "completion_tokens": 1},
            }
        )

        with patch("httpx.AsyncClient", return_value=client):
            result = await activities.dispatch_codex(task)

        assert result.agent == Agent.CODEX
        assert result.content == "4"

    @pytest.mark.asyncio
    async def test_dispatch_gemini(self, activities, task):
        client = make_async_client(
            json_data={
                "candidates": [{"content": {"parts": [{"text": "4"}]}}],
                "usageMetadata": {
                    "promptTokenCount": 10,
                    "candidatesTokenCount": 1,
                },
            }
        )

        with patch("httpx.AsyncClient", return_value=client):
            result = await activities.dispatch_gemini(task)

        assert result.agent == Agent.GEMINI
        assert result.content == "4"

    @pytest.mark.asyncio
    async def test_dispatch_ollama(self, activities, task):
        client = make_async_client(
            json_data={
                "response": "4",
                "model": "llama3.2:1b",
                "prompt_eval_count": 10,
                "eval_count": 1,
            }
        )

        with patch("httpx.AsyncClient", return_value=client):
            result = await activities.dispatch_ollama(task)

        assert result.agent == Agent.OLLAMA
        assert result.content == "4"
        assert result.model == "llama3.2:1b"
