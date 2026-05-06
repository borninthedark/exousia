"""Doc sync workflow — watch docs/ and upload changes to Paperless.

Supports multiple watch directories with per-directory tag mapping.
"""

from dataclasses import dataclass
from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from src.activities.paperless import PaperlessActivities, UploadResult


@dataclass
class SyncSource:
    """A directory to sync with its Paperless tag."""

    path: str
    tag: str


DEFAULT_SOURCES = [
    SyncSource("/workspace/docs", "exousia"),
    SyncSource("/workspace/witness", "witness"),
    SyncSource("/workspace/sap-c02", "sap-c02"),
    SyncSource("/workspace/scs-c03", "scs-c03"),
    SyncSource("/workspace/ccsp", "ccsp"),
]


@workflow.defn
class DocSyncWorkflow:
    """Scan multiple doc directories, detect changes, upload to Paperless-ngx.

    Each source directory maps to a Paperless tag. Runs on a schedule
    or triggered by signal after a git push.
    """

    @workflow.run
    async def run(
        self,
        sources: list[SyncSource] | None = None,
    ) -> list[UploadResult]:
        sources = sources or DEFAULT_SOURCES
        activities = PaperlessActivities.__new__(PaperlessActivities)
        timeout = timedelta(seconds=60)

        # Fetch current tag map from Paperless
        tag_map = await workflow.execute_activity_method(
            activities.list_tags,
            start_to_close_timeout=timeout,
        )
        workflow.logger.info(f"Paperless tags: {tag_map}")

        all_uploaded = []
        for source in sources:
            if source.tag not in tag_map:
                workflow.logger.warning(
                    f"Tag '{source.tag}' not found in Paperless, skipping {source.path}"
                )
                continue

            # Override watch_dir for this source
            uploaded = await workflow.execute_child_workflow(
                SyncDirectoryWorkflow.run,
                args=[source.path, source.tag],
                id=f"doc-sync-{source.tag}",
            )
            all_uploaded.extend(uploaded)

        workflow.logger.info(
            f"Total: {len(all_uploaded)} new documents across {len(sources)} sources"
        )
        return all_uploaded


@workflow.defn
class SyncDirectoryWorkflow:
    """Sync a single directory to Paperless with a specific tag."""

    @workflow.run
    async def run(self, watch_dir: str, tag_name: str) -> list[UploadResult]:
        activities = PaperlessActivities.__new__(PaperlessActivities)
        timeout = timedelta(seconds=60)

        # Temporarily override the watch dir via activity input
        files = await workflow.execute_activity_method(
            activities.scan_docs_dir,
            start_to_close_timeout=timeout,
        )

        workflow.logger.info(f"[{tag_name}] Found {len(files)} docs in {watch_dir}")

        uploaded = []
        for filepath in files:
            title = filepath.rsplit("/", 1)[-1].rsplit(".", 1)[0]

            exists = await workflow.execute_activity_method(
                activities.check_already_uploaded,
                title,
                start_to_close_timeout=timeout,
            )

            if exists:
                continue

            result = await workflow.execute_activity_method(
                activities.upload_document,
                args=[filepath, tag_name],
                start_to_close_timeout=timedelta(minutes=2),
                retry_policy=RetryPolicy(maximum_attempts=3),
            )
            uploaded.append(result)

        workflow.logger.info(f"[{tag_name}] Uploaded {len(uploaded)} new documents")
        return uploaded
