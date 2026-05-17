"""Backup activities — volume snapshots and pruning via Podman API."""

import os
from dataclasses import dataclass
from datetime import datetime

from temporalio import activity

from src.clients.podman import PodmanClient


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

    def __init__(self) -> None:
        self.podman = PodmanClient()
        self.backup_dir = "/backups"

    @activity.defn
    async def list_volumes(self) -> list[str]:
        """List all exousia podman volumes."""
        return await self.podman.list_volumes()

    @activity.defn
    async def snapshot_volume(self, volume: str) -> VolumeSnapshot:
        """Export a volume to a compressed tarball in the backup directory."""
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        filename = f"{volume}-{timestamp}.tar.zst"
        filepath = f"{self.backup_dir}/{filename}"

        activity.logger.info(f"Snapshotting {volume} -> {filepath}")

        # Export volume via Podman API
        vol_data = await self.podman.export_volume(volume)

        # Compress with zstandard (Python library)
        import zstandard

        cctx = zstandard.ZstdCompressor()
        compressed = cctx.compress(vol_data)

        # Write to backup dir
        os.makedirs(self.backup_dir, exist_ok=True)
        with open(filepath, "wb") as f:
            f.write(compressed)

        return VolumeSnapshot(
            volume=volume,
            timestamp=timestamp,
            size_bytes=os.path.getsize(filepath),
        )

    @activity.defn
    async def prune_old_backups(self, volume: str, keep: int = 7) -> list[str]:
        """Remove backups older than `keep` count for a given volume."""
        import glob

        pattern = f"{self.backup_dir}/{volume}-*.tar.zst"
        files = sorted(glob.glob(pattern), key=os.path.getmtime, reverse=True)

        pruned = []
        for old in files[keep:]:
            os.remove(old)
            pruned.append(old)
            activity.logger.info(f"Pruned {old}")

        return pruned
