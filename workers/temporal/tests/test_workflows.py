"""Tests for workflow definitions — verify structure and data models."""

from src.activities.llm import Agent, AgentConfig, AgentResponse, AgentTask
from src.workflows.backup import BackupWorkflow
from src.workflows.doc_sync import DEFAULT_SOURCES, DocSyncWorkflow, SyncDirectoryWorkflow
from src.workflows.health import HealthCheckWorkflow
from src.workflows.llm_pipeline import (
    LLMPipelineWorkflow,
    PipelineRequest,
    PipelineResult,
    Strategy,
)


class TestWorkflowDefinitions:
    """Verify workflow classes are properly decorated and discoverable."""

    def test_backup_workflow_defined(self):
        assert hasattr(BackupWorkflow, "__temporal_workflow_definition")

    def test_doc_sync_workflow_defined(self):
        assert hasattr(DocSyncWorkflow, "__temporal_workflow_definition")

    def test_sync_directory_workflow_defined(self):
        assert hasattr(SyncDirectoryWorkflow, "__temporal_workflow_definition")

    def test_health_check_workflow_defined(self):
        assert hasattr(HealthCheckWorkflow, "__temporal_workflow_definition")

    def test_llm_pipeline_workflow_defined(self):
        assert hasattr(LLMPipelineWorkflow, "__temporal_workflow_definition")


class TestDocSyncDefaults:
    """Verify doc sync source configuration."""

    def test_default_sources_count(self):
        assert len(DEFAULT_SOURCES) == 5

    def test_default_source_tags(self):
        tags = {s.tag for s in DEFAULT_SOURCES}
        assert tags == {"exousia", "witness", "sap-c02", "scs-c03", "ccsp"}

    def test_default_source_paths(self):
        for src in DEFAULT_SOURCES:
            assert src.path.startswith("/workspace/")


class TestPipelineDataModels:
    """Verify LLM pipeline data models."""

    def test_strategy_values(self):
        assert set(Strategy) == {
            Strategy.SINGLE,
            Strategy.FAN_OUT,
            Strategy.CHAIN,
            Strategy.DEBATE,
        }

    def test_agent_values(self):
        assert set(Agent) == {
            Agent.CLAUDE,
            Agent.CODEX,
            Agent.GEMINI,
            Agent.OLLAMA,
        }

    def test_pipeline_request_defaults(self):
        req = PipelineRequest(prompt="test")
        assert req.strategy == Strategy.FAN_OUT
        assert req.agents == [Agent.CLAUDE, Agent.CODEX, Agent.GEMINI]
        assert req.debate_rounds == 2
        assert req.temperature == 0.7

    def test_pipeline_request_custom(self):
        req = PipelineRequest(
            prompt="test",
            strategy=Strategy.SINGLE,
            agents=[Agent.OLLAMA],
            temperature=0.0,
        )
        assert req.strategy == Strategy.SINGLE
        assert req.agents == [Agent.OLLAMA]

    def test_pipeline_result(self):
        resp = AgentResponse(
            agent=Agent.CLAUDE,
            content="hello",
            model="test",
        )
        result = PipelineResult(
            strategy=Strategy.SINGLE,
            responses=[resp],
        )
        assert result.synthesis is None
        assert len(result.responses) == 1

    def test_agent_task(self):
        task = AgentTask(
            agent=Agent.GEMINI,
            prompt="analyze this",
            system="you are a researcher",
        )
        assert task.agent == Agent.GEMINI
        assert task.max_tokens == 4096

    def test_agent_config_defaults(self):
        config = AgentConfig()
        assert config.ollama_url == "http://ollama:11434"
        assert config.ollama_model == "llama3.2:1b"
        assert config.anthropic_model == "claude-sonnet-4-20250514"


class TestHealthServiceTargets:
    """Verify health check service targets."""

    def test_all_services_listed(self):
        from src.activities.health import SERVICES

        names = {s.name for s in SERVICES}
        assert "forgejo" in names
        assert "paperless" in names
        assert "temporal" in names
        assert "ollama" in names
        assert "caddy" in names

    def test_paperless_has_host_header(self):
        from src.activities.health import SERVICES

        paperless = next(s for s in SERVICES if s.name == "paperless")
        assert paperless.headers["Host"] == "paperless.exousia.local"

    def test_caddy_accepts_redirects(self):
        from src.activities.health import SERVICES

        caddy = next(s for s in SERVICES if s.name == "caddy")
        assert 308 in caddy.expected_status
