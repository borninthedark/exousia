"""Register Temporal schedules for all recurring workflows."""

import asyncio
import os

from temporalio.client import Client, Schedule, ScheduleActionStartWorkflow, ScheduleSpec

TEMPORAL_HOST = os.getenv("TEMPORAL_HOST", "localhost:7233")
TASK_QUEUE = "exousia"

SCHEDULES = [
    ("health-check", "HealthCheckWorkflow", "*/5 * * * *", "Deep service health verification"),
    ("anomaly-detection", "AnomalyDetectionWorkflow", "*/15 * * * *", "Error spike detection"),
    ("ticket-sync", "TicketSyncWorkflow", "*/15 * * * *", "Paperless ↔ Forgejo issue sync"),
    ("pr-review", "PRReviewWorkflow", "*/30 * * * *", "Auto-review open Forgejo PRs"),
    ("base-image-mirror", "BaseImageMirrorWorkflow", "0 2 * * *", "Nightly base image mirror"),
    ("daily-backup", "BackupWorkflow", "0 3 * * *", "Nightly volume backup with pruning"),
    ("miniflux-digest", "MinifluxDigestWorkflow", "0 7 * * *", "Daily RSS digest via llama"),
    ("cve-check", "CVECheckWorkflow", "0 8 * * *", "Daily CVE allowlist review"),
    ("container-lifecycle", "ContainerLifecycleWorkflow", "30 9 * * *", "Daily image updates + restart + prune"),
    ("health-report", "HealthReportWorkflow", "0 8 * * 0", "Weekly health report"),
    ("deps-update", "DepsUpdateWorkflow", "0 9 * * 3", "Weekly dependency update check"),
    ("security-scan", "SecurityScanWorkflow", "0 6 * * 1", "Weekly Trivy scan"),
    ("journal-knowledge", "JournalKnowledgeWorkflow", "0 23 * * *", "Daily ops insights from logs"),
    ("resource-audit", "ResourceAuditWorkflow", "0 9 1 * *", "Monthly resource audit"),
    ("dr-drill", "DRDrillWorkflow", "0 2 15 * *", "Monthly DR drill"),
]


async def main():
    client = await Client.connect(TEMPORAL_HOST)

    for sid, wf, cron, memo in SCHEDULES:
        try:
            await client.create_schedule(
                sid,
                Schedule(
                    action=ScheduleActionStartWorkflow(
                        wf,
                        id=f"{sid}-run",
                        task_queue=TASK_QUEUE,
                    ),
                    spec=ScheduleSpec(cron_expressions=[cron]),
                ),
            )
            print(f"Created: {sid} ({cron}) — {memo}")
        except Exception as e:
            if "already exists" in str(e).lower():
                print(f"Exists:  {sid}")
            else:
                print(f"Error:   {sid} — {e}")


if __name__ == "__main__":
    asyncio.run(main())
