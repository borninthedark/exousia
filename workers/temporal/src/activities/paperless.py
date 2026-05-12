"""Paperless-ngx activities — document upload and tag management."""

import hashlib
from dataclasses import dataclass, field
from pathlib import Path

import httpx
from temporalio import activity


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
