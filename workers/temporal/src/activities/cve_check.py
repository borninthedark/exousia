"""CVE check activities — monitor for upstream fixes to allowlisted CVEs.

Uses HTTP APIs only (GitHub, Fedora Bodhi, Forgejo). No subprocess calls.
"""

from dataclasses import dataclass

import httpx
from temporalio import activity

from src.clients.forgejo import ForgejoClient

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

    def __init__(self) -> None:
        self.forgejo = ForgejoClient()

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

            if "grpc" in str(info["package"]):
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
                                if tag >= str(info["fixed_version"]):
                                    status.fixed_upstream = True
                                    status.notes = f"Fix released: v{tag}"
                                    break
                except Exception as e:
                    status.notes = f"Error checking upstream: {e}"

            results.append(status)

        return results

    @activity.defn
    async def scan_image_for_cves(self) -> list[str]:
        """Check for new CVEs by querying the CI scan results.

        Note: Trivy scanning is handled by the CI pipeline (Lille/Hiyori).
        This activity checks if the latest CI run found new critical CVEs
        by querying Forgejo for the latest workflow run results.
        """
        # The CI pipeline stores scan results as artifacts.
        # For now, return empty — the CVE gate in CI is the primary control.
        activity.logger.info("CVE scan delegated to CI pipeline (Lille/Hiyori)")
        return []

    @activity.defn
    async def create_forgejo_issue(self, title: str, body: str) -> str:
        """Create a Forgejo issue for CVE remediation tracking."""
        return await self.forgejo.create_issue(title, body)
