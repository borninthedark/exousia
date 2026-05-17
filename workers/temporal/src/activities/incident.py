"""Incident response activities — log analysis, diagnosis, auto-remediation.

Uses HTTP APIs only — no subprocess calls.
"""

import os
from dataclasses import dataclass

import httpx
from temporalio import activity

from src.clients.forgejo import ForgejoClient
from src.clients.systemd import SystemdClient


@dataclass
class IncidentContext:
    container: str
    trigger: str  # "unhealthy", "error_spike", "crash_loop"
    logs: list[str] | None = None
    diagnosis: str | None = None


@dataclass
class RemediationResult:
    container: str
    action: str  # "restarted", "issue_created", "escalated"
    success: bool
    details: str | None = None


class IncidentActivities:
    """Automated incident response: detect, diagnose, remediate."""

    def __init__(self) -> None:
        self.openobserve_url = os.getenv("OPENOBSERVE_URL", "http://openobserve:5080")
        self.openobserve_email = os.getenv("ZO_ROOT_USER_EMAIL", "")
        self.openobserve_password = os.getenv("ZO_ROOT_USER_PASSWORD", "")
        self.ollama_url = os.getenv("OLLAMA_URL", "http://ollama:11434")
        self.ollama_model = os.getenv("OLLAMA_MODEL", "qwen3:8b")
        self.systemd = SystemdClient()
        self.forgejo = ForgejoClient()

    @activity.defn
    async def query_recent_logs(self, container: str, minutes: int = 5) -> list[str]:
        """Pull recent logs for a container from OpenObserve."""
        import time

        now = int(time.time() * 1_000_000)
        start = now - (minutes * 60 * 1_000_000)

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{self.openobserve_url}/api/default/_search",
                auth=(self.openobserve_email, self.openobserve_password),
                json={
                    "query": {
                        "sql": (
                            f"SELECT message FROM systemd "
                            f"WHERE container = '{container}' "
                            f"ORDER BY _timestamp DESC LIMIT 50"
                        ),
                        "start_time": start,
                        "end_time": now,
                        "from": 0,
                        "size": 50,
                    }
                },
            )
            if resp.status_code != 200:
                return [f"Failed to query logs: {resp.status_code}"]

            data = resp.json()
            return [str(hit.get("message", "")) for hit in data.get("hits", [])]

    @activity.defn
    async def diagnose_with_llm(self, context: IncidentContext) -> str:
        """Ask Qwen3 to diagnose the issue from logs."""
        logs_text = "\n".join(context.logs[:30]) if context.logs else "No logs available"

        prompt = (
            f"You are a systems engineer diagnosing a container issue.\n\n"
            f"Container: {context.container}\n"
            f"Trigger: {context.trigger}\n\n"
            f"Recent logs:\n{logs_text}\n\n"
            f"Provide a brief diagnosis (2-3 sentences) and recommend one action:\n"
            f'- "restart" if it\'s a transient issue\n'
            f'- "investigate" if it needs human attention\n'
            f'- "ignore" if it\'s a known harmless pattern\n\n'
            f"Format: DIAGNOSIS: <text> ACTION: <restart|investigate|ignore>"
        )

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(
                    f"{self.ollama_url}/api/generate",
                    json={
                        "model": self.ollama_model,
                        "prompt": prompt,
                        "stream": False,
                        "options": {"temperature": 0.3, "num_predict": 200},
                    },
                )
                if resp.status_code == 200:
                    return str(resp.json().get("response", "No response"))
                return f"LLM error: {resp.status_code}"
        except Exception as e:
            return f"LLM unavailable: {e}"

    @activity.defn
    async def restart_container(self, container: str) -> RemediationResult:
        """Restart a container via Podman API."""
        import asyncio

        success = await self.systemd.restart_container(container)

        if not success:
            return RemediationResult(
                container=container,
                action="restarted",
                success=False,
                details="Podman restart API returned failure",
            )

        await asyncio.sleep(10)
        return RemediationResult(
            container=container,
            action="restarted",
            success=True,
        )

    @activity.defn
    async def create_incident_issue(self, context: IncidentContext) -> RemediationResult:
        """Create a Forgejo issue for manual investigation."""
        logs_snippet = "\n".join(context.logs[:10]) if context.logs else "No logs"
        body = (
            f"## Incident: {context.container}\n\n"
            f"**Trigger:** {context.trigger}\n"
            f"**Diagnosis:** {context.diagnosis}\n\n"
            f"### Recent Logs\n```\n{logs_snippet}\n```\n\n"
            f"### Recommended Action\nManual investigation required.\n"
        )
        try:
            url = await self.forgejo.create_issue(
                title=f"Incident: {context.container} — {context.trigger}",
                body=body,
            )
            return RemediationResult(
                container=context.container,
                action="issue_created",
                success=True,
                details=url,
            )
        except Exception as e:
            return RemediationResult(
                container=context.container,
                action="issue_created",
                success=False,
                details=str(e),
            )
