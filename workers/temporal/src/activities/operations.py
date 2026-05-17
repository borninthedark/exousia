"""Operational activities — security scans, deps, changelog, alerts, base image.

Uses HTTP APIs (Podman socket, Forgejo, Miniflux, OpenObserve, Ollama).
No subprocess calls except `pip` which runs inside the container.
"""

import os
import time
from dataclasses import dataclass

import httpx
from temporalio import activity

from src.clients.forgejo import ForgejoClient
from src.clients.podman import PodmanClient


@dataclass
class ScanResult:
    container: str
    image: str
    critical: int
    high: int
    cves: list[str]


@dataclass
class DepUpdate:
    package: str
    current: str
    latest: str
    repo: str


@dataclass
class AlertPayload:
    title: str
    body: str
    severity: str  # "critical", "warning", "info"


class OperationsActivities:
    """Operational activities for security, deps, alerting, and infra."""

    def __init__(self) -> None:
        self.ollama_url = os.getenv("OLLAMA_URL", "http://ollama:11434")
        self.openobserve_url = os.getenv("OPENOBSERVE_URL", "http://openobserve:5080")
        self.openobserve_email = os.getenv("ZO_ROOT_USER_EMAIL", "")
        self.openobserve_password = os.getenv("ZO_ROOT_USER_PASSWORD", "")
        self.miniflux_url = os.getenv("MINIFLUX_URL", "http://miniflux:8080")
        self.miniflux_api_key = os.getenv("MINIFLUX_API_KEY", "")
        self.podman = PodmanClient()
        self.forgejo = ForgejoClient()

    # --- Miniflux Digest ---

    @activity.defn
    async def fetch_unread_entries(self, limit: int = 20) -> list[dict[str, str]]:
        """Fetch unread RSS entries from Miniflux."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                f"{self.miniflux_url}/v1/entries",
                headers={"X-Auth-Token": self.miniflux_api_key},
                params={
                    "status": "unread",
                    "limit": limit,
                    "order": "published_at",
                    "direction": "desc",
                },
            )
            resp.raise_for_status()
            entries = resp.json().get("entries", [])
            return [
                {
                    "id": str(e["id"]),
                    "title": e["title"],
                    "url": e["url"],
                    "feed": e.get("feed", {}).get("title", ""),
                    "content": e.get("content", "")[:2000],
                }
                for e in entries
            ]

    @activity.defn
    async def mark_entries_read(self, entry_ids: list[str]) -> None:
        """Mark entries as read in Miniflux."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            await client.put(
                f"{self.miniflux_url}/v1/entries",
                headers={"X-Auth-Token": self.miniflux_api_key},
                json={"entry_ids": [int(e) for e in entry_ids], "status": "read"},
            )

    # --- Podman Security Scan ---

    @activity.defn
    async def scan_running_images(self) -> list[ScanResult]:
        """Get list of running images for security audit.

        Note: Trivy scanning requires the trivy binary which isn't available
        in the worker container. This activity collects the image inventory.
        Full scanning is handled by the CI pipeline (Lille/Hiyori).
        """
        containers = await self.podman.list_containers()
        return [
            ScanResult(
                container=c["name"],
                image=c["image"],
                critical=0,
                high=0,
                cves=[],
            )
            for c in containers
        ]

    # --- PR Auto-Review ---

    @activity.defn
    async def get_open_prs(self) -> list[dict[str, str]]:
        """Get open PRs from Forgejo."""
        return await self.forgejo.get_open_prs()

    @activity.defn
    async def get_pr_diff(self, pr_number: str) -> str:
        """Get the diff of a PR."""
        return await self.forgejo.get_pr_diff(pr_number)

    @activity.defn
    async def post_pr_comment(self, pr_number: str, body: str) -> None:
        """Post a review comment on a PR."""
        await self.forgejo.post_pr_comment(pr_number, body)

    # --- Dependency Updates ---

    @activity.defn
    async def check_python_deps(self) -> list[DepUpdate]:
        """Check for outdated Python dependencies (pip runs inside container)."""
        import asyncio

        proc = await asyncio.create_subprocess_exec(
            "pip",
            "list",
            "--outdated",
            "--format=json",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()

        import json

        try:
            packages = json.loads(stdout.decode())
            return [
                DepUpdate(
                    package=p["name"],
                    current=p["version"],
                    latest=p["latest_version"],
                    repo="exousia",
                )
                for p in packages[:20]
            ]
        except (json.JSONDecodeError, KeyError):
            return []

    # --- Changelog Generation ---

    @activity.defn
    async def get_commits_since_tag(self, tag: str = "") -> list[str]:
        """Get commit messages since last tag via Forgejo API."""
        return await self.forgejo.get_commits_since_tag(tag)

    @activity.defn
    async def get_latest_tag(self) -> str:
        """Get the latest git tag via Forgejo API."""
        return await self.forgejo.get_latest_tag()

    # --- Journal to Knowledge ---

    @activity.defn
    async def query_daily_logs(self) -> list[str]:
        """Get today's important log entries from OpenObserve."""
        now = int(time.time() * 1_000_000)
        start = now - (24 * 60 * 60 * 1_000_000)

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{self.openobserve_url}/api/default/_search",
                auth=(self.openobserve_email, self.openobserve_password),
                json={
                    "query": {
                        "sql": (
                            "SELECT container, message FROM systemd "
                            "WHERE priority <= '4' AND container != '' "
                            "ORDER BY _timestamp DESC LIMIT 100"
                        ),
                        "start_time": start,
                        "end_time": now,
                        "from": 0,
                        "size": 100,
                    }
                },
            )
            if resp.status_code != 200:
                return []
            hits = resp.json().get("hits", [])
            return [
                f"[{h.get('container', '?')}] {h.get('message', '')}"
                for h in hits
            ]

    # --- Alerting ---

    @activity.defn
    async def send_email_alert(self, alert: AlertPayload) -> bool:
        """Send alert via SMTP (Proton Mail)."""
        try:
            import aiosmtplib
            from email.message import EmailMessage

            msg = EmailMessage()
            msg["Subject"] = f"[{alert.severity.upper()}] {alert.title}"
            msg["From"] = "info@princetonstrong.online"
            msg["To"] = "info@princetonstrong.online"
            msg.set_content(alert.body)

            await aiosmtplib.send(
                msg,
                hostname="smtp.protonmail.ch",
                port=465,
                use_tls=True,
                username="info@princetonstrong.online",
                password=os.getenv("SMTP_PASSWORD", ""),
            )
            return True
        except Exception as e:
            activity.logger.error(f"Email alert failed: {e}")
            return False

    @activity.defn
    async def create_forgejo_issue(self, title: str, body: str) -> str:
        """Create a Forgejo issue."""
        return await self.forgejo.create_issue(title, body)

    # --- Log Anomaly Detection ---

    @activity.defn
    async def check_error_rate(self, minutes: int = 15) -> dict[str, int]:
        """Query OpenObserve for error counts per container in last N minutes."""
        now = int(time.time() * 1_000_000)
        start = now - (minutes * 60 * 1_000_000)

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{self.openobserve_url}/api/default/_search",
                auth=(self.openobserve_email, self.openobserve_password),
                json={
                    "query": {
                        "sql": (
                            "SELECT container, COUNT(*) as count FROM systemd "
                            "WHERE priority <= '3' AND container != '' "
                            "GROUP BY container ORDER BY count DESC"
                        ),
                        "start_time": start,
                        "end_time": now,
                        "from": 0,
                        "size": 50,
                    }
                },
            )
            if resp.status_code != 200:
                return {}
            return {
                str(h["container"]): int(h["count"])
                for h in resp.json().get("hits", [])
            }

    # --- Base Image Mirror ---

    @activity.defn
    async def pull_base_image(self) -> str:
        """Pull latest Fedora base image via Podman API."""
        source = "quay.io/fedora/fedora-sway-atomic:44"
        image_id = await self.podman.pull_image(source)
        activity.logger.info(f"Pulled {source} -> {image_id}")
        return image_id

    @activity.defn
    async def push_to_local_registry(self, source: str, target: str) -> None:
        """Tag and push image to local registry via Podman API."""
        # Parse target into repo:tag
        if ":" in target.split("/")[-1]:
            repo, tag = target.rsplit(":", 1)
        else:
            repo, tag = target, "latest"

        await self.podman.tag_image(source, repo, tag)
        await self.podman.push_image(target, tls_verify=False)
        activity.logger.info(f"Pushed {target}")
