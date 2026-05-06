"""Exousia Temporal worker — registers all workflows and activities."""

import asyncio
import os

from temporalio.client import Client
from temporalio.worker import Worker

from src.activities import BackupActivities, HealthActivities, LLMActivities, PaperlessActivities
from src.activities.llm import AgentConfig
from src.activities.paperless import DocSyncConfig
from src.workflows import (
    BackupWorkflow,
    DocSyncWorkflow,
    HealthCheckWorkflow,
    LLMPipelineWorkflow,
    SyncDirectoryWorkflow,
)

TASK_QUEUE = "exousia"
TEMPORAL_HOST = os.getenv("TEMPORAL_HOST", "temporal-server:7233")


def build_activities() -> list:
    """Instantiate all activity classes with config from env."""
    paperless_config = DocSyncConfig(
        api_url=os.getenv("PAPERLESS_API_URL", "http://paperless:8000/api"),
        token=os.getenv("PAPERLESS_TOKEN", ""),
        host=os.getenv("PAPERLESS_HOST", "paperless.exousia.local"),
        watch_dir=os.getenv("DOCS_WATCH_DIR", "/workspace/docs"),
        tag_map={},  # populated dynamically by DocSyncWorkflow
    )

    llm_config = AgentConfig(
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY", ""),
        openai_api_key=os.getenv("OPENAI_API_KEY", ""),
        google_api_key=os.getenv("GOOGLE_API_KEY", ""),
        ollama_url=os.getenv("OLLAMA_URL", "http://ollama:11434"),
        ollama_model=os.getenv("OLLAMA_MODEL", "llama3.2:1b"),
    )

    return [
        BackupActivities(),
        PaperlessActivities(paperless_config),
        HealthActivities(),
        LLMActivities(llm_config),
    ]


async def main():
    client = await Client.connect(TEMPORAL_HOST)

    activities = build_activities()
    all_activities = []
    for act_instance in activities:
        for name in dir(act_instance):
            method = getattr(act_instance, name)
            if hasattr(method, "__temporal_activity_definition"):
                all_activities.append(method)

    worker = Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[
            BackupWorkflow,
            DocSyncWorkflow,
            SyncDirectoryWorkflow,
            HealthCheckWorkflow,
            LLMPipelineWorkflow,
        ],
        activities=all_activities,
    )

    print(f"Worker started on queue={TASK_QUEUE} server={TEMPORAL_HOST}")
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
