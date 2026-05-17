"""Register Temporal schedules for all recurring workflows."""

import asyncio
import os

from temporalio.client import Client, Schedule, ScheduleActionStartWorkflow, ScheduleSpec

TEMPORAL_HOST = os.getenv("TEMPORAL_HOST", "localhost:7233")
TASK_QUEUE = "exousia"


async def main():
    client = await Client.connect(TEMPORAL_HOST)

    schedules = [
        {
            "id": "container-lifecycle",
            "workflow": "ContainerLifecycleWorkflow",
            "cron": "30 9 * * *",  # Sunday 4 AM
            "memo": "Daily container image updates with rolling restart",
        },
        {
            "id": "cve-check",
            "workflow": "CVECheckWorkflow",
            "cron": "0 8 * * *",  # Daily 8 AM
            "memo": "Daily CVE allowlist review",
        },
        {
            "id": "ticket-sync",
            "workflow": "TicketSyncWorkflow",
            "cron": "*/15 * * * *",  # Every 15 min
            "memo": "Paperless ↔ Forgejo issue sync",
        },
        {
            "id": "health-check",
            "workflow": "HealthCheckWorkflow",
            "cron": "*/5 * * * *",  # Every 5 min
            "memo": "Deep service health verification",
        },
        {
            "id": "daily-backup",
            "workflow": "BackupWorkflow",
            "cron": "0 3 * * *",  # Daily 3 AM
            "memo": "Nightly volume backup with pruning",
        },
    ]

    for sched in schedules:
        try:
            await client.create_schedule(
                sched["id"],
                Schedule(
                    action=ScheduleActionStartWorkflow(
                        sched["workflow"],
                        id=f'{sched["id"]}-run',
                        task_queue=TASK_QUEUE,
                    ),
                    spec=ScheduleSpec(cron_expressions=[sched["cron"]]),
                ),
            )
            print(f"Created: {sched['id']} ({sched['cron']}) — {sched['memo']}")
        except Exception as e:
            if "already exists" in str(e).lower():
                print(f"Exists:  {sched['id']} — skipping")
            else:
                print(f"Error:   {sched['id']} — {e}")


if __name__ == "__main__":
    asyncio.run(main())
