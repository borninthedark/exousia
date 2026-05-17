"""Miniflux activities — RSS feed management."""

import os
from dataclasses import dataclass

import httpx
from temporalio import activity


class MinifluxActivities:
    """Activities for interacting with the Miniflux RSS reader API."""

    def __init__(self) -> None:
        self.url = os.getenv("MINIFLUX_URL", "http://miniflux:8080")
        self.api_key = os.getenv("MINIFLUX_API_KEY", "")

    def _headers(self) -> dict[str, str]:
        return {"X-Auth-Token": self.api_key}

    @activity.defn
    async def fetch_unread_entries(self, limit: int = 20) -> list[dict[str, str]]:
        """Fetch unread RSS entries from Miniflux."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                f"{self.url}/v1/entries",
                headers=self._headers(),
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
                f"{self.url}/v1/entries",
                headers=self._headers(),
                json={"entry_ids": [int(e) for e in entry_ids], "status": "read"},
            )
