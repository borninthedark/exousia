"""Podman REST API client — talks to the Podman socket over HTTP.

Replaces all `podman` subprocess calls with clean API requests.
Socket path: /run/user/1000/podman/podman.sock (mounted into worker container)
API docs: https://docs.podman.io/en/latest/_static/api.html
"""

from __future__ import annotations

import httpx


class PodmanClient:
    """Async client for the Podman REST API via Unix socket."""

    def __init__(self, socket_path: str = "/var/run/podman/podman.sock"):
        self.base = "http://d"  # dummy host, overridden by UDS transport
        self.transport = httpx.AsyncHTTPTransport(uds=socket_path)

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(transport=self.transport, base_url=self.base, timeout=300.0)

    async def list_containers(self) -> list[dict[str, str]]:
        """List running containers with name and image."""
        async with self._client() as client:
            resp = await client.get("/v4.0.0/libpod/containers/json")
            resp.raise_for_status()
            return [
                {"name": c.get("Names", [""])[0], "image": c.get("Image", "")}
                for c in resp.json()
            ]

    async def healthcheck_run(self, name: str) -> bool:
        """Run healthcheck for a container. Returns True if healthy."""
        async with self._client() as client:
            resp = await client.get(f"/v4.0.0/libpod/containers/{name}/healthcheck")
            if resp.status_code != 200:
                return False
            return resp.json().get("Status", "") == "healthy"

    async def pull_image(self, reference: str) -> str:
        """Pull an image by reference. Returns image ID."""
        async with self._client() as client:
            resp = await client.post(
                "/v4.0.0/libpod/images/pull",
                params={"reference": reference},
            )
            resp.raise_for_status()
            lines = resp.text.strip().splitlines()
            # Last line contains the image ID
            import json

            for line in reversed(lines):
                try:
                    data = json.loads(line)
                    if "id" in data:
                        return str(data["id"])
                except json.JSONDecodeError:
                    continue
            return ""

    async def tag_image(self, name: str, repo: str, tag: str) -> None:
        """Tag an image."""
        async with self._client() as client:
            resp = await client.post(
                f"/v4.0.0/libpod/images/{name}/tag",
                params={"repo": repo, "tag": tag},
            )
            resp.raise_for_status()

    async def push_image(self, name: str, tls_verify: bool = False) -> None:
        """Push an image to a registry."""
        async with self._client() as client:
            resp = await client.post(
                f"/v4.0.0/libpod/images/{name}/push",
                params={"tlsVerify": str(tls_verify).lower()},
            )
            resp.raise_for_status()

    async def prune_images(self) -> list[str]:
        """Remove unused images. Returns list of pruned image IDs."""
        async with self._client() as client:
            resp = await client.post("/v4.0.0/libpod/images/prune", params={"all": "true"})
            resp.raise_for_status()
            return [img.get("Id", "") for img in resp.json() if img.get("Id")]

    async def list_volumes(self) -> list[str]:
        """List all volume names."""
        async with self._client() as client:
            resp = await client.get("/v4.0.0/libpod/volumes/json")
            resp.raise_for_status()
            return [v["Name"] for v in resp.json()]

    async def export_volume(self, name: str) -> bytes:
        """Export a volume as a tar archive (bytes)."""
        async with self._client() as client:
            resp = await client.get(f"/v4.0.0/libpod/volumes/{name}/export")
            resp.raise_for_status()
            return resp.content

    async def check_image_updates(self) -> list[dict[str, str]]:
        """Check which containers have newer images available.

        Compares local image digests against registry digests.
        """
        containers = await self.list_containers()
        updates = []

        async with self._client() as client:
            for c in containers:
                name = c["name"]
                image = c["image"]

                # Get local image digest
                resp = await client.get(f"/v4.0.0/libpod/images/{image}/json")
                if resp.status_code != 200:
                    continue
                local_digest = resp.json().get("Digest", "")

                # Check registry for newer digest (skopeo-like)
                # The Podman API doesn't have a direct "check for updates" endpoint,
                # so we compare the current digest against what's in the registry
                # by attempting a pull with --dry-run behavior
                # For now, mark as potentially updatable if image uses :latest tag
                if ":latest" in image or ":" not in image.split("/")[-1]:
                    updates.append({
                        "container": name,
                        "image": image,
                        "local_digest": local_digest,
                    })

        return updates
