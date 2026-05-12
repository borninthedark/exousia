"""Backup activities — volume snapshots and pruning."""

import asyncio
from dataclasses import dataclass
from datetime import datetime

from temporalio import activity


@dataclass
class VolumeSnapshot:
    volume: str
    timestamp: str
    size_bytes: int


@dataclass
class BackupResult:
    snapshots: list[VolumeSnapshot]
    pruned: list[str]


class BackupActivities:
    """Activities for podman volume backup and pruning."""

    @activity.defn
    async def list_volumes(self) -> list[str]:
        """List all exousia podman volumes."""
        proc = await asyncio.create_subprocess_exec(
            "podman",
            "volume",
            "ls",
            "--format",
            "{{.Name}}",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        return [v for v in stdout.decode().strip().splitlines() if v]

    @activity.defn
    async def snapshot_volume(self, volume: str) -> VolumeSnapshot:
        """Export a volume to a tarball in the backup directory."""
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup_dir = "/backups"
        filename = f"{volume}-{timestamp}.tar.zst"
        filepath = f"{backup_dir}/{filename}"

        activity.logger.info(f"Snapshotting {volume} -> {filepath}")

        proc = await asyncio.create_subprocess_exec(
            "podman",
            "volume",
            "export",
            volume,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        vol_stdout, vol_stderr = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(f"volume export failed: {vol_stderr.decode()}")

        compress = await asyncio.create_subprocess_exec(
            "zstd",
            "-o",
            filepath,
            stdin=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, zstd_stderr = await compress.communicate(input=vol_stdout)
        if compress.returncode != 0:
            raise RuntimeError(f"compression failed: {zstd_stderr.decode()}")

        stat = await asyncio.create_subprocess_exec(
            "stat",
            "-c",
            "%s",
            filepath,
            stdout=asyncio.subprocess.PIPE,
        )
        size_out, _ = await stat.communicate()

        return VolumeSnapshot(
            volume=volume,
            timestamp=timestamp,
            size_bytes=int(size_out.decode().strip()),
        )

    @activity.defn
    async def prune_old_backups(self, volume: str, keep: int = 7) -> list[str]:
        """Remove backups older than `keep` count for a given volume."""
        import glob
        import os

        backup_dir = "/backups"
        pattern = f"{backup_dir}/{volume}-*.tar.zst"
        files = sorted(glob.glob(pattern), key=os.path.getmtime, reverse=True)

        pruned = []
        for old in files[keep:]:
            os.remove(old)
            pruned.append(old)
            activity.logger.info(f"Pruned {old}")

        return pruned
