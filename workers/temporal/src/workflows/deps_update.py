"""Dependency update workflow — check for outdated packages weekly."""

from datetime import timedelta

from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from src.activities.operations import DepUpdate, OperationsActivities


@workflow.defn
class DepsUpdateWorkflow:
    """Check for outdated dependencies and create tracking issue.

    Schedule: weekly Wednesday 9 AM
        spec=ScheduleSpec(cron_expressions=["0 9 * * 3"])
    """

    @workflow.run
    async def run(self) -> dict:
        ops = OperationsActivities()

        # 1. Check Python deps
        outdated: list[DepUpdate] = await workflow.execute_activity_method(
            ops.check_python_deps,
            start_to_close_timeout=timedelta(seconds=60),
        )

        if not outdated:
            workflow.logger.info("All dependencies up to date")
            return {"outdated": 0}

        # 2. Create issue with update list
        body = "## Outdated Dependencies\n\n"
        body += "| Package | Current | Latest |\n|---|---|---|\n"
        for dep in outdated:
            body += f"| {dep.package} | {dep.current} | {dep.latest} |\n"

        await workflow.execute_activity_method(
            ops.create_forgejo_issue,
            args=[f"deps: {len(outdated)} packages outdated", body],
            start_to_close_timeout=timedelta(seconds=30),
        )

        workflow.logger.info(f"Created issue for {len(outdated)} outdated deps")
        return {"outdated": len(outdated)}
