"""Changelog generation workflow — parse commits and generate release notes."""

from datetime import timedelta

from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from src.activities.llm import Agent, AgentResponse, AgentTask, LLMActivities
    from src.activities.operations import OperationsActivities


@workflow.defn
class ChangelogWorkflow:
    """Generate changelog from conventional commits since last tag.

    Trigger: on-demand (after release tag) or weekly summary
    """

    @workflow.run
    async def run(self) -> str:
        ops = OperationsActivities()
        llm = LLMActivities.__new__(LLMActivities)

        # 1. Get latest tag
        tag = await workflow.execute_activity_method(
            ops.get_latest_tag,
            start_to_close_timeout=timedelta(seconds=15),
        )

        # 2. Get commits since tag
        commits = await workflow.execute_activity_method(
            ops.get_commits_since_tag,
            tag,
            start_to_close_timeout=timedelta(seconds=15),
        )

        if not commits:
            return "No new commits since last tag."

        # 3. Ask LLM to format changelog
        commit_list = "\n".join(f"- {c}" for c in commits)
        task = AgentTask(
            agent=Agent.OLLAMA,
            system="You are a release notes writer. Group commits by type (features, fixes, docs, chores). Use markdown. Be concise.",
            prompt=f"Generate a changelog from these commits (since {tag or 'beginning'}):\n\n{commit_list}",
            temperature=0.3,
            max_tokens=1500,
        )

        response: AgentResponse = await workflow.execute_activity_method(
            llm.dispatch_ollama,
            task,
            start_to_close_timeout=timedelta(seconds=90),
        )

        workflow.logger.info(f"Changelog generated from {len(commits)} commits")
        return response.content
