"""Security scan workflow — weekly Trivy scan of all running images."""

from datetime import timedelta

from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from src.activities.alert import AlertActivities, AlertPayload
    from src.activities.vikunja import VikunjaActivities
    from src.activities.operations import OperationsActivities, ScanResult


@workflow.defn
class SecurityScanWorkflow:
    """Trivy scan all running container images for HIGH+ vulnerabilities.

    Schedule: weekly Monday 6 AM
        spec=ScheduleSpec(cron_expressions=["0 6 * * 1"])
    """

    @workflow.run
    async def run(self) -> dict:
        ops = OperationsActivities()
        alert = AlertActivities()

        # 1. Scan all running images
        results: list[ScanResult] = await workflow.execute_activity_method(
            ops.scan_running_images,
            start_to_close_timeout=timedelta(minutes=30),
        )

        if not results:
            workflow.logger.info("Security scan: no HIGH/CRITICAL findings")
            return {"scanned": 0, "findings": 0}

        # 2. Build report
        body = "## Weekly Security Scan Results\n\n"
        total_critical = 0
        total_high = 0
        for r in results:
            total_critical += r.critical
            total_high += r.high
            body += f"### {r.container} (`{r.image}`)\n"
            body += f"- Critical: {r.critical}, High: {r.high}\n"
            if r.cves:
                body += f"- CVEs: {', '.join(r.cves[:5])}\n"
            body += "\n"

        # 3. Create issue if critical findings
        if total_critical > 0:
            await workflow.execute_activity_method(
                ops.create_forgejo_issue,
                args=[
                    f"Security: {total_critical} critical CVEs in running containers",
                    body,
                ],
                start_to_close_timeout=timedelta(seconds=30),
            )

            # Also email alert for critical
            await workflow.execute_activity_method(
                alert.send_email_alert,
                AlertPayload(
                    title=f"{total_critical} critical CVEs found",
                    body=body,
                    severity="critical",
                ),
                start_to_close_timeout=timedelta(seconds=30),
            )

        workflow.logger.info(
            f"Scan complete: {len(results)} images with findings, "
            f"{total_critical} critical, {total_high} high"
        )

        return {
            "scanned": len(results),
            "critical": total_critical,
            "high": total_high,
        }
