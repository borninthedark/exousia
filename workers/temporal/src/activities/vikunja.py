"""Vikunja activities — project and task management from Temporal workflows."""

from dataclasses import dataclass

from temporalio import activity

from src.clients.vikunja import VikunjaClient


@dataclass
class TaskUpdate:
    task_id: int
    title: str | None = None
    description: str | None = None
    done: bool | None = None
    priority: int | None = None


class VikunjaActivities:
    """Create and manage tasks in Vikunja from Temporal workflows."""

    def __init__(self) -> None:
        self.vikunja = VikunjaClient()

    @activity.defn
    async def create_task(
        self,
        project_id: int,
        title: str,
        description: str = "",
        priority: int = 3,
    ) -> int:
        """Create a task in Vikunja. Returns task ID."""
        task_id = await self.vikunja.create_task(
            project_id=project_id,
            title=title,
            description=description,
            priority=priority,
        )
        activity.logger.info(f"Created Vikunja task {task_id}: {title}")
        return task_id

    @activity.defn
    async def complete_task(self, task_id: int) -> None:
        """Mark a task as done."""
        await self.vikunja.complete_task(task_id)
        activity.logger.info(f"Completed Vikunja task {task_id}")

    @activity.defn
    async def add_task_comment(self, task_id: int, comment: str) -> None:
        """Add a comment to a task (e.g., workflow results)."""
        await self.vikunja.add_comment(task_id, comment)

    @activity.defn
    async def update_task_status(self, update: TaskUpdate) -> None:
        """Update task fields (title, description, done, priority)."""
        kwargs = {}
        if update.title is not None:
            kwargs["title"] = update.title
        if update.description is not None:
            kwargs["description"] = update.description
        if update.done is not None:
            kwargs["done"] = update.done
        if update.priority is not None:
            kwargs["priority"] = update.priority
        if kwargs:
            await self.vikunja.update_task(update.task_id, **kwargs)

    @activity.defn
    async def list_project_tasks(self, project_id: int) -> list[dict]:
        """List all tasks in a project."""
        return await self.vikunja.list_tasks(project_id)

    @activity.defn
    async def search_tasks(self, query: str) -> list[dict]:
        """Search tasks across all projects."""
        return await self.vikunja.search_tasks(query)
