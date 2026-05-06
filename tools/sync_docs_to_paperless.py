#!/usr/bin/env python3
"""Convert Markdown docs to PDF and upload to Paperless-ngx.

Uses ReportLab to render Markdown files as clean PDFs, then uploads via
the Paperless REST API.
Skips files already uploaded (matched by title) to avoid duplicates.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import httpx
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

PAPERLESS_URL = os.environ.get("PAPERLESS_URL", "http://localhost:8000")
PAPERLESS_TOKEN = os.environ.get("PAPERLESS_TOKEN", "")
DOCS_DIR = Path(__file__).resolve().parent.parent / "docs"
OUTPUT_DIR = Path(tempfile.gettempdir()) / "exousia-docs-pdf"
TAG_NAME = "exousia"


def md_to_pdf(md_path: Path, pdf_path: Path) -> None:
    """Convert a Markdown file to PDF using ReportLab."""
    text = md_path.read_text(encoding="utf-8")
    styles = getSampleStyleSheet()

    # Title style
    title_style = ParagraphStyle(
        "DocTitle",
        parent=styles["Title"],
        fontSize=16,
        leading=20,
        spaceAfter=12,
    )

    # Body style — monospace for code-heavy docs
    body_style = ParagraphStyle(
        "DocBody",
        parent=styles["Normal"],
        fontName="Courier",
        fontSize=9,
        leading=12,
        spaceAfter=4,
    )

    # Heading style
    heading_style = ParagraphStyle(
        "DocHeading",
        parent=styles["Heading2"],
        fontSize=12,
        leading=15,
        spaceBefore=10,
        spaceAfter=4,
    )

    doc = SimpleDocTemplate(
        str(pdf_path),
        pagesize=letter,
        rightMargin=0.75 * inch,
        leftMargin=0.75 * inch,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
    )

    story: list = []

    # Use filename as title
    title = md_path.stem.replace("-", " ").replace("_", " ").title()
    story.append(Paragraph(title, title_style))
    story.append(Spacer(1, 6))

    for line in text.splitlines():
        if not line.strip():
            story.append(Spacer(1, 6))
            continue

        # Headings
        if line.startswith("# "):
            story.append(Paragraph(escape_xml(line[2:]), title_style))
        elif line.startswith("## "):
            story.append(Paragraph(escape_xml(line[3:]), heading_style))
        elif line.startswith("### "):
            story.append(Paragraph(escape_xml(line[4:]), heading_style))
        else:
            story.append(Paragraph(escape_xml(line), body_style))

    doc.build(story)


def escape_xml(text: str) -> str:
    """Escape XML special characters for ReportLab Paragraph."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def get_existing_titles(client: httpx.Client) -> set[str]:
    """Fetch all document titles from Paperless to check for duplicates."""
    titles: set[str] = set()
    url = f"{PAPERLESS_URL}/api/documents/?page_size=1000"
    resp = client.get(url)
    resp.raise_for_status()
    for doc in resp.json().get("results", []):
        titles.add(doc["title"])
    return titles


def get_or_create_tag(client: httpx.Client, tag_name: str) -> int:
    """Get or create a Paperless tag, return its ID."""
    resp = client.get(f"{PAPERLESS_URL}/api/tags/?name__iexact={tag_name}")
    resp.raise_for_status()
    results = resp.json().get("results", [])
    if results:
        tag_id: int = results[0]["id"]
        return tag_id

    resp = client.post(
        f"{PAPERLESS_URL}/api/tags/",
        json={"name": tag_name},
    )
    resp.raise_for_status()
    new_id: int = resp.json()["id"]
    return new_id


def upload_pdf(client: httpx.Client, pdf_path: Path, title: str, tag_id: int) -> None:
    """Upload a PDF to Paperless-ngx."""
    with open(pdf_path, "rb") as f:
        resp = client.post(
            f"{PAPERLESS_URL}/api/documents/post_document/",
            data={"title": title, "tags": [tag_id]},
            files={"document": (pdf_path.name, f, "application/pdf")},
        )
    resp.raise_for_status()
    print(f"  uploaded: {title}")


def main() -> None:
    if not PAPERLESS_TOKEN:
        print("ERROR: PAPERLESS_TOKEN not set", file=sys.stderr)
        sys.exit(1)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Collect all markdown files (skip venv, node_modules, etc.)
    md_files = sorted(DOCS_DIR.rglob("*.md"))
    if not md_files:
        print("No markdown files found in docs/")
        return

    print(f"Found {len(md_files)} markdown files")

    # Convert all to PDF
    pdf_files: list[tuple[Path, str]] = []
    for md_file in md_files:
        rel = md_file.relative_to(DOCS_DIR)
        title = f"exousia/{rel.with_suffix('')}"
        pdf_name = str(rel).replace("/", "-").replace(".md", ".pdf")
        pdf_path = OUTPUT_DIR / pdf_name

        try:
            md_to_pdf(md_file, pdf_path)
            pdf_files.append((pdf_path, title))
            print(f"  converted: {rel}")
        except Exception as e:
            print(f"  FAILED: {rel} — {e}", file=sys.stderr)

    # Upload to Paperless
    headers = {"Authorization": f"Token {PAPERLESS_TOKEN}"}
    with httpx.Client(
        base_url=PAPERLESS_URL,
        headers=headers,
        timeout=30.0,
    ) as client:
        existing = get_existing_titles(client)
        tag_id = get_or_create_tag(client, TAG_NAME)

        uploaded = 0
        skipped = 0
        for pdf_path, title in pdf_files:
            if title in existing:
                print(f"  exists: {title}")
                skipped += 1
                continue
            try:
                upload_pdf(client, pdf_path, title, tag_id)
                uploaded += 1
            except Exception as e:
                print(f"  UPLOAD FAILED: {title} — {e}", file=sys.stderr)

    print(f"\nDone: {uploaded} uploaded, {skipped} skipped (already exist)")


if __name__ == "__main__":
    main()
