"""Backup workflow — scheduled volume snapshots with pruning."""

from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from src.activities.backup import BackupActivities, BackupResult


@workflow.defn
class BackupWorkflow:
    """Snapshot all exousia volumes and prune old backups.

    Schedule via Temporal:
        client.create_schedule(
            "daily-backup",
            Schedule(action=ScheduleActionStartWorkflow(BackupWorkflow.run, ...)),
            spec=ScheduleSpec(cron_expressions=["0 3 * * *"]),  # 3 AM daily
        )
    """

    @workflow.run
    async def run(self, keep: int = 7) -> BackupResult:
        activities = BackupActivities()

        volumes = await workflow.execute_activity_method(
            activities.list_volumes,
            start_to_close_timeout=timedelta(seconds=30),
        )

        workflow.logger.info(f"Backing up {len(volumes)} volumes")

        snapshots = []
        pruned = []
        for volume in volumes:
            snap = await workflow.execute_activity_method(
                activities.snapshot_volume,
                volume,
                start_to_close_timeout=timedelta(minutes=30),
                retry_policy=RetryPolicy(maximum_attempts=3),
            )
            snapshots.append(snap)

            old = await workflow.execute_activity_method(
                activities.prune_old_backups,
                args=[volume, keep],
                start_to_close_timeout=timedelta(seconds=60),
            )
            pruned.extend(old)

        workflow.logger.info(f"Backup complete: {len(snapshots)} snapshots, {len(pruned)} pruned")
        return BackupResult(snapshots=snapshots, pruned=pruned)
