"""Health check workflow — deep service verification with alerting."""

import asyncio
from datetime import timedelta

from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from src.activities.health import SERVICES, HealthActivities, HealthResult


@workflow.defn
class HealthCheckWorkflow:
    """Check all services and alert on failures.

    Schedule every 5 minutes:
        spec=ScheduleSpec(cron_expressions=["*/5 * * * *"])
    """

    @workflow.run
    async def run(self) -> list[HealthResult]:
        activities = HealthActivities()
        timeout = timedelta(seconds=30)

        # Run all service checks in parallel
        checks = []
        for target in SERVICES:
            checks.append(
                workflow.execute_activity_method(
                    activities.check_service,
                    target,
                    start_to_close_timeout=timeout,
                )
            )

        results: list[HealthResult] = await asyncio.gather(*checks)

        # Also verify Ollama models
        model_check = await workflow.execute_activity_method(
            activities.check_ollama_models,
            start_to_close_timeout=timeout,
        )
        results.append(model_check)

        # Log summary
        healthy = sum(1 for r in results if r.healthy)
        total = len(results)
        workflow.logger.info(f"Health: {healthy}/{total} services healthy")

        # Alert on failures
        unhealthy = [r for r in results if not r.healthy]
        if unhealthy:
            await workflow.execute_activity_method(
                activities.send_alert,
                unhealthy,
                start_to_close_timeout=timedelta(seconds=60),
            )

        return results
