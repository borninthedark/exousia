"""Container lifecycle workflow — weekly image updates with rolling restart."""

from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from src.activities.container_lifecycle import (
        ContainerLifecycleActivities,
        RestartResult,
        UpdateResult,
    )

# Restart order: databases first, then core, then apps
RESTART_ORDER = [
    # Databases
    ["forgejo-db", "immich-db", "paperless-db", "temporal-db", "miniflux-db"],
    # Redis/cache
    ["immich-redis", "paperless-redis"],
    # Core infrastructure
    ["authelia", "caddy", "coredns", "forgejo", "temporal-server"],
    # Application services
    [
        "beszel",
        "beszel-agent",
        "changedetection",
        "dashy",
        "immich",
        "immich-ml",
        "miniflux",
        "navidrome",
        "ollama",
        "open-webui",
        "openobserve",
        "paperless",
        "temporal-ui",
        "uptime-kuma",
        "fluent-bit",
    ],
    # Runners
    ["forgejo-runner", "forgejo-runner-witness", "exousia-worker"],
]


@workflow.defn
class ContainerLifecycleWorkflow:
    """Check for image updates and perform rolling restart.

    Schedule weekly:
        spec=ScheduleSpec(cron_expressions=["0 4 * * 0"])  # Sunday 4 AM
    """

    @workflow.run
    async def run(self) -> dict:
        activities = ContainerLifecycleActivities()
        timeout = timedelta(minutes=5)
        retry = RetryPolicy(maximum_attempts=2)

        # 1. Check for available updates
        updates: list[UpdateResult] = await workflow.execute_activity_method(
            activities.check_updates,
            start_to_close_timeout=timedelta(seconds=60),
        )

        updatable = [u for u in updates if u.updated]
        workflow.logger.info(f"Found {len(updatable)} image updates available")

        if not updatable:
            return {"updates": 0, "restarted": 0, "rollbacks": 0}

        # 2. Pull new images
        for update in updatable:
            if update.new_image:
                await workflow.execute_activity_method(
                    activities.pull_image,
                    update.new_image,
                    start_to_close_timeout=timeout,
                    retry_policy=retry,
                )

        # 3. Rolling restart in dependency order
        restarted = 0
        rollbacks = 0

        for tier in RESTART_ORDER:
            for service in tier:
                # Only restart if it had an update
                if not any(u.container == service for u in updatable):
                    continue

                result: RestartResult = await workflow.execute_activity_method(
                    activities.restart_service,
                    service,
                    start_to_close_timeout=timedelta(minutes=2),
                    retry_policy=retry,
                )

                if result.healthy:
                    restarted += 1
                    workflow.logger.info(f"Restarted {service} — healthy")
                else:
                    workflow.logger.warning(f"Unhealthy after restart: {service}, rolling back")
                    await workflow.execute_activity_method(
                        activities.rollback_service,
                        service,
                        start_to_close_timeout=timedelta(minutes=2),
                    )
                    rollbacks += 1

            # Wait between tiers for stability
            await workflow.sleep(timedelta(seconds=10))

        # 4. Prune old images
        pruned = await workflow.execute_activity_method(
            activities.prune_images,
            start_to_close_timeout=timedelta(minutes=5),
        )

        return {
            "updates": len(updatable),
            "restarted": restarted,
            "rollbacks": rollbacks,
            "pruned": pruned,
        }
