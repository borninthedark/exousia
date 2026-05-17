"""Systemd D-Bus client — restart services via the D-Bus socket.

Replaces `systemctl --user restart <service>` subprocess calls.
Requires the D-Bus user session socket mounted into the container.
"""

from __future__ import annotations

import httpx


class SystemdClient:
    """Manage systemd user services via the Varlink/HTTP API.

    Since direct D-Bus from a container is complex, this uses
    a simpler approach: call the Podman API to restart containers
    directly, which achieves the same effect as systemctl restart.
    """

    def __init__(self, socket_path: str = "/var/run/podman/podman.sock"):
        self.socket_path = socket_path
        self.base = "http://d"

    def _client(self) -> httpx.AsyncClient:
        transport = httpx.AsyncHTTPTransport(uds=self.socket_path)
        return httpx.AsyncClient(transport=transport, base_url=self.base, timeout=120.0)

    async def restart_container(self, name: str) -> bool:
        """Restart a container by name. Returns True on success."""
        async with self._client() as client:
            resp = await client.post(f"/v4.0.0/libpod/containers/{name}/restart")
            return resp.status_code == 204

    async def stop_container(self, name: str) -> bool:
        """Stop a container by name."""
        async with self._client() as client:
            resp = await client.post(f"/v4.0.0/libpod/containers/{name}/stop")
            return resp.status_code == 204

    async def start_container(self, name: str) -> bool:
        """Start a container by name."""
        async with self._client() as client:
            resp = await client.post(f"/v4.0.0/libpod/containers/{name}/start")
            return resp.status_code == 204
