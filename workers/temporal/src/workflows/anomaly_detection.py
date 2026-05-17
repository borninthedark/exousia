"""Log anomaly detection workflow — detect error spikes and trigger incident response."""

from datetime import timedelta

from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from src.activities.incident import IncidentActivities, IncidentContext
    from src.activities.alert import AlertActivities, AlertPayload
    from src.activities.operations import OperationsActivities
    from src.activities.observe import ObserveActivities

# Error threshold: if a container has more than this many errors in 15 min, alert
ERROR_THRESHOLD = 50


@workflow.defn
class AnomalyDetectionWorkflow:
    """Detect error rate spikes and auto-trigger incident response.

    Schedule: every 15 min
        spec=ScheduleSpec(cron_expressions=["*/15 * * * *"])
    """

    @workflow.run
    async def run(self) -> dict:
        ops = OperationsActivities()
        observe = ObserveActivities()
        incident_acts = IncidentActivities()

        # 1. Check error rates
        error_counts: dict[str, int] = await workflow.execute_activity_method(
            observe.check_error_rate,
            15,
            start_to_close_timeout=timedelta(seconds=30),
        )

        if not error_counts:
            return {"anomalies": 0}

        # 2. Find containers above threshold
        anomalies = {k: v for k, v in error_counts.items() if v > ERROR_THRESHOLD}

        if not anomalies:
            return {"anomalies": 0, "checked": len(error_counts)}

        workflow.logger.warning(f"Anomalies detected: {anomalies}")

        # 3. For each anomaly, trigger incident response
        for container, count in anomalies.items():
            context = IncidentContext(
                container=container,
                trigger=f"error_spike ({count} errors in 15min)",
            )

            # Query logs for this container
            context.logs = await workflow.execute_activity_method(
                incident_acts.query_recent_logs,
                container,
                start_to_close_timeout=timedelta(seconds=30),
            )

            # Diagnose
            diagnosis = await workflow.execute_activity_method(
                incident_acts.diagnose_with_llm,
                context,
                start_to_close_timeout=timedelta(seconds=90),
            )
            context.diagnosis = diagnosis

            # Auto-restart if LLM recommends it
            if "action: restart" in diagnosis.lower():
                await workflow.execute_activity_method(
                    incident_acts.restart_container,
                    container,
                    start_to_close_timeout=timedelta(minutes=2),
                )
            elif "action: ignore" not in diagnosis.lower():
                # Escalate — create issue
                await workflow.execute_activity_method(
                    incident_acts.create_incident_issue,
                    context,
                    start_to_close_timeout=timedelta(seconds=30),
                )

        return {"anomalies": len(anomalies), "containers": list(anomalies.keys())}
