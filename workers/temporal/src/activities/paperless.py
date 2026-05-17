"""Paperless-ngx activities — document upload and tag management."""

import hashlib
from dataclasses import dataclass, field
from pathlib import Path

import httpx
from temporalio import activity

from src.clients.forgejo import ForgejoClient


@dataclass
class DocSyncConfig:
    api_url: str = "http://paperless:8000/api"
    token: str = ""
    host: str = "paperless.exousia.local"
    watch_dir: str = "/workspace/docs"
    tag_map: dict[str, int] = field(default_factory=dict)


@dataclass
class UploadResult:
    filename: str
    task_id: str
    tag: str


class PaperlessActivities:
    """Activities for syncing documents to Paperless-ngx."""

    def __init__(self, config: DocSyncConfig):
        self.config = config
        self.forgejo = ForgejoClient()

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Token {self.config.token}",
            "Host": self.config.host,
        }

    @activity.defn
    async def scan_docs_dir(self) -> list[str]:
        """Return list of doc files in watch directory."""
        watch = Path(self.config.watch_dir)
        if not watch.exists():
            return []
        extensions = {".md", ".pdf", ".txt", ".rst", ".html"}
        return [str(p) for p in sorted(watch.rglob("*")) if p.is_file() and p.suffix in extensions]

    @activity.defn
    async def get_file_hash(self, filepath: str) -> str:
        """SHA256 hash of a file for change detection."""
        h = hashlib.sha256()
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()

    @activity.defn
    async def check_already_uploaded(self, title: str) -> bool:
        """Check if a document with this title already exists in Paperless."""
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.config.api_url}/documents/",
                headers=self._headers(),
                params={"query": f"title:{title}"},
            )
            resp.raise_for_status()
            result: bool = resp.json()["count"] > 0
        return result

    @activity.defn
    async def upload_document(self, filepath: str, tag_name: str) -> UploadResult:
        """Upload a document to Paperless-ngx."""
        path = Path(filepath)
        title = path.stem
        tag_id = self.config.tag_map.get(tag_name)

        activity.logger.info(f"Uploading {path.name} with tag={tag_name}")

        async with httpx.AsyncClient(timeout=60.0) as client:
            files = {"document": (path.name, open(filepath, "rb"))}
            data = {"title": title}
            if tag_id:
                data["tags"] = str(tag_id)

            resp = await client.post(
                f"{self.config.api_url}/documents/post_document/",
                headers=self._headers(),
                files=files,
                data=data,
            )
            resp.raise_for_status()

        return UploadResult(
            filename=path.name,
            task_id=resp.text.strip('"'),
            tag=tag_name,
        )

    @activity.defn
    async def list_tags(self) -> dict[str, int]:
        """Fetch all tags from Paperless."""
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.config.api_url}/tags/",
                headers=self._headers(),
            )
            resp.raise_for_status()
            return {t["name"]: t["id"] for t in resp.json()["results"]}

    @activity.defn
    async def get_documents_by_tag(self, tag_name: str) -> list[dict[str, str]]:
        """Get documents with a specific tag (e.g., 'actionable')."""
        async with httpx.AsyncClient() as client:
            # First get the tag ID
            tags = await self.list_tags()
            tag_id = tags.get(tag_name)
            if not tag_id:
                return []

            resp = await client.get(
                f"{self.config.api_url}/documents/",
                headers=self._headers(),
                params={"tags__id": tag_id},
            )
            resp.raise_for_status()
            docs = []
            for doc in resp.json().get("results", []):
                docs.append(
                    {
                        "id": str(doc["id"]),
                        "title": doc["title"],
                        "created": doc.get("created", ""),
                        "url": f"https://{self.config.host}/documents/{doc['id']}/details",
                    }
                )
            return docs

    @activity.defn
    async def update_document_tags(
        self, doc_id: str, add_tags: list[str], remove_tags: list[str]
    ) -> bool:
        """Add or remove tags from a document."""
        async with httpx.AsyncClient() as client:
            tags = await self.list_tags()

            # Get current document
            resp = await client.get(
                f"{self.config.api_url}/documents/{doc_id}/",
                headers=self._headers(),
            )
            resp.raise_for_status()
            current_tags = set(resp.json().get("tags", []))

            # Modify tags
            for tag_name in add_tags:
                if tag_name in tags:
                    current_tags.add(tags[tag_name])
            for tag_name in remove_tags:
                if tag_name in tags:
                    current_tags.discard(tags[tag_name])

            # Update
            resp = await client.patch(
                f"{self.config.api_url}/documents/{doc_id}/",
                headers=self._headers(),
                json={"tags": list(current_tags)},
            )
            return bool(resp.status_code == 200)

    @activity.defn
    async def create_forgejo_issue_from_doc(self, doc: dict[str, str]) -> str:
        """Create a Forgejo issue linked to a Paperless document."""
        title = f"Action required: {doc['title']}"
        body = (
            f"## Document Action Item\n\n"
            f"**Document:** [{doc['title']}]({doc['url']})\n"
            f"**Created:** {doc.get('created', 'unknown')}\n"
            f"**Paperless ID:** {doc['id']}\n\n"
            f"---\n"
            f"This issue was auto-created from a Paperless document tagged `actionable`.\n"
            f"When resolved, the document will be re-tagged as `completed`.\n"
        )
        return await self.forgejo.create_issue(title, body)

    @activity.defn
    async def check_closed_issues_for_docs(self) -> list[dict[str, str]]:
        """Find closed Forgejo issues that reference Paperless doc IDs."""
        closed_issues = await self.forgejo.get_closed_issues()
        closed_docs = []
        for issue in closed_issues:
            body = issue.get("body", "")
            if "Paperless ID:" in body:
                for line in body.splitlines():
                    if "Paperless ID:" in line:
                        doc_id = line.split("Paperless ID:")[-1].strip()
                        closed_docs.append(
                            {
                                "doc_id": doc_id,
                                "issue_url": issue.get("html_url", ""),
                            }
                        )
        return closed_docs
