"""Autonomous agent activities — LLM-driven task execution.

Uses Qwen3/Llama via Ollama to plan and execute low-priority tasks,
creating PRs on Forgejo for human review before merge.
"""

import os
from dataclasses import dataclass

import httpx
from temporalio import activity

from src.clients.forgejo import ForgejoClient
from src.clients.vikunja import VikunjaClient


@dataclass
class AgentPlan:
    task_id: int
    title: str
    description: str
    steps: list[str]
    files_to_modify: list[str]
    branch_name: str


@dataclass
class AgentResult:
    task_id: int
    success: bool
    pr_url: str = ""
    error: str = ""
    summary: str = ""


class AgentActivities:
    """Autonomous LLM agent for low-priority task execution."""

    def __init__(self) -> None:
        self.ollama_url = os.getenv("OLLAMA_URL", "http://ollama:11434")
        self.planning_model = os.getenv("AGENT_PLANNING_MODEL", "qwen3:8b")
        self.coding_model = os.getenv("AGENT_CODING_MODEL", "qwen2.5-coder:1.5b")
        self.forgejo = ForgejoClient()
        self.vikunja = VikunjaClient()

    async def _generate(self, model: str, prompt: str, system: str = "", temperature: float = 0.3) -> str:
        """Call Ollama for text generation."""
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                f"{self.ollama_url}/api/generate",
                json={
                    "model": model,
                    "prompt": prompt,
                    "system": system,
                    "stream": False,
                    "options": {"temperature": temperature, "num_predict": 2000},
                },
            )
            resp.raise_for_status()
            return str(resp.json().get("response", ""))

    @activity.defn
    async def fetch_next_task(self, project_id: int, max_priority: int = 2) -> dict | None:
        """Get the next undone low-priority task from Vikunja."""
        tasks = await self.vikunja.list_tasks(project_id)
        for task in sorted(tasks, key=lambda t: -t.get("priority", 0)):
            if not task.get("done") and task.get("priority", 0) <= max_priority:
                return {
                    "id": task["id"],
                    "title": task["title"],
                    "description": task.get("description", ""),
                    "priority": task.get("priority", 0),
                }
        return None

    @activity.defn
    async def plan_task(self, task_title: str, task_description: str) -> list[str]:
        """Ask the planning model to break a task into implementation steps."""
        prompt = (
            f"You are a senior engineer planning a task for a homelab platform called Exousia.\n\n"
            f"Task: {task_title}\n"
            f"Description: {task_description}\n\n"
            f"The codebase uses:\n"
            f"- Python 3.12, Temporal workflows, httpx for HTTP clients\n"
            f"- Podman quadlet containers, systemd user services\n"
            f"- Forgejo (git), Caddy (proxy), Authelia (auth)\n\n"
            f"Output a numbered list of specific implementation steps. "
            f"Each step should name the exact file to create or modify. "
            f"Be concise — 3-7 steps max."
        )
        response = await self._generate(self.planning_model, prompt)
        steps = []
        for line in response.strip().splitlines():
            line = line.strip()
            if line and line[0].isdigit():
                # Strip "1. " prefix
                step = line.split(".", 1)[-1].strip() if "." in line else line
                if step:
                    steps.append(step)
        return steps[:7]

    @activity.defn
    async def read_file_from_repo(self, filepath: str) -> str:
        """Read a file from the Forgejo repo via API."""
        async with self.forgejo._client() as client:
            resp = await client.get(
                f"/repos/{self.forgejo.repo}/raw/{filepath}",
                params={"ref": "uryu/working-dev"},
            )
            if resp.status_code == 200:
                return resp.text
            return ""

    @activity.defn
    async def generate_code(self, filepath: str, existing_content: str, instruction: str) -> str:
        """Ask the coding model to generate or modify code."""
        if existing_content:
            prompt = (
                f"Modify this file according to the instruction.\n\n"
                f"File: {filepath}\n"
                f"Instruction: {instruction}\n\n"
                f"Current content:\n```\n{existing_content[:3000]}\n```\n\n"
                f"Output ONLY the complete modified file content. No explanation."
            )
        else:
            prompt = (
                f"Create a new file.\n\n"
                f"File: {filepath}\n"
                f"Instruction: {instruction}\n\n"
                f"Output ONLY the file content. No explanation."
            )

        response = await self._generate(
            self.coding_model,
            prompt,
            system="You are a Python developer. Output only code, no markdown fences, no explanation.",
            temperature=0.1,
        )

        # Strip markdown code fences if the model added them
        content = response.strip()
        if content.startswith("```"):
            lines = content.splitlines()
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            content = "\n".join(lines)

        return content

    @activity.defn
    async def create_branch_and_pr(
        self,
        branch_name: str,
        files: list[dict],
        title: str,
        body: str,
    ) -> str:
        """Create a branch with file changes and open a PR on Forgejo."""
        async with self.forgejo._client() as client:
            # Create branch from working-dev
            await client.post(
                f"/repos/{self.forgejo.repo}/branches",
                json={"new_branch_name": branch_name, "old_branch_name": "uryu/working-dev"},
            )

            # Commit files to the branch
            for f in files:
                # Check if file exists
                resp = await client.get(
                    f"/repos/{self.forgejo.repo}/contents/{f['path']}",
                    params={"ref": branch_name},
                )
                if resp.status_code == 200:
                    sha = resp.json().get("sha", "")
                    await client.put(
                        f"/repos/{self.forgejo.repo}/contents/{f['path']}",
                        json={
                            "content": __import__("base64").b64encode(f["content"].encode()).decode(),
                            "message": f"agent: {f.get('message', 'update ' + f['path'])}",
                            "branch": branch_name,
                            "sha": sha,
                        },
                    )
                else:
                    await client.post(
                        f"/repos/{self.forgejo.repo}/contents/{f['path']}",
                        json={
                            "content": __import__("base64").b64encode(f["content"].encode()).decode(),
                            "message": f"agent: {f.get('message', 'create ' + f['path'])}",
                            "branch": branch_name,
                        },
                    )

            # Create PR
            resp = await client.post(
                f"/repos/{self.forgejo.repo}/pulls",
                json={
                    "title": f"[agent] {title}",
                    "body": body,
                    "head": branch_name,
                    "base": "uryu/working-dev",
                },
            )
            if resp.status_code in (200, 201):
                return str(resp.json().get("html_url", ""))
            return f"PR creation failed: {resp.status_code}"

    @activity.defn
    async def update_vikunja_task(self, task_id: int, comment: str, done: bool = False) -> None:
        """Update Vikunja task with agent results."""
        await self.vikunja.add_comment(task_id, comment)
        if done:
            await self.vikunja.complete_task(task_id)
