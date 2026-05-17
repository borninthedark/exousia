"""Base image mirror workflow — nightly pull and push to local registry."""

from datetime import timedelta

from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from src.activities.operations import OperationsActivities


@workflow.defn
class BaseImageMirrorWorkflow:
    """Pull latest Fedora base image and push to local registry.

    Schedule: daily 2 AM (before backup at 3 AM)
        spec=ScheduleSpec(cron_expressions=["0 2 * * *"])
    """

    @workflow.run
    async def run(self) -> dict:
        ops = OperationsActivities()

        source = "quay.io/fedora/fedora-sway-atomic:44"
        target = "localhost:5000/fedora-sway-atomic:44"

        # 1. Pull latest
        digest = await workflow.execute_activity_method(
            ops.pull_base_image,
            start_to_close_timeout=timedelta(minutes=15),
        )

        # 2. Push to local registry
        await workflow.execute_activity_method(
            ops.push_to_local_registry,
            args=[source, target],
            start_to_close_timeout=timedelta(minutes=10),
        )

        workflow.logger.info(f"Mirrored {source} → {target}")
        return {"source": source, "target": target, "digest": digest}
