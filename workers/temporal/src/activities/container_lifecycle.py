"""Container lifecycle activities — image updates, rolling restarts, rollback.

Uses Podman REST API via socket — no subprocess calls.
"""

import asyncio
from dataclasses import dataclass

from temporalio import activity

from src.clients.podman import PodmanClient
from src.clients.systemd import SystemdClient


@dataclass
class UpdateResult:
    container: str
    updated: bool
    old_image: str | None = None
    new_image: str | None = None
    error: str | None = None


@dataclass
class RestartResult:
    container: str
    healthy: bool
    error: str | None = None


class ContainerLifecycleActivities:
    """Manage container image updates and rolling restarts."""

    def __init__(self) -> None:
        self.podman = PodmanClient()
        self.systemd = SystemdClient()

    @activity.defn
    async def check_updates(self) -> list[UpdateResult]:
        """Check which containers have newer images available."""
        updates = await self.podman.check_image_updates()
        return [
            UpdateResult(
                container=u["container"],
                updated=True,
                new_image=u["image"],
            )
            for u in updates
        ]

    @activity.defn
    async def pull_image(self, image: str) -> str:
        """Pull the latest version of an image."""
        image_id = await self.podman.pull_image(image)
        activity.logger.info(f"Pulled {image} -> {image_id}")
        return image_id

    @activity.defn
    async def restart_service(self, service: str) -> RestartResult:
        """Restart a container and verify health."""
        success = await self.systemd.restart_container(service)
        if not success:
            return RestartResult(container=service, healthy=False, error="restart failed")

        # Wait for healthcheck to settle
        await asyncio.sleep(15)

        # Check health via Podman API
        healthy = await self.podman.healthcheck_run(service)
        return RestartResult(container=service, healthy=healthy)

    @activity.defn
    async def prune_images(self) -> str:
        """Remove dangling and unused images after updates."""
        pruned = await self.podman.prune_images()
        activity.logger.info(f"Image prune: {len(pruned)} images removed")
        return f"{len(pruned)} images pruned"

    @activity.defn
    async def rollback_service(self, service: str) -> RestartResult:
        """Rollback a service by restarting with the previous image."""
        success = await self.systemd.restart_container(service)
        if not success:
            return RestartResult(container=service, healthy=False, error="rollback restart failed")
        await asyncio.sleep(10)
        return RestartResult(container=service, healthy=True)
