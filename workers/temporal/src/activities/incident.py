"""Incident response activities — log analysis, diagnosis, auto-remediation."""

import asyncio
import os
from dataclasses import dataclass

import httpx
from temporalio import activity


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

    def __init__(self):
        self.openobserve_url = os.getenv("OPENOBSERVE_URL", "http://openobserve:5080")
        self.openobserve_email = os.getenv("ZO_ROOT_USER_EMAIL", "")
        self.openobserve_password = os.getenv("ZO_ROOT_USER_PASSWORD", "")
        self.ollama_url = os.getenv("OLLAMA_URL", "http://ollama:11434")
        self.ollama_model = os.getenv("OLLAMA_MODEL", "qwen3:8b")

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
                        "sql": f"SELECT message FROM systemd WHERE container = '{container}' ORDER BY _timestamp DESC LIMIT 50",
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
            return [hit.get("message", "") for hit in data.get("hits", [])]

    @activity.defn
    async def diagnose_with_llm(self, context: IncidentContext) -> str:
        """Ask Qwen3 to diagnose the issue from logs."""
        logs_text = "\n".join(context.logs[:30]) if context.logs else "No logs available"

        prompt = f"""You are a systems engineer diagnosing a container issue.

Container: {context.container}
Trigger: {context.trigger}

Recent logs:
{logs_text}

Provide a brief diagnosis (2-3 sentences) and recommend one action:
- "restart" if it's a transient issue
- "investigate" if it needs human attention
- "ignore" if it's a known harmless pattern

Format: DIAGNOSIS: <text> ACTION: <restart|investigate|ignore>"""

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
        """Restart a container service."""
        proc = await asyncio.create_subprocess_exec(
            "systemctl",
            "--user",
            "restart",
            container,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()

        if proc.returncode != 0:
            return RemediationResult(
                container=container,
                action="restarted",
                success=False,
                details=stderr.decode(),
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
        body = f"""## Incident: {context.container}

**Trigger:** {context.trigger}
**Diagnosis:** {context.diagnosis}

### Recent Logs
```
{logs_snippet}
```

### Recommended Action
Manual investigation required.
"""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    "http://forgejo:3000/api/v1/repos/uryu/exousia/issues",
                    headers={"Authorization": "token 8275ed637720a8fbb59607a35e68783111b86880"},
                    json={
                        "title": f"Incident: {context.container} — {context.trigger}",
                        "body": body,
                    },
                )
                success = resp.status_code in (200, 201)
                url = resp.json().get("html_url", "") if success else ""
                return RemediationResult(
                    container=context.container,
                    action="issue_created",
                    success=success,
                    details=url,
                )
        except Exception as e:
            return RemediationResult(
                container=context.container,
                action="issue_created",
                success=False,
                details=str(e),
            )
