"""Security posture activities — firewalld, SELinux, port auditing."""

import asyncio
from dataclasses import dataclass

from temporalio import activity

from src.clients.podman import PodmanClient


@dataclass
class SecurityFinding:
    category: str  # "port_exposure", "selinux", "firewalld", "container"
    severity: str  # "critical", "warning", "info"
    description: str


class SecurityActivities:
    """Check system security posture — ports, SELinux, firewalld, containers."""

    def __init__(self) -> None:
        self.podman = PodmanClient()

    @activity.defn
    async def check_exposed_ports(self) -> list[SecurityFinding]:
        """Find ports bound to 0.0.0.0 (exposed to network)."""
        proc = await asyncio.create_subprocess_exec(
            "ss", "-tlnp",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()

        findings = []
        for line in stdout.decode().splitlines():
            if "0.0.0.0:" in line and "127.0.0" not in line:
                parts = line.split()
                addr = parts[3] if len(parts) > 3 else "unknown"
                if ":5355" in addr:
                    continue  # mDNS is expected
                findings.append(SecurityFinding(
                    category="port_exposure",
                    severity="warning",
                    description=f"Port exposed to all interfaces: {addr}",
                ))
        return findings

    @activity.defn
    async def check_selinux(self) -> SecurityFinding:
        """Verify SELinux is in enforcing mode."""
        proc = await asyncio.create_subprocess_exec(
            "getenforce",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        mode = stdout.decode().strip()

        if mode == "Enforcing":
            return SecurityFinding("selinux", "info", "SELinux is enforcing")
        return SecurityFinding("selinux", "critical", f"SELinux is {mode} — should be Enforcing")

    @activity.defn
    async def check_firewalld(self) -> SecurityFinding:
        """Verify firewalld is active."""
        proc = await asyncio.create_subprocess_exec(
            "systemctl", "is-active", "firewalld",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        status = stdout.decode().strip()

        if status == "active":
            return SecurityFinding("firewalld", "info", "firewalld is active")
        return SecurityFinding("firewalld", "critical", f"firewalld is {status}")

    @activity.defn
    async def check_container_security(self) -> list[SecurityFinding]:
        """Audit container security labels and privileges."""
        containers = await self.podman.list_containers()
        findings = []

        async with self.podman._client() as client:
            for c in containers:
                name = c["name"]
                resp = await client.get(f"/v4.0.0/libpod/containers/{name}/json")
                if resp.status_code != 200:
                    continue
                data = resp.json()
                host_config = data.get("HostConfig", {})

                if host_config.get("Privileged"):
                    findings.append(SecurityFinding(
                        "container", "warning",
                        f"{name}: running privileged",
                    ))

                if host_config.get("NetworkMode") == "host":
                    findings.append(SecurityFinding(
                        "container", "warning",
                        f"{name}: using host network",
                    ))

        return findings
