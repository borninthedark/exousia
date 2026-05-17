"""CVE check activities — monitor for upstream fixes to allowlisted CVEs.

Uses NIST NVD API (same pattern as witness/fitness/services/nist_client.py)
to check CVE status and Fedora Bodhi for package availability.
"""

import asyncio
from dataclasses import dataclass

import httpx
from temporalio import activity

NIST_API_BASE = "https://services.nvd.nist.gov/rest/json/cves/2.0"

# Current CVE allowlist — keep in sync with pernida.yml and hiyori.yml
CVE_ALLOWLIST = {
    "CVE-2026-33186": {
        "package": "google.golang.org/grpc",
        "fixed_version": "1.79.3",
        "affected_binaries": ["podman", "buildah"],
        "tracking_url": "https://github.com/grpc/grpc-go/releases",
    },
}


@dataclass
class CVEStatus:
    cve_id: str
    package: str
    fixed_upstream: bool
    fixed_in_fedora: bool
    current_fedora_version: str | None = None
    notes: str | None = None


@dataclass
class CVECheckResult:
    checked: list[CVEStatus]
    removable: list[str]  # CVEs that can be removed from allowlist


class CVECheckActivities:
    """Check if allowlisted CVEs have been fixed upstream or in Fedora."""

    @activity.defn
    async def check_fedora_packages(self) -> list[CVEStatus]:
        """Query Bodhi for latest Fedora package versions."""
        results = []

        for cve_id, info in CVE_ALLOWLIST.items():
            status = CVEStatus(
                cve_id=cve_id,
                package=str(info["package"]),
                fixed_upstream=False,
                fixed_in_fedora=False,
            )

            # Check Fedora Bodhi for podman/buildah updates
            for binary in info["affected_binaries"]:
                try:
                    async with httpx.AsyncClient(timeout=30.0) as client:
                        resp = await client.get(
                            "https://bodhi.fedoraproject.org/updates/",
                            params={
                                "search": binary,
                                "releases": "F44",
                                "status": "stable",
                                "rows_per_page": "3",
                            },
                        )
                        if resp.status_code == 200:
                            data = resp.json()
                            updates = data.get("updates", [])
                            if updates:
                                latest = updates[0].get("title", "")
                                status.current_fedora_version = latest
                                status.notes = f"Latest F44 {binary}: {latest}"
                except Exception as e:
                    status.notes = f"Error checking {binary}: {e}"

            results.append(status)

        return results

    @activity.defn
    async def check_upstream_releases(self) -> list[CVEStatus]:
        """Check upstream GitHub releases for fixes."""
        results = []

        for cve_id, info in CVE_ALLOWLIST.items():
            status = CVEStatus(
                cve_id=cve_id,
                package=str(info["package"]),
                fixed_upstream=False,
                fixed_in_fedora=False,
            )

            # Check grpc-go releases for the fix version
            if "grpc" in info["package"]:
                try:
                    async with httpx.AsyncClient(timeout=30.0) as client:
                        resp = await client.get(
                            "https://api.github.com/repos/grpc/grpc-go/releases",
                            params={"per_page": "5"},
                        )
                        if resp.status_code == 200:
                            releases = resp.json()
                            for rel in releases:
                                tag = rel.get("tag_name", "").lstrip("v")
                                if tag >= info["fixed_version"]:
                                    status.fixed_upstream = True
                                    status.notes = f"Fix released: v{tag}"
                                    break
                except Exception as e:
                    status.notes = f"Error checking upstream: {e}"

            results.append(status)

        return results

    @activity.defn
    async def scan_image_for_cves(self) -> list[str]:
        """Run Trivy scan against local image and return new critical CVEs."""
        proc = await asyncio.create_subprocess_exec(
            "podman",
            "run",
            "--rm",
            "--network=host",
            "docker.io/aquasec/trivy:latest",
            "image",
            "--severity",
            "CRITICAL",
            "--insecure",
            "--format",
            "json",
            "localhost:5000/exousia:latest",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()

        if proc.returncode != 0:
            activity.logger.warning("Trivy scan failed")
            return []

        import json

        try:
            data = json.loads(stdout.decode())
            new_cves = []
            for r in data.get("Results", []):
                for v in r.get("Vulnerabilities", []):
                    if v.get("Severity") == "CRITICAL":
                        cve = v["VulnerabilityID"]
                        if cve not in CVE_ALLOWLIST:
                            new_cves.append(cve)
            return new_cves
        except json.JSONDecodeError:
            return []

    @activity.defn
    async def create_forgejo_issue(self, title: str, body: str) -> str:
        """Create a Forgejo issue for CVE remediation tracking."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                "http://forgejo:3000/api/v1/repos/uryu/exousia/issues",
                headers={"Authorization": "token 8275ed637720a8fbb59607a35e68783111b86880"},
                json={"title": title, "body": body, "labels": []},
            )
            if resp.status_code in (200, 201):
                return str(resp.json().get("html_url", ""))
            raise RuntimeError(f"Failed to create issue: {resp.status_code}")
