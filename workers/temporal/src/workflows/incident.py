"""Incident response workflow — detect, diagnose, auto-remediate."""

from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from src.activities.incident import IncidentActivities, IncidentContext, RemediationResult


@workflow.defn
class IncidentResponseWorkflow:
    """Respond to a container incident: gather logs, diagnose, act.

    Trigger via signal or schedule:
        client.start_workflow(IncidentResponseWorkflow.run, context, ...)
    """

    @workflow.run
    async def run(self, context: IncidentContext) -> RemediationResult:
        activities = IncidentActivities()

        # 1. Gather recent logs from OpenObserve
        context.logs = await workflow.execute_activity_method(
            activities.query_recent_logs,
            context.container,
            start_to_close_timeout=timedelta(seconds=30),
        )

        workflow.logger.info(
            f"Incident: {context.container} ({context.trigger}) — {len(context.logs or [])} log lines"
        )

        # 2. Ask LLM to diagnose
        diagnosis = await workflow.execute_activity_method(
            activities.diagnose_with_llm,
            context,
            start_to_close_timeout=timedelta(seconds=90),
        )
        context.diagnosis = diagnosis

        # 3. Parse recommended action from LLM response
        action = "investigate"  # default safe
        diag_lower = diagnosis.lower()
        if "action: restart" in diag_lower:
            action = "restart"
        elif "action: ignore" in diag_lower:
            action = "ignore"

        workflow.logger.info(f"Diagnosis: {diagnosis[:100]}... Action: {action}")

        # 4. Execute remediation
        if action == "restart":
            result = await workflow.execute_activity_method(
                activities.restart_container,
                context.container,
                start_to_close_timeout=timedelta(minutes=2),
                retry_policy=RetryPolicy(maximum_attempts=2),
            )

            # If restart failed, escalate to issue
            if not result.success:
                result = await workflow.execute_activity_method(
                    activities.create_incident_issue,
                    context,
                    start_to_close_timeout=timedelta(seconds=30),
                )
            return result

        elif action == "ignore":
            return RemediationResult(
                container=context.container,
                action="ignored",
                success=True,
                details=diagnosis[:200],
            )

        else:
            # investigate — create issue for human
            result = await workflow.execute_activity_method(
                activities.create_incident_issue,
                context,
                start_to_close_timeout=timedelta(seconds=30),
            )
            return result
