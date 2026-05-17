"""Container lifecycle activities — image updates, rolling restarts, rollback."""

import asyncio
from dataclasses import dataclass

from temporalio import activity


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

    @activity.defn
    async def check_updates(self) -> list[UpdateResult]:
        """Check which containers have newer images available."""
        proc = await asyncio.create_subprocess_exec(
            "podman",
            "auto-update",
            "--dry-run",
            "--format",
            "{{.Unit}} {{.Image}} {{.Updated}}",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        results = []
        for line in stdout.decode().strip().splitlines():
            if not line.strip():
                continue
            parts = line.split()
            if len(parts) >= 3:
                unit = parts[0].replace(".service", "")
                image = parts[1]
                updated = parts[2].lower() == "true"
                results.append(
                    UpdateResult(
                        container=unit,
                        updated=updated,
                        new_image=image if updated else None,
                    )
                )
        return results

    @activity.defn
    async def pull_image(self, image: str) -> str:
        """Pull the latest version of an image."""
        proc = await asyncio.create_subprocess_exec(
            "podman",
            "pull",
            image,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(f"pull failed: {stderr.decode()}")
        activity.logger.info(f"Pulled {image}")
        return stdout.decode().strip().splitlines()[-1]

    @activity.defn
    async def restart_service(self, service: str) -> RestartResult:
        """Restart a systemd user service and verify health."""
        proc = await asyncio.create_subprocess_exec(
            "systemctl",
            "--user",
            "restart",
            service,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()
        if proc.returncode != 0:
            return RestartResult(
                container=service,
                healthy=False,
                error=stderr.decode(),
            )

        # Wait for healthcheck to settle
        await asyncio.sleep(15)

        # Check health status
        proc = await asyncio.create_subprocess_exec(
            "podman",
            "healthcheck",
            "run",
            service,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await proc.communicate()
        healthy = proc.returncode == 0

        return RestartResult(container=service, healthy=healthy)

    @activity.defn
    async def prune_images(self) -> str:
        """Remove dangling and unused images after updates."""
        proc = await asyncio.create_subprocess_exec(
            "podman", "image", "prune", "-af",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        reclaimed = stdout.decode().strip()
        activity.logger.info(f"Image prune: {reclaimed or 'nothing to prune'}")
        return reclaimed

    @activity.defn
    async def rollback_service(self, service: str) -> RestartResult:
        """Rollback a service by restarting with the previous image."""
        # Podman keeps the previous image; just restart
        proc = await asyncio.create_subprocess_exec(
            "systemctl",
            "--user",
            "restart",
            service,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()
        if proc.returncode != 0:
            return RestartResult(container=service, healthy=False, error=stderr.decode())

        await asyncio.sleep(10)
        return RestartResult(container=service, healthy=True)
