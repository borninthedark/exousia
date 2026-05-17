"""Forgejo REST API client — replaces git subprocess calls.

Provides commit history, tag info, and issue management
without requiring git CLI inside the container.
"""

from __future__ import annotations

import os

import httpx

FORGEJO_API = os.getenv("FORGEJO_API", "http://forgejo:3000/api/v1")
FORGEJO_TOKEN = os.getenv("FORGEJO_TOKEN", "8275ed637720a8fbb59607a35e68783111b86880")
FORGEJO_REPO = os.getenv("FORGEJO_REPO", "uryu/exousia")


class ForgejoClient:
    """Async client for the Forgejo REST API."""

    def __init__(
        self,
        api_url: str = FORGEJO_API,
        token: str = FORGEJO_TOKEN,
        repo: str = FORGEJO_REPO,
    ):
        self.api_url = api_url
        self.token = token
        self.repo = repo
        self.headers = {"Authorization": f"token {self.token}"}

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=self.api_url,
            headers=self.headers,
            timeout=30.0,
        )

    async def get_latest_tag(self) -> str:
        """Get the latest release tag name."""
        async with self._client() as client:
            resp = await client.get(f"/repos/{self.repo}/releases", params={"limit": "1"})
            if resp.status_code == 200 and resp.json():
                return str(resp.json()[0].get("tag_name", ""))
        return ""

    async def get_commits_since_tag(self, tag: str = "") -> list[str]:
        """Get commit messages since a tag (or last 50 if no tag)."""
        async with self._client() as client:
            params: dict[str, str] = {"limit": "50"}
            if tag:
                # Get the tag's commit SHA first
                resp = await client.get(f"/repos/{self.repo}/git/refs/tags/{tag}")
                if resp.status_code == 200:
                    tag_sha = resp.json()[0].get("object", {}).get("sha", "")
                    if tag_sha:
                        params["sha"] = tag_sha

            resp = await client.get(f"/repos/{self.repo}/commits", params=params)
            if resp.status_code != 200:
                return []
            return [
                c.get("commit", {}).get("message", "").split("\n")[0]
                for c in resp.json()
            ]

    async def get_open_prs(self) -> list[dict[str, str]]:
        """Get open pull requests."""
        async with self._client() as client:
            resp = await client.get(
                f"/repos/{self.repo}/pulls",
                params={"state": "open", "limit": "10"},
            )
            resp.raise_for_status()
            return [
                {
                    "number": str(pr["number"]),
                    "title": pr["title"],
                    "url": pr["html_url"],
                }
                for pr in resp.json()
            ]

    async def get_pr_diff(self, pr_number: str) -> str:
        """Get the diff of a pull request."""
        async with self._client() as client:
            resp = await client.get(f"/repos/{self.repo}/pulls/{pr_number}.diff")
            resp.raise_for_status()
            return resp.text[:8000]

    async def post_pr_comment(self, pr_number: str, body: str) -> None:
        """Post a comment on a PR/issue."""
        async with self._client() as client:
            await client.post(
                f"/repos/{self.repo}/issues/{pr_number}/comments",
                json={"body": body},
            )

    async def create_issue(self, title: str, body: str) -> str:
        """Create an issue. Returns the HTML URL."""
        async with self._client() as client:
            resp = await client.post(
                f"/repos/{self.repo}/issues",
                json={"title": title, "body": body},
            )
            if resp.status_code in (200, 201):
                return str(resp.json().get("html_url", ""))
            raise RuntimeError(f"Failed to create issue: {resp.status_code}")

    async def get_closed_issues(self, limit: int = 50) -> list[dict[str, str]]:
        """Get recently closed issues."""
        async with self._client() as client:
            resp = await client.get(
                f"/repos/{self.repo}/issues",
                params={"state": "closed", "type": "issues", "limit": str(limit)},
            )
            if resp.status_code != 200:
                return []
            return [
                {
                    "number": str(i["number"]),
                    "title": i["title"],
                    "body": i.get("body", ""),
                    "html_url": i.get("html_url", ""),
                }
                for i in resp.json()
            ]
