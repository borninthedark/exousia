"""Tests for sync_docs_to_paperless.py — Markdown-to-PDF + Paperless upload."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import pytest
from sync_docs_to_paperless import (
    escape_xml,
    get_existing_titles,
    get_or_create_tag,
    main,
    md_to_pdf,
    upload_pdf,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_response(data: dict | list, status_code: int = 200) -> httpx.Response:
    """Build a fake httpx.Response."""
    return httpx.Response(
        status_code=status_code,
        json=data,
        request=httpx.Request("GET", "http://test"),
    )


# ---------------------------------------------------------------------------
# escape_xml
# ---------------------------------------------------------------------------


class TestEscapeXml:
    def test_ampersand(self) -> None:
        assert escape_xml("foo & bar") == "foo &amp; bar"

    def test_lt_gt(self) -> None:
        assert escape_xml("<div>") == "&lt;div&gt;"

    def test_combined(self) -> None:
        assert escape_xml("a & <b>") == "a &amp; &lt;b&gt;"

    def test_no_special_chars(self) -> None:
        assert escape_xml("hello world") == "hello world"

    def test_empty_string(self) -> None:
        assert escape_xml("") == ""

    def test_multiple_ampersands(self) -> None:
        assert escape_xml("a&b&c") == "a&amp;b&amp;c"


# ---------------------------------------------------------------------------
# md_to_pdf
# ---------------------------------------------------------------------------


class TestMdToPdf:
    def test_creates_pdf(self, tmp_path: Path) -> None:
        md_file = tmp_path / "test-doc.md"
        md_file.write_text("# Hello\n\nSome body text.\n")
        pdf_file = tmp_path / "test-doc.pdf"

        md_to_pdf(md_file, pdf_file)

        assert pdf_file.exists()
        assert pdf_file.stat().st_size > 0
        # PDF starts with %PDF
        assert pdf_file.read_bytes()[:5] == b"%PDF-"

    def test_handles_headings(self, tmp_path: Path) -> None:
        md_file = tmp_path / "headings.md"
        md_file.write_text("# H1\n## H2\n### H3\nBody\n")
        pdf_file = tmp_path / "headings.pdf"

        md_to_pdf(md_file, pdf_file)

        assert pdf_file.exists()
        assert pdf_file.stat().st_size > 0

    def test_handles_empty_lines(self, tmp_path: Path) -> None:
        md_file = tmp_path / "blanks.md"
        md_file.write_text("Line one\n\n\nLine two\n")
        pdf_file = tmp_path / "blanks.pdf"

        md_to_pdf(md_file, pdf_file)

        assert pdf_file.exists()

    def test_handles_special_chars(self, tmp_path: Path) -> None:
        md_file = tmp_path / "special.md"
        md_file.write_text("Use <code> & 'quotes'\n")
        pdf_file = tmp_path / "special.pdf"

        md_to_pdf(md_file, pdf_file)

        assert pdf_file.exists()

    def test_title_from_filename(self, tmp_path: Path) -> None:
        md_file = tmp_path / "my-great-doc.md"
        md_file.write_text("Content\n")
        pdf_file = tmp_path / "my-great-doc.pdf"

        md_to_pdf(md_file, pdf_file)

        assert pdf_file.exists()

    def test_empty_file(self, tmp_path: Path) -> None:
        md_file = tmp_path / "empty.md"
        md_file.write_text("")
        pdf_file = tmp_path / "empty.pdf"

        md_to_pdf(md_file, pdf_file)

        assert pdf_file.exists()


# ---------------------------------------------------------------------------
# get_existing_titles
# ---------------------------------------------------------------------------


class TestGetExistingTitles:
    def test_returns_titles(self) -> None:
        mock_client = MagicMock(spec=httpx.Client)
        mock_client.get.return_value = _make_response(
            {"results": [{"title": "doc-a"}, {"title": "doc-b"}]}
        )

        titles = get_existing_titles(mock_client)

        assert titles == {"doc-a", "doc-b"}
        mock_client.get.assert_called_once()

    def test_empty_results(self) -> None:
        mock_client = MagicMock(spec=httpx.Client)
        mock_client.get.return_value = _make_response({"results": []})

        titles = get_existing_titles(mock_client)

        assert titles == set()

    def test_raises_on_http_error(self) -> None:
        mock_client = MagicMock(spec=httpx.Client)
        mock_client.get.return_value = _make_response({}, status_code=500)

        with pytest.raises(httpx.HTTPStatusError):
            get_existing_titles(mock_client)


# ---------------------------------------------------------------------------
# get_or_create_tag
# ---------------------------------------------------------------------------


class TestGetOrCreateTag:
    def test_returns_existing_tag(self) -> None:
        mock_client = MagicMock(spec=httpx.Client)
        mock_client.get.return_value = _make_response({"results": [{"id": 42, "name": "exousia"}]})

        tag_id = get_or_create_tag(mock_client, "exousia")

        assert tag_id == 42
        mock_client.post.assert_not_called()

    def test_creates_new_tag(self) -> None:
        mock_client = MagicMock(spec=httpx.Client)
        mock_client.get.return_value = _make_response({"results": []})
        mock_client.post.return_value = _make_response({"id": 99, "name": "exousia"})

        tag_id = get_or_create_tag(mock_client, "exousia")

        assert tag_id == 99
        mock_client.post.assert_called_once()

    def test_raises_on_get_error(self) -> None:
        mock_client = MagicMock(spec=httpx.Client)
        mock_client.get.return_value = _make_response({}, status_code=403)

        with pytest.raises(httpx.HTTPStatusError):
            get_or_create_tag(mock_client, "exousia")

    def test_raises_on_create_error(self) -> None:
        mock_client = MagicMock(spec=httpx.Client)
        mock_client.get.return_value = _make_response({"results": []})
        mock_client.post.return_value = _make_response({}, status_code=500)

        with pytest.raises(httpx.HTTPStatusError):
            get_or_create_tag(mock_client, "exousia")


# ---------------------------------------------------------------------------
# upload_pdf
# ---------------------------------------------------------------------------


class TestUploadPdf:
    def test_uploads_successfully(self, tmp_path: Path) -> None:
        pdf_file = tmp_path / "doc.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 fake content")

        mock_client = MagicMock(spec=httpx.Client)
        mock_client.post.return_value = _make_response({"task_id": "abc123"})

        upload_pdf(mock_client, pdf_file, "test-doc", tag_id=5)

        mock_client.post.assert_called_once()
        call_kwargs = mock_client.post.call_args
        assert "post_document" in call_kwargs.args[0]

    def test_raises_on_error(self, tmp_path: Path) -> None:
        pdf_file = tmp_path / "doc.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 fake content")

        mock_client = MagicMock(spec=httpx.Client)
        mock_client.post.return_value = _make_response({}, status_code=400)

        with pytest.raises(httpx.HTTPStatusError):
            upload_pdf(mock_client, pdf_file, "test-doc", tag_id=5)


# ---------------------------------------------------------------------------
# main (integration-style with mocks)
# ---------------------------------------------------------------------------


class TestMain:
    @patch("sync_docs_to_paperless.PAPERLESS_TOKEN", "")
    def test_exits_without_token(self) -> None:
        with pytest.raises(SystemExit):
            main()

    @patch("sync_docs_to_paperless.PAPERLESS_TOKEN", "fake-token")
    @patch("sync_docs_to_paperless.DOCS_DIR")
    def test_no_md_files(self, mock_docs_dir: MagicMock, capsys: pytest.CaptureFixture) -> None:
        mock_docs_dir.rglob.return_value = []

        main()

        captured = capsys.readouterr()
        assert "No markdown files" in captured.out

    @patch("sync_docs_to_paperless.PAPERLESS_TOKEN", "fake-token")
    @patch("sync_docs_to_paperless.httpx.Client")
    @patch("sync_docs_to_paperless.OUTPUT_DIR")
    @patch("sync_docs_to_paperless.DOCS_DIR")
    def test_skips_existing(
        self,
        mock_docs_dir: MagicMock,
        mock_output_dir: MagicMock,
        mock_client_cls: MagicMock,
        tmp_path: Path,
        capsys: pytest.CaptureFixture,
    ) -> None:
        # Set up a single md file
        md_file = tmp_path / "existing.md"
        md_file.write_text("# Existing Doc\n")
        mock_docs_dir.rglob.return_value = [md_file]
        mock_output_dir.__truediv__ = lambda self, x: tmp_path / x
        mock_output_dir.mkdir = MagicMock()

        # Mock relative_to to return the filename
        with patch.object(type(md_file), "relative_to", return_value=Path("existing.md")):
            # Mock httpx client
            mock_client = MagicMock()
            mock_client_cls.return_value.__enter__ = MagicMock(return_value=mock_client)
            mock_client_cls.return_value.__exit__ = MagicMock(return_value=False)

            # existing title matches
            mock_client.get.side_effect = [
                _make_response({"results": [{"title": "exousia/existing"}]}),
                _make_response({"results": [{"id": 1, "name": "exousia"}]}),
            ]

            main()

        captured = capsys.readouterr()
        assert "skipped" in captured.out

    @patch("sync_docs_to_paperless.PAPERLESS_TOKEN", "fake-token")
    @patch("sync_docs_to_paperless.md_to_pdf", side_effect=RuntimeError("render fail"))
    @patch("sync_docs_to_paperless.OUTPUT_DIR")
    @patch("sync_docs_to_paperless.DOCS_DIR")
    def test_conversion_failure(
        self,
        mock_docs_dir: MagicMock,
        mock_output_dir: MagicMock,
        mock_md_to_pdf: MagicMock,
        tmp_path: Path,
        capsys: pytest.CaptureFixture,
    ) -> None:
        md_file = tmp_path / "broken.md"
        md_file.write_text("bad content")
        mock_docs_dir.rglob.return_value = [md_file]
        mock_output_dir.__truediv__ = lambda self, x: tmp_path / x
        mock_output_dir.mkdir = MagicMock()

        with patch.object(type(md_file), "relative_to", return_value=Path("broken.md")):
            # No files converted, so no upload attempted — need an empty client context
            with patch("sync_docs_to_paperless.httpx.Client") as mock_cls:
                mock_client = MagicMock()
                mock_cls.return_value.__enter__ = MagicMock(return_value=mock_client)
                mock_cls.return_value.__exit__ = MagicMock(return_value=False)
                mock_client.get.side_effect = [
                    _make_response({"results": []}),
                    _make_response({"results": [{"id": 1, "name": "exousia"}]}),
                ]
                main()

        captured = capsys.readouterr()
        assert "FAILED" in captured.err

    @patch("sync_docs_to_paperless.PAPERLESS_TOKEN", "fake-token")
    @patch("sync_docs_to_paperless.httpx.Client")
    @patch("sync_docs_to_paperless.OUTPUT_DIR")
    @patch("sync_docs_to_paperless.DOCS_DIR")
    def test_upload_failure(
        self,
        mock_docs_dir: MagicMock,
        mock_output_dir: MagicMock,
        mock_client_cls: MagicMock,
        tmp_path: Path,
        capsys: pytest.CaptureFixture,
    ) -> None:
        md_file = tmp_path / "newdoc.md"
        md_file.write_text("# New\nContent\n")
        mock_docs_dir.rglob.return_value = [md_file]
        mock_output_dir.__truediv__ = lambda self, x: tmp_path / x
        mock_output_dir.mkdir = MagicMock()

        with patch.object(type(md_file), "relative_to", return_value=Path("newdoc.md")):
            mock_client = MagicMock()
            mock_client_cls.return_value.__enter__ = MagicMock(return_value=mock_client)
            mock_client_cls.return_value.__exit__ = MagicMock(return_value=False)

            mock_client.get.side_effect = [
                _make_response({"results": []}),  # no existing titles
                _make_response({"results": [{"id": 1, "name": "exousia"}]}),  # tag
            ]
            # upload_pdf raises
            mock_client.post.return_value = _make_response({}, status_code=500)

            main()

        captured = capsys.readouterr()
        assert "UPLOAD FAILED" in captured.err
