"""Operational activities — security scans, deps, changelog, alerts, base image."""

import asyncio
import os
import time
from dataclasses import dataclass

import httpx
from temporalio import activity

FORGEJO_TOKEN = "8275ed637720a8fbb59607a35e68783111b86880"
FORGEJO_API = "http://forgejo:3000/api/v1"


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

    def __init__(self):
        self.ollama_url = os.getenv("OLLAMA_URL", "http://ollama:11434")
        self.openobserve_url = os.getenv("OPENOBSERVE_URL", "http://openobserve:5080")
        self.openobserve_email = os.getenv("ZO_ROOT_USER_EMAIL", "")
        self.openobserve_password = os.getenv("ZO_ROOT_USER_PASSWORD", "")
        self.miniflux_url = os.getenv("MINIFLUX_URL", "http://miniflux:8080")
        self.miniflux_api_key = os.getenv("MINIFLUX_API_KEY", "")

    # --- Miniflux Digest ---

    @activity.defn
    async def fetch_unread_entries(self, limit: int = 20) -> list[dict[str, str]]:
        """Fetch unread RSS entries from Miniflux."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                f"{self.miniflux_url}/v1/entries",
                headers={"X-Auth-Token": self.miniflux_api_key},
                params={"status": "unread", "limit": limit, "order": "published_at", "direction": "desc"},
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
        """Trivy scan all running container images for HIGH+ vulns."""
        # Get list of running images
        proc = await asyncio.create_subprocess_exec(
            "podman", "ps", "--format", "{{.Names}} {{.Image}}",
            stdout=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()

        results = []
        for line in stdout.decode().strip().splitlines():
            parts = line.split(maxsplit=1)
            if len(parts) != 2:
                continue
            name, image = parts

            # Run trivy scan
            scan = await asyncio.create_subprocess_exec(
                "podman", "run", "--rm", "--network=host",
                "docker.io/aquasec/trivy:latest",
                "image", "--severity", "HIGH,CRITICAL",
                "--format", "json", "--quiet", image,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            scan_out, _ = await scan.communicate()

            if scan.returncode != 0:
                continue

            import json

            try:
                data = json.loads(scan_out.decode())
                critical = 0
                high = 0
                cves = []
                for r in data.get("Results", []):
                    for v in r.get("Vulnerabilities", []):
                        cve_id = v["VulnerabilityID"]
                        if v.get("Severity") == "CRITICAL":
                            critical += 1
                            cves.append(cve_id)
                        elif v.get("Severity") == "HIGH":
                            high += 1
                if critical > 0 or high > 0:
                    results.append(ScanResult(
                        container=name, image=image,
                        critical=critical, high=high, cves=cves[:10],
                    ))
            except json.JSONDecodeError:
                continue

        return results

    # --- PR Auto-Review ---

    @activity.defn
    async def get_open_prs(self) -> list[dict[str, str]]:
        """Get open PRs from Forgejo."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                f"{FORGEJO_API}/repos/uryu/exousia/pulls",
                headers={"Authorization": f"token {FORGEJO_TOKEN}"},
                params={"state": "open", "limit": "10"},
            )
            resp.raise_for_status()
            return [
                {"number": str(pr["number"]), "title": pr["title"], "url": pr["html_url"]}
                for pr in resp.json()
            ]

    @activity.defn
    async def get_pr_diff(self, pr_number: str) -> str:
        """Get the diff of a PR."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                f"{FORGEJO_API}/repos/uryu/exousia/pulls/{pr_number}.diff",
                headers={"Authorization": f"token {FORGEJO_TOKEN}"},
            )
            resp.raise_for_status()
            return resp.text[:8000]  # Limit diff size for LLM context

    @activity.defn
    async def post_pr_comment(self, pr_number: str, body: str) -> None:
        """Post a review comment on a PR."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            await client.post(
                f"{FORGEJO_API}/repos/uryu/exousia/issues/{pr_number}/comments",
                headers={"Authorization": f"token {FORGEJO_TOKEN}"},
                json={"body": body},
            )

    # --- Dependency Updates ---

    @activity.defn
    async def check_python_deps(self) -> list[DepUpdate]:
        """Check for outdated Python dependencies."""
        proc = await asyncio.create_subprocess_exec(
            "pip", "list", "--outdated", "--format=json",
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
        """Get conventional commits since last tag."""
        cmd = ["git", "-C", "/workspace", "log", "--pretty=format:%s"]
        if tag:
            cmd.append(f"{tag}..HEAD")
        else:
            cmd.extend(["--since=7 days ago"])

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        return [line for line in stdout.decode().strip().splitlines() if line]

    @activity.defn
    async def get_latest_tag(self) -> str:
        """Get the latest git tag."""
        proc = await asyncio.create_subprocess_exec(
            "git", "-C", "/workspace", "describe", "--tags", "--abbrev=0",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        return stdout.decode().strip() if proc.returncode == 0 else ""

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
            return [f"[{h.get('container', '?')}] {h.get('message', '')}" for h in hits]

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
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{FORGEJO_API}/repos/uryu/exousia/issues",
                headers={"Authorization": f"token {FORGEJO_TOKEN}"},
                json={"title": title, "body": body},
            )
            if resp.status_code in (200, 201):
                return str(resp.json().get("html_url", ""))
            return ""

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
            return {h["container"]: h["count"] for h in resp.json().get("hits", [])}

    # --- Base Image Mirror ---

    @activity.defn
    async def pull_base_image(self) -> str:
        """Pull latest Fedora base image to local registry."""
        source = "quay.io/fedora/fedora-sway-atomic:44"
        proc = await asyncio.create_subprocess_exec(
            "podman", "pull", source,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(f"Pull failed: {stderr.decode()}")
        activity.logger.info(f"Pulled {source}")
        return stdout.decode().strip().splitlines()[-1]

    @activity.defn
    async def push_to_local_registry(self, source: str, target: str) -> None:
        """Tag and push image to local registry."""
        # Tag
        proc = await asyncio.create_subprocess_exec(
            "podman", "tag", source, target,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await proc.communicate()

        # Push
        proc = await asyncio.create_subprocess_exec(
            "podman", "push", "--tls-verify=false", target,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(f"Push failed: {stderr.decode()}")
        activity.logger.info(f"Pushed {target}")
