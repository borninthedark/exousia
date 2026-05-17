"""CVE check workflow — daily scan for resolved allowlisted CVEs."""

from datetime import timedelta

from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from src.activities.cve_check import CVECheckActivities, CVECheckResult, CVEStatus


@workflow.defn
class CVECheckWorkflow:
    """Daily check: are our allowlisted CVEs fixed upstream/Fedora yet?

    Schedule daily:
        spec=ScheduleSpec(cron_expressions=["0 8 * * *"])  # 8 AM daily
    """

    @workflow.run
    async def run(self) -> CVECheckResult:
        activities = CVECheckActivities()
        vikunja = VikunjaActivities()
        timeout = timedelta(seconds=60)

        # 1. Check upstream releases (GitHub)
        upstream: list[CVEStatus] = await workflow.execute_activity_method(
            activities.check_upstream_releases,
            start_to_close_timeout=timeout,
        )

        # 2. Check Fedora packages (Bodhi)
        fedora: list[CVEStatus] = await workflow.execute_activity_method(
            activities.check_fedora_packages,
            start_to_close_timeout=timeout,
        )

        # 3. Merge results
        merged = {}
        for s in upstream + fedora:
            if s.cve_id not in merged:
                merged[s.cve_id] = s
            else:
                existing = merged[s.cve_id]
                existing.fixed_upstream = existing.fixed_upstream or s.fixed_upstream
                existing.fixed_in_fedora = existing.fixed_in_fedora or s.fixed_in_fedora
                if s.notes:
                    existing.notes = f"{existing.notes}; {s.notes}" if existing.notes else s.notes

        # 4. Determine which CVEs can be removed from allowlist
        removable = [cve_id for cve_id, status in merged.items() if status.fixed_in_fedora]

        # 5. If any are removable, create an issue
        if removable:
            body = "The following CVEs can be removed from the pipeline allowlist:\n\n"
            for cve_id in removable:
                s = merged[cve_id]
                body += f"- **{cve_id}** ({s.package}): {s.notes}\n"
            body += "\nRemove from `pernida.yml` (Lille) and `hiyori.yml` (scan step)."

            await workflow.execute_activity_method(
                activities.create_cve_issue,
                args=[f"CVE allowlist cleanup: {', '.join(removable)}", body],
                start_to_close_timeout=timedelta(seconds=30),
            )
            await workflow.execute_activity_method(
                vikunja.create_ops_task,
                args=[f"Remove CVE allowlist: {", ".join(removable)}", body, 4],
                start_to_close_timeout=timedelta(seconds=15),
            )
            workflow.logger.info(f"Created issue for removable CVEs: {removable}")

        # 6. Also check for new critical CVEs in the image
        new_cves: list[str] = await workflow.execute_activity_method(
            activities.scan_image_for_cves,
            start_to_close_timeout=timedelta(minutes=15),
        )

        if new_cves:
            body = "New critical CVEs found in the image (not in allowlist):\n\n"
            for cve in new_cves:
                body += f"- {cve}\n"
            body += "\nInvestigate and either fix or add to allowlist with justification."

            await workflow.execute_activity_method(
                activities.create_cve_issue,
                args=[f"New critical CVEs: {', '.join(new_cves[:3])}", body],
                start_to_close_timeout=timedelta(seconds=30),
            )

        result = CVECheckResult(
            checked=list(merged.values()),
            removable=removable,
        )
        workflow.logger.info(f"CVE check: {len(merged)} checked, {len(removable)} removable")
        return result
