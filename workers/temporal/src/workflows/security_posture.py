"""Security posture workflow — weekly automated security audit.

Checks: exposed ports, SELinux, firewalld, container security labels.
Creates Vikunja task for any findings.
"""

from datetime import timedelta

from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from src.activities.alert import AlertActivities, AlertPayload
    from src.activities.security import SecurityActivities, SecurityFinding
    from src.activities.vikunja import VikunjaActivities


@workflow.defn
class SecurityPostureWorkflow:
    """Weekly security posture audit.

    Schedule: weekly Friday 6 AM
        spec=ScheduleSpec(cron_expressions=["0 6 * * 5"])
    """

    @workflow.run
    async def run(self) -> str:
        security = SecurityActivities()
        alert = AlertActivities()
        vikunja = VikunjaActivities()
        timeout = timedelta(seconds=30)

        all_findings: list[SecurityFinding] = []

        # 1. Check exposed ports
        port_findings = await workflow.execute_activity_method(
            security.check_exposed_ports,
            start_to_close_timeout=timeout,
        )
        all_findings.extend(port_findings)

        # 2. Check SELinux
        selinux = await workflow.execute_activity_method(
            security.check_selinux,
            start_to_close_timeout=timeout,
        )
        all_findings.append(selinux)

        # 3. Check firewalld
        firewalld = await workflow.execute_activity_method(
            security.check_firewalld,
            start_to_close_timeout=timeout,
        )
        all_findings.append(firewalld)

        # 4. Check container security
        container_findings = await workflow.execute_activity_method(
            security.check_container_security,
            start_to_close_timeout=timedelta(seconds=60),
        )
        all_findings.extend(container_findings)

        # 5. Build report
        critical = [f for f in all_findings if f.severity == "critical"]
        warnings = [f for f in all_findings if f.severity == "warning"]
        info = [f for f in all_findings if f.severity == "info"]

        report = "# Security Posture Report\n\n"
        report += f"- Critical: {len(critical)}\n"
        report += f"- Warnings: {len(warnings)}\n"
        report += f"- Info: {len(info)}\n\n"

        if critical:
            report += "## Critical\n\n"
            for f in critical:
                report += f"- **[{f.category}]** {f.description}\n"
            report += "\n"

        if warnings:
            report += "## Warnings\n\n"
            for f in warnings:
                report += f"- [{f.category}] {f.description}\n"
            report += "\n"

        if info:
            report += "## Info\n\n"
            for f in info:
                report += f"- [{f.category}] {f.description}\n"

        # 6. Create Vikunja task if findings
        if critical or warnings:
            severity = 4 if critical else 3
            await workflow.execute_activity_method(
                vikunja.create_ops_task,
                args=[
                    f"Security: {len(critical)} critical, {len(warnings)} warnings",
                    report,
                    severity,
                ],
                start_to_close_timeout=timedelta(seconds=15),
            )

        # 7. Email if critical
        if critical:
            await workflow.execute_activity_method(
                alert.send_email_alert,
                AlertPayload(
                    title=f"Security: {len(critical)} critical findings",
                    body=report,
                    severity="critical",
                ),
                start_to_close_timeout=timedelta(seconds=30),
            )

        workflow.logger.info(
            f"Security posture: {len(critical)} critical, {len(warnings)} warnings, {len(info)} info"
        )
        return report
