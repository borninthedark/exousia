"""OpenObserve activities — log queries and anomaly detection."""

import os
import time

import httpx
from temporalio import activity


class ObserveActivities:
    """Activities for querying OpenObserve log data."""

    def __init__(self) -> None:
        self.url = os.getenv("OPENOBSERVE_URL", "http://openobserve:5080")
        self.email = os.getenv("ZO_ROOT_USER_EMAIL", "")
        self.password = os.getenv("ZO_ROOT_USER_PASSWORD", "")

    def _auth(self) -> tuple[str, str]:
        return (self.email, self.password)

    async def _search(self, sql: str, minutes: int) -> dict:
        """Execute a search query against OpenObserve."""
        now = int(time.time() * 1_000_000)
        start = now - (minutes * 60 * 1_000_000)

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{self.url}/api/default/_search",
                auth=self._auth(),
                json={
                    "query": {
                        "sql": sql,
                        "start_time": start,
                        "end_time": now,
                        "from": 0,
                        "size": 100,
                    }
                },
            )
            if resp.status_code != 200:
                return {"hits": []}
            return resp.json()

    @activity.defn
    async def query_daily_logs(self) -> list[str]:
        """Get today's important log entries (priority ≤ 4)."""
        data = await self._search(
            "SELECT container, message FROM systemd "
            "WHERE priority <= '4' AND container != '' "
            "ORDER BY _timestamp DESC LIMIT 100",
            minutes=1440,
        )
        return [
            f"[{h.get('container', '?')}] {h.get('message', '')}"
            for h in data.get("hits", [])
        ]

    @activity.defn
    async def check_error_rate(self, minutes: int = 15) -> dict[str, int]:
        """Error counts per container in last N minutes."""
        data = await self._search(
            "SELECT container, COUNT(*) as count FROM systemd "
            "WHERE priority <= '3' AND container != '' "
            "GROUP BY container ORDER BY count DESC",
            minutes=minutes,
        )
        return {
            str(h["container"]): int(h["count"])
            for h in data.get("hits", [])
        }
