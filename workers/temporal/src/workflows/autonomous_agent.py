"""Autonomous agent workflow — LLM-driven task execution with PR creation.

Pulls low/medium-priority tasks from Vikunja, plans with Qwen3,
implements with Qwen2.5-coder, creates PR for human review.
Can also use Gemini for planning/review when API key is available.
"""

from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from src.activities.agent import AgentActivities, AgentResult
    from src.activities.llm import Agent, AgentTask, LLMActivities
    from src.activities.vikunja import VikunjaActivities, OPS_PROJECT_ID, ROADMAP_PROJECT_ID


@workflow.defn
class AutonomousAgentWorkflow:
    """Pick up a low/medium-priority task and autonomously implement it.

    Flow:
    1. Fetch next undone task (priority <= 2) from Vikunja
    2. Plan implementation with Qwen3 (or Gemini)
    3. Read relevant files from repo
    4. Generate code changes with Qwen2.5-coder
    5. Create branch + PR on Forgejo
    6. Update Vikunja task with PR link

    Schedule: every 2 hours during work hours
        spec=ScheduleSpec(cron_expressions=["0 */2 8-22 * *"])

    Or trigger manually for a specific task:
        temporal workflow start --type AutonomousAgentWorkflow \
          --task-queue exousia --input '{"task_id": 9}'
    """

    @workflow.run
    async def run(self, task_id: int = 0) -> AgentResult:
        agent = AgentActivities()
        vikunja = VikunjaActivities()
        timeout = timedelta(seconds=300)
        retry = RetryPolicy(maximum_attempts=3)

        # 1. Get task — either specified or next available
        if task_id > 0:
            task = await workflow.execute_activity_method(
                vikunja.list_project_tasks,
                ROADMAP_PROJECT_ID,
                start_to_close_timeout=timedelta(seconds=15),
            )
            task_data = next((t for t in task if t["id"] == task_id), None)
            if not task_data:
                # Try ops project
                task = await workflow.execute_activity_method(
                    vikunja.list_project_tasks,
                    OPS_PROJECT_ID,
                    start_to_close_timeout=timedelta(seconds=15),
                )
                task_data = next((t for t in task if t["id"] == task_id), None)
        else:
            # Find next low-priority task from either project
            task_data = await workflow.execute_activity_method(
                agent.fetch_next_task,
                args=[ROADMAP_PROJECT_ID, 2],
                start_to_close_timeout=timedelta(seconds=15),
            )
            if not task_data:
                task_data = await workflow.execute_activity_method(
                    agent.fetch_next_task,
                    args=[OPS_PROJECT_ID, 2],
                    start_to_close_timeout=timedelta(seconds=15),
                )

        if not task_data:
            workflow.logger.info("No eligible tasks found")
            return AgentResult(task_id=0, success=True, summary="No tasks to process")

        tid = task_data["id"]
        title = task_data["title"]
        description = task_data.get("description", "")

        workflow.logger.info(f"Agent working on task {tid}: {title}")

        # 2. Update task status
        await workflow.execute_activity_method(
            agent.update_vikunja_task,
            args=[tid, "🤖 Agent started working on this task", False],
            start_to_close_timeout=timedelta(seconds=15),
        )

        # 3. Plan with Qwen3
        steps = await workflow.execute_activity_method(
            agent.plan_task,
            args=[title, description],
            start_to_close_timeout=timeout,
            retry_policy=retry,
        )

        if not steps:
            await workflow.execute_activity_method(
                agent.update_vikunja_task,
                args=[tid, "🤖 Agent couldn't generate a plan. Needs human input.", False],
                start_to_close_timeout=timedelta(seconds=15),
            )
            return AgentResult(task_id=tid, success=False, error="No plan generated")

        plan_text = "\n".join(f"{i+1}. {s}" for i, s in enumerate(steps))
        await workflow.execute_activity_method(
            agent.update_vikunja_task,
            args=[tid, f"🤖 Implementation plan:\n\n{plan_text}", False],
            start_to_close_timeout=timedelta(seconds=15),
        )

        # 4. For each step, read existing file and generate changes
        branch = f"agent/task-{tid}"
        files = []

        for step in steps:
            # Extract filepath from step (heuristic: look for paths with extensions)
            import re

            path_match = re.search(r"[`'\"]?([a-zA-Z0-9_/.-]+\.(py|yml|yaml|md|toml|conf|container))[`'\"]?", step)
            if not path_match:
                continue

            filepath = path_match.group(1)

            # Read existing content
            existing = await workflow.execute_activity_method(
                agent.read_file_from_repo,
                filepath,
                start_to_close_timeout=timedelta(seconds=15),
            )

            # Generate new content
            new_content = await workflow.execute_activity_method(
                agent.generate_code,
                args=[filepath, existing, step],
                start_to_close_timeout=timeout,
                retry_policy=retry,
            )

            if new_content and new_content != existing:
                files.append({
                    "path": filepath,
                    "content": new_content,
                    "message": step[:72],
                })

        if not files:
            await workflow.execute_activity_method(
                agent.update_vikunja_task,
                args=[tid, "🤖 No file changes generated. Task may need manual implementation.", False],
                start_to_close_timeout=timedelta(seconds=15),
            )
            return AgentResult(task_id=tid, success=False, error="No file changes")

        # 5. Create branch and PR
        pr_body = (
            f"## Automated Implementation\n\n"
            f"**Vikunja Task:** #{tid} — {title}\n\n"
            f"### Plan\n\n{plan_text}\n\n"
            f"### Files Changed\n\n"
            + "\n".join(f"- `{f['path']}`" for f in files)
            + "\n\n---\n*Generated by AutonomousAgentWorkflow (Qwen3 + Qwen2.5-coder)*"
        )

        pr_url = await workflow.execute_activity_method(
            agent.create_branch_and_pr,
            args=[branch, files, title, pr_body],
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=retry,
        )

        # 6. Update Vikunja
        comment = f"🤖 PR created: {pr_url}\n\n{len(files)} file(s) changed. Awaiting human review."
        await workflow.execute_activity_method(
            agent.update_vikunja_task,
            args=[tid, comment, False],
            start_to_close_timeout=timedelta(seconds=15),
        )

        workflow.logger.info(f"Agent completed task {tid}: {pr_url}")
        return AgentResult(task_id=tid, success=True, pr_url=pr_url, summary=f"{len(files)} files changed")
