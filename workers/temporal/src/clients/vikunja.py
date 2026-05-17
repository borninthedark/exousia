"""Vikunja REST API client — project and task management.

Enables Temporal workflows to create/update tasks, manage projects,
and orchestrate sprint planning.
"""

from __future__ import annotations

import os

import httpx


class VikunjaClient:
    """Async client for the Vikunja REST API."""

    def __init__(
        self,
        api_url: str | None = None,
        token: str | None = None,
    ):
        self.api_url = api_url or os.getenv("VIKUNJA_API_URL", "http://vikunja:3456")
        self.token = token or os.getenv("VIKUNJA_API_TOKEN", "")

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=f"{self.api_url}/api/v1",
            headers={"Authorization": f"Bearer {self.token}"},
            timeout=30.0,
        )

    async def list_projects(self) -> list[dict]:
        """List all projects."""
        async with self._client() as client:
            resp = await client.get("/projects")
            resp.raise_for_status()
            return resp.json()

    async def create_project(self, title: str, description: str = "") -> int:
        """Create a project. Returns project ID."""
        async with self._client() as client:
            resp = await client.put(
                "/projects",
                json={"title": title, "description": description},
            )
            resp.raise_for_status()
            return int(resp.json()["id"])

    async def list_tasks(self, project_id: int) -> list[dict]:
        """List tasks in a project."""
        async with self._client() as client:
            resp = await client.get(f"/projects/{project_id}/tasks")
            resp.raise_for_status()
            return resp.json()

    async def create_task(
        self,
        project_id: int,
        title: str,
        description: str = "",
        priority: int = 3,
        labels: list[str] | None = None,
    ) -> int:
        """Create a task in a project. Returns task ID."""
        async with self._client() as client:
            resp = await client.put(
                f"/projects/{project_id}/tasks",
                json={
                    "title": title,
                    "description": description,
                    "priority": priority,
                    "project_id": project_id,
                },
            )
            resp.raise_for_status()
            return int(resp.json()["id"])

    async def update_task(self, task_id: int, **kwargs) -> dict:
        """Update a task (title, description, priority, done, etc)."""
        async with self._client() as client:
            resp = await client.post(f"/tasks/{task_id}", json=kwargs)
            resp.raise_for_status()
            return resp.json()

    async def complete_task(self, task_id: int) -> dict:
        """Mark a task as done."""
        return await self.update_task(task_id, done=True)

    async def add_comment(self, task_id: int, comment: str) -> dict:
        """Add a comment to a task."""
        async with self._client() as client:
            resp = await client.put(
                f"/tasks/{task_id}/comments",
                json={"comment": comment},
            )
            resp.raise_for_status()
            return resp.json()

    async def get_task(self, task_id: int) -> dict:
        """Get a single task by ID."""
        async with self._client() as client:
            resp = await client.get(f"/tasks/{task_id}")
            resp.raise_for_status()
            return resp.json()

    async def search_tasks(self, query: str) -> list[dict]:
        """Search tasks across all projects."""
        async with self._client() as client:
            resp = await client.get("/tasks/all", params={"s": query})
            resp.raise_for_status()
            return resp.json()
