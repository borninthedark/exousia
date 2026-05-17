"""Full stack health report — weekly email summarizing system state."""

from datetime import timedelta

from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from src.activities.health import HealthActivities, HealthResult
    from src.activities.alert import AlertActivities, AlertPayload
    from src.activities.operations import OperationsActivities
    from src.activities.observe import ObserveActivities


@workflow.defn
class HealthReportWorkflow:
    """Weekly comprehensive health report across all services.

    Combines: container health, error rates, disk usage, image ages.
    Sends email summary.

    Schedule: weekly Sunday 8 AM
        spec=ScheduleSpec(cron_expressions=["0 8 * * 0"])
    """

    @workflow.run
    async def run(self) -> str:
        health = HealthActivities()
        ops = OperationsActivities()
        alert = AlertActivities()
        observe = ObserveActivities()
        timeout = timedelta(seconds=30)

        # 1. Run health checks on all services
        from src.activities.health import SERVICES

        health_results: list[HealthResult] = []
        for target in SERVICES:
            result = await workflow.execute_activity_method(
                health.check_service,
                target,
                start_to_close_timeout=timeout,
            )
            health_results.append(result)

        healthy = [r for r in health_results if r.healthy]
        unhealthy = [r for r in health_results if not r.healthy]

        # 2. Get error rates from OpenObserve (last 7 days)
        error_rates: dict[str, int] = await workflow.execute_activity_method(
            observe.check_error_rate,
            10080,  # 7 days in minutes
            start_to_close_timeout=timeout,
        )

        # 3. Get container inventory
        images = await workflow.execute_activity_method(
            ops.scan_running_images,
            start_to_close_timeout=timedelta(seconds=60),
        )

        # 4. Build report
        report = "# Weekly Health Report\n\n"

        report += "## Service Health\n\n"
        report += f"- **Healthy:** {len(healthy)}/{len(health_results)}\n"
        if unhealthy:
            report += f"- **Unhealthy:** {', '.join(r.name for r in unhealthy)}\n"
        report += "\n"

        report += "## Error Rates (7 days)\n\n"
        report += "| Container | Errors |\n|---|---|\n"
        for container, count in sorted(error_rates.items(), key=lambda x: x[1], reverse=True)[:10]:
            report += f"| {container} | {count} |\n"
        report += "\n"

        report += "## Running Containers\n\n"
        report += f"- **Total:** {len(images)}\n"
        report += "\n"

        # 5. Send email
        await workflow.execute_activity_method(
            alert.send_email_alert,
            AlertPayload(
                title="Weekly Health Report",
                body=report,
                severity="info",
            ),
            start_to_close_timeout=timedelta(seconds=30),
        )

        # 6. Also create a Forgejo issue for tracking
        await workflow.execute_activity_method(
            ops.create_forgejo_issue,
            args=[
                f"Weekly Health Report — {len(healthy)}/{len(health_results)} healthy",
                report,
            ],
            start_to_close_timeout=timeout,
        )

        workflow.logger.info(
            f"Health report: {len(healthy)}/{len(health_results)} healthy, "
            f"{sum(error_rates.values())} total errors"
        )
        return report
