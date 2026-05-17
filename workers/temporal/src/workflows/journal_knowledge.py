"""Journal to knowledge workflow — extract operational insights from daily logs."""

from datetime import timedelta

from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from src.activities.llm import Agent, AgentResponse, AgentTask, LLMActivities
    from src.activities.observe import ObserveActivities


@workflow.defn
class JournalKnowledgeWorkflow:
    """Extract key decisions and patterns from daily logs.

    Schedule: daily 11 PM
        spec=ScheduleSpec(cron_expressions=["0 23 * * *"])
    """

    @workflow.run
    async def run(self) -> str:
        observe = ObserveActivities()
        llm = LLMActivities.__new__(LLMActivities)

        # 1. Get today's important logs (priority <= 4 = notice and above)
        logs = await workflow.execute_activity_method(
            observe.query_daily_logs,
            start_to_close_timeout=timedelta(seconds=30),
        )

        if not logs:
            return "No notable log entries today."

        # 2. Ask LLM to extract insights
        log_text = "\n".join(logs[:80])
        task = AgentTask(
            agent=Agent.OLLAMA,
            system=(
                "You are an ops analyst reviewing today's system logs. "
                "Extract: 1) Key events (deployments, restarts, errors). "
                "2) Patterns worth noting. 3) Action items if any. "
                "Format as a brief daily ops report in markdown."
            ),
            prompt=f"Today's log entries:\n\n{log_text}",
            temperature=0.3,
            max_tokens=1000,
        )

        response: AgentResponse = await workflow.execute_activity_method(
            llm.dispatch_ollama,
            task,
            start_to_close_timeout=timedelta(seconds=120),
        )

        workflow.logger.info("Daily knowledge extraction complete")
        return response.content
