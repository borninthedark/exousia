"""Miniflux digest workflow — daily RSS summary via llama."""

from datetime import timedelta

from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from src.activities.llm import AgentResponse, AgentTask, Agent, LLMActivities
    from src.activities.operations import OperationsActivities


@workflow.defn
class MinifluxDigestWorkflow:
    """Summarize unread RSS entries daily via llama3.2.

    Schedule: daily 7 AM
        spec=ScheduleSpec(cron_expressions=["0 7 * * *"])
    """

    @workflow.run
    async def run(self) -> str:
        ops = OperationsActivities()
        llm = LLMActivities.__new__(LLMActivities)

        # 1. Fetch unread entries
        entries = await workflow.execute_activity_method(
            ops.fetch_unread_entries,
            20,
            start_to_close_timeout=timedelta(seconds=30),
        )

        if not entries:
            return "No unread entries."

        # 2. Build digest prompt
        articles = "\n\n".join(
            f"**{e['title']}** ({e['feed']})\n{e['content'][:500]}"
            for e in entries
        )

        task = AgentTask(
            agent=Agent.OLLAMA,
            system="You are a concise news briefing assistant. Summarize the key points from these RSS articles in 3-5 bullet points. Group by topic. Be brief.",
            prompt=f"Summarize today's feed:\n\n{articles}",
            temperature=0.3,
            max_tokens=1000,
        )

        # 3. Generate digest with llama
        response: AgentResponse = await workflow.execute_activity_method(
            llm.dispatch_ollama,
            task,
            start_to_close_timeout=timedelta(seconds=120),
        )

        # 4. Mark as read
        entry_ids = [e["id"] for e in entries]
        await workflow.execute_activity_method(
            ops.mark_entries_read,
            entry_ids,
            start_to_close_timeout=timedelta(seconds=15),
        )

        workflow.logger.info(f"Digest: {len(entries)} articles summarized")
        return response.content
