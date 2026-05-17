"""Operational activities — PR review, deps, changelog, base image.

Thin wrappers around ForgejoClient and PodmanClient for Temporal activity registration.
"""

import asyncio
from dataclasses import dataclass

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


class OperationsActivities:
    """Thin activity wrappers for Forgejo and Podman operations."""

    def __init__(self) -> None:
        self.podman = PodmanClient()
        self.forgejo = ForgejoClient()

    # --- Security Scan ---

    @activity.defn
    async def scan_running_images(self) -> list[ScanResult]:
        """Get running container image inventory."""
        containers = await self.podman.list_containers()
        return [
            ScanResult(
                container=c["name"], image=c["image"],
                critical=0, high=0, cves=[],
            )
            for c in containers
        ]

    # --- PR Review ---

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
        """Check for outdated Python dependencies."""
        import json

        proc = await asyncio.create_subprocess_exec(
            "pip", "list", "--outdated", "--format=json",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()

        try:
            packages = json.loads(stdout.decode())
            return [
                DepUpdate(
                    package=p["name"], current=p["version"],
                    latest=p["latest_version"], repo="exousia",
                )
                for p in packages[:20]
            ]
        except (json.JSONDecodeError, KeyError):
            return []

    # --- Changelog ---

    @activity.defn
    async def get_commits_since_tag(self, tag: str = "") -> list[str]:
        """Get commit messages since last tag via Forgejo API."""
        return await self.forgejo.get_commits_since_tag(tag)

    @activity.defn
    async def get_latest_tag(self) -> str:
        """Get the latest git tag via Forgejo API."""
        return await self.forgejo.get_latest_tag()

    # --- Issue Creation ---

    @activity.defn
    async def create_forgejo_issue(self, title: str, body: str) -> str:
        """Create a Forgejo issue."""
        return await self.forgejo.create_issue(title, body)

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
        if ":" in target.split("/")[-1]:
            repo, tag = target.rsplit(":", 1)
        else:
            repo, tag = target, "latest"

        await self.podman.tag_image(source, repo, tag)
        await self.podman.push_image(target, tls_verify=False)
        activity.logger.info(f"Pushed {target}")
