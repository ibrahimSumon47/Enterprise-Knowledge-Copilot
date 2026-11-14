"""Upload validation and text extraction.

The file extension and the bytes both have to agree on the type. The browser's
Content-Type header is ignored: it is attacker-controlled. Every parser is
bounded before it decompresses or extracts anything, so a renamed archive or a
zip bomb becomes a failed document rather than a stalled process.
"""

from __future__ import annotations

import io
import re
import zipfile
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import PurePosixPath

MAX_BYTES = 10 * 1024 * 1024
MAX_ORG_BYTES = 200 * 1024 * 1024
MAX_UNCOMPRESSED = 50 * 1024 * 1024
MAX_ZIP_ENTRIES = 400
MAX_PAGES = 300
MAX_EXTRACTED_CHARS = 2_000_000
PARSE_TIMEOUT_SECONDS = 25

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".md", ".markdown", ".html", ".htm", ".txt"}

TEXT_EXTENSIONS = {".md", ".markdown", ".txt"}
HTML_EXTENSIONS = {".html", ".htm"}


class UploadError(Exception):
    """A rejection the API can show the user without a stack trace."""

    def __init__(self, reason: str, status_code: int = 400) -> None:
        super().__init__(reason)
        self.reason = reason
        self.status_code = status_code


@dataclass(frozen=True)
class ExtractedDocument:
    kind: str
    text: str
    safe_name: str


def safe_filename(name: str | None, fallback: str = "upload.txt") -> str:
    """Basename only: no traversal, no control characters, bounded length."""
    raw = PurePosixPath((name or "").replace("\\", "/")).name
    cleaned = re.sub(r"[^A-Za-z0-9._ -]+", "-", raw).strip(" .-")
    cleaned = cleaned.replace("..", ".")
    if not cleaned or cleaned.startswith("."):
        cleaned = fallback
    stem, dot, suffix = cleaned.rpartition(".")
    if not dot:
        return cleaned[:120]
    return f"{stem[:100]}.{suffix.lower()[:10]}"


def _text(data: bytes) -> str:
    if b"\x00" in data:
        raise UploadError("the file contains binary data")
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise UploadError("the file is not valid UTF-8 text") from exc


class _TextExtractor(HTMLParser):
    """Text only: scripts, styles and embedded objects never reach the corpus."""

    BLOCKED = {"script", "style", "noscript", "iframe", "object", "embed", "svg", "template"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.blocked = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in self.BLOCKED:
            self.blocked += 1
        elif tag in {"p", "br", "li", "h1", "h2", "h3", "h4", "tr", "div"}:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in self.BLOCKED and self.blocked:
            self.blocked -= 1

    def handle_data(self, data: str) -> None:
        if not self.blocked:
            self.parts.append(data)


def _html_text(raw: str) -> str:
    parser = _TextExtractor()
    try:
        parser.feed(raw)
        parser.close()
    except Exception as exc:  # noqa: BLE001 - malformed HTML becomes a rejection
        raise UploadError("the HTML could not be read") from exc
    return "".join(parser.parts)


def _check_docx_archive(data: bytes) -> None:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            infos = archive.infolist()
            if len(infos) > MAX_ZIP_ENTRIES:
                raise UploadError("the DOCX has too many archive entries")
            if sum(info.file_size for info in infos) > MAX_UNCOMPRESSED:
                raise UploadError("the DOCX expands beyond the parsing limit")
            if any(info.flag_bits & 0x1 for info in infos):
                raise UploadError("encrypted DOCX files are not supported")
            names = {info.filename for info in infos}
            if "word/document.xml" not in names or "[Content_Types].xml" not in names:
                raise UploadError("the file is a ZIP, not a DOCX")
            for info in infos[:MAX_ZIP_ENTRIES]:
                if info.file_size > 10 * 1024 * 1024:
                    raise UploadError("a DOCX entry is too large")
    except zipfile.BadZipFile as exc:
        raise UploadError("the DOCX archive is corrupt") from exc


def _pdf_text(data: bytes) -> str:
    from pypdf import PdfReader

    try:
        reader = PdfReader(io.BytesIO(data), strict=False)
        if len(reader.pages) > MAX_PAGES:
            raise UploadError("the PDF has too many pages")
        parts = []
        for page in reader.pages:
            parts.append(page.extract_text() or "")
            if sum(len(part) for part in parts) > MAX_EXTRACTED_CHARS:
                raise UploadError("the PDF contains too much text")
        return "\n".join(parts)
    except UploadError:
        raise
    except Exception as exc:  # noqa: BLE001 - any parser failure is a failed document
        raise UploadError("the PDF could not be read") from exc


def _docx_text(data: bytes) -> str:
    from docx import Document

    _check_docx_archive(data)
    try:
        document = Document(io.BytesIO(data))
        blocks = [paragraph.text for paragraph in document.paragraphs]
        for table in document.tables:
            for row in table.rows:
                blocks.append(" | ".join(cell.text for cell in row.cells))
        return "\n".join(blocks)
    except Exception as exc:  # noqa: BLE001
        raise UploadError("the DOCX could not be read") from exc


def extract(name: str | None, data: bytes) -> ExtractedDocument:
    """Validate extension + magic, then extract plain text within fixed limits."""
    if not data:
        raise UploadError("the file is empty")
    if len(data) > MAX_BYTES:
        raise UploadError("the file is larger than 10 MB", status_code=413)
    safe = safe_filename(name)
    suffix = PurePosixPath(safe).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise UploadError("only PDF, DOCX, Markdown, HTML and TXT are accepted")

    if data.startswith(b"%PDF-"):
        kind = "pdf"
    elif data.startswith(b"PK\x03\x04"):
        kind = "docx"
    else:
        text = _text(data)
        stripped = text.lstrip().lower()
        if suffix in HTML_EXTENSIONS:
            if not stripped.startswith(("<!doctype html", "<html", "<")):
                raise UploadError("the file extension says HTML but the content does not")
            kind = "html"
        elif suffix == ".html":
            raise UploadError("the HTML content does not match its extension")
        else:
            if stripped.startswith(("%pdf", "pk\x03\x04")):
                raise UploadError("the file content does not match its extension")
            kind = "text"

    expected = {
        ".pdf": "pdf",
        ".docx": "docx",
        ".html": "html",
        ".htm": "html",
    }.get(suffix, "text")
    if kind != expected:
        raise UploadError("the file content does not match its extension")

    if kind == "pdf":
        extracted = _pdf_text(data)
    elif kind == "docx":
        extracted = _docx_text(data)
    else:
        raw = _text(data)
        extracted = _html_text(raw) if kind == "html" else raw

    cleaned = re.sub(r"[ \t]+\n", "\n", extracted)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    if len(cleaned) < 20:
        raise UploadError("no readable text was found in the file")
    if len(cleaned) > MAX_EXTRACTED_CHARS:
        raise UploadError("the extracted text is too large")
    return ExtractedDocument(kind=kind, text=cleaned, safe_name=safe)
