"""Disaster recovery drill — backup, verify, and report."""

import asyncio
from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from src.activities.backup import BackupActivities, BackupResult, VolumeSnapshot
    from src.activities.health import HealthActivities, HealthResult, SERVICES
    from src.activities.alert import AlertActivities, AlertPayload
    from src.activities.operations import OperationsActivities


@workflow.defn
class DRDrillWorkflow:
    """Disaster recovery drill: backup all, verify integrity, report.

    This is a read-only drill — it does NOT stop/restore services.
    It verifies that backups are producible and complete.

    Schedule: monthly 15th at 2 AM (or on-demand)
        spec=ScheduleSpec(cron_expressions=["0 2 15 * *"])
    """

    @workflow.run
    async def run(self) -> str:
        backup = BackupActivities()
        health = HealthActivities()
        ops = OperationsActivities()
        alert = AlertActivities()
        timeout = timedelta(minutes=30)
        retry = RetryPolicy(maximum_attempts=2)

        report = "# Disaster Recovery Drill Report\n\n"
        issues = []

        # 1. Pre-drill health check
        report += "## Pre-Drill Health\n\n"
        pre_results: list[HealthResult] = []
        for target in SERVICES:
            result = await workflow.execute_activity_method(
                health.check_service,
                target,
                start_to_close_timeout=timedelta(seconds=30),
            )
            pre_results.append(result)

        pre_healthy = sum(1 for r in pre_results if r.healthy)
        report += f"- Services healthy: {pre_healthy}/{len(pre_results)}\n"
        for r in pre_results:
            if not r.healthy:
                report += f"- **UNHEALTHY:** {r.name} — {r.error}\n"
                issues.append(f"{r.name} unhealthy before drill")
        report += "\n"

        # 2. Backup all volumes
        report += "## Volume Backups\n\n"
        volumes = await workflow.execute_activity_method(
            backup.list_volumes,
            start_to_close_timeout=timedelta(seconds=30),
        )
        report += f"- Volumes to back up: {len(volumes)}\n\n"

        snapshots: list[VolumeSnapshot] = []
        failed_volumes: list[str] = []

        for volume in volumes:
            try:
                snap = await workflow.execute_activity_method(
                    backup.snapshot_volume,
                    volume,
                    start_to_close_timeout=timeout,
                    retry_policy=retry,
                )
                snapshots.append(snap)
            except Exception as e:
                failed_volumes.append(volume)
                issues.append(f"Backup failed: {volume} — {e}")

        report += "| Volume | Size | Status |\n|---|---|---|\n"
        for snap in snapshots:
            size_mb = round(snap.size_bytes / 1_048_576, 1)
            report += f"| {snap.volume} | {size_mb} MB | OK |\n"
        for vol in failed_volumes:
            report += f"| {vol} | — | **FAILED** |\n"
        report += "\n"

        total_size = sum(s.size_bytes for s in snapshots)
        report += f"- **Total backup size:** {round(total_size / 1_073_741_824, 2)} GB\n"
        report += f"- **Successful:** {len(snapshots)}/{len(volumes)}\n"
        report += f"- **Failed:** {len(failed_volumes)}\n\n"

        # 3. Verify backup integrity (check files exist and are non-zero)
        report += "## Integrity Verification\n\n"
        zero_size = [s for s in snapshots if s.size_bytes == 0]
        if zero_size:
            report += f"- **WARNING:** {len(zero_size)} backups have zero size\n"
            for s in zero_size:
                issues.append(f"Zero-size backup: {s.volume}")
        else:
            report += "- All backups have non-zero size\n"
        report += "\n"

        # 4. Post-drill health check (verify nothing broke)
        report += "## Post-Drill Health\n\n"
        post_results: list[HealthResult] = []
        for target in SERVICES:
            result = await workflow.execute_activity_method(
                health.check_service,
                target,
                start_to_close_timeout=timedelta(seconds=30),
            )
            post_results.append(result)

        post_healthy = sum(1 for r in post_results if r.healthy)
        report += f"- Services healthy: {post_healthy}/{len(post_results)}\n"

        degraded = [
            r.name
            for r in post_results
            if not r.healthy and any(p.name == r.name and p.healthy for p in pre_results)
        ]
        if degraded:
            report += f"- **DEGRADED DURING DRILL:** {', '.join(degraded)}\n"
            issues.append(f"Services degraded during drill: {', '.join(degraded)}")
        report += "\n"

        # 5. Summary
        report += "## Summary\n\n"
        if not issues:
            report += "**DR drill passed.** All volumes backed up, all services healthy.\n"
        else:
            report += f"**DR drill completed with {len(issues)} issue(s):**\n\n"
            for issue in issues:
                report += f"- {issue}\n"

        # 6. Prune drill backups (keep only the regular nightly ones)
        for volume in volumes:
            await workflow.execute_activity_method(
                backup.prune_old_backups,
                args=[volume, 7],
                start_to_close_timeout=timedelta(seconds=60),
            )

        # 7. Send report
        severity = "warning" if issues else "info"
        await workflow.execute_activity_method(
            alert.send_email_alert,
            AlertPayload(title="DR Drill Report", body=report, severity=severity),
            start_to_close_timeout=timedelta(seconds=30),
        )

        await workflow.execute_activity_method(
            ops.create_forgejo_issue,
            args=[
                f"DR Drill — {'PASSED' if not issues else f'{len(issues)} issues'}",
                report,
            ],
            start_to_close_timeout=timedelta(seconds=30),
        )

        workflow.logger.info(
            f"DR drill: {len(snapshots)}/{len(volumes)} backed up, "
            f"{len(issues)} issues"
        )
        return report
