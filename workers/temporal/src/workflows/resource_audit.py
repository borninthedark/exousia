"""Resource audit workflow — monthly cost and resource utilization report."""

from datetime import timedelta

from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from src.activities.container_lifecycle import ContainerLifecycleActivities
    from src.activities.alert import AlertActivities, AlertPayload
    from src.activities.operations import OperationsActivities
    from src.activities.observe import ObserveActivities


@workflow.defn
class ResourceAuditWorkflow:
    """Monthly audit: RAM per service, disk per volume, prune candidates.

    Schedule: monthly 1st at 9 AM
        spec=ScheduleSpec(cron_expressions=["0 9 1 * *"])
    """

    @workflow.run
    async def run(self) -> str:
        ops = OperationsActivities()
        alert = AlertActivities()
        observe = ObserveActivities()
        lifecycle = ContainerLifecycleActivities()
        timeout = timedelta(seconds=60)

        # 1. Get container stats (names + images)
        containers = await workflow.execute_activity_method(
            ops.scan_running_images,
            start_to_close_timeout=timeout,
        )

        # 2. Check for available image updates
        updates = await workflow.execute_activity_method(
            lifecycle.check_updates,
            start_to_close_timeout=timeout,
        )
        updatable = [u for u in updates if u.updated]

        # 3. Get error rates (30 days)
        error_rates: dict[str, int] = await workflow.execute_activity_method(
            observe.check_error_rate,
            43200,  # 30 days in minutes
            start_to_close_timeout=timeout,
        )

        # 4. Build report
        report = "# Monthly Resource Audit\n\n"

        report += "## Container Inventory\n\n"
        report += f"- **Running:** {len(containers)}\n"
        report += f"- **With updates available:** {len(updatable)}\n\n"

        if updatable:
            report += "### Pending Updates\n\n"
            report += "| Container | Image |\n|---|---|\n"
            for u in updatable:
                report += f"| {u.container} | {u.new_image} |\n"
            report += "\n"

        report += "## Error Volume (30 days)\n\n"
        report += "| Container | Errors | Avg/day |\n|---|---|---|\n"
        for container, count in sorted(error_rates.items(), key=lambda x: x[1], reverse=True)[:15]:
            avg = round(count / 30, 1)
            report += f"| {container} | {count:,} | {avg} |\n"
        report += "\n"

        # 5. Identify quiet containers (potential decommission candidates)
        active_names = {c["name"] for c in containers}
        noisy = {k for k, v in error_rates.items() if v > 1000}
        quiet = active_names - set(error_rates.keys())

        if quiet:
            report += "## Quiet Containers (no log activity)\n\n"
            report += "These containers produced no log output. Verify they're needed:\n\n"
            for name in sorted(quiet):
                report += f"- {name}\n"
            report += "\n"

        if noisy:
            report += "## Noisy Containers (>1000 errors/month)\n\n"
            report += "Consider investigating or filtering:\n\n"
            for name in sorted(noisy):
                report += f"- {name} ({error_rates[name]:,} errors)\n"
            report += "\n"

        # 6. Recommendations
        report += "## Recommendations\n\n"
        if updatable:
            report += f"- Update {len(updatable)} container images\n"
        if noisy:
            report += f"- Investigate {len(noisy)} noisy containers\n"
        if quiet:
            report += f"- Review {len(quiet)} quiet containers for decommission\n"
        report += "- Run `podman system df` to check disk usage\n"
        report += "- Run `podman image prune` if reclaimable > 10 GB\n"

        # 7. Send report
        await workflow.execute_activity_method(
            alert.send_email_alert,
            AlertPayload(
                title="Monthly Resource Audit",
                body=report,
                severity="info",
            ),
            start_to_close_timeout=timedelta(seconds=30),
        )

        await workflow.execute_activity_method(
            ops.create_forgejo_issue,
            args=["Monthly Resource Audit", report],
            start_to_close_timeout=timedelta(seconds=30),
        )

        workflow.logger.info(
            f"Resource audit: {len(containers)} containers, "
            f"{len(updatable)} updates, {len(noisy)} noisy"
        )
        return report
