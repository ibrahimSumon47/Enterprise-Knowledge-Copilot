"""Upload security: type sniffing, bombs, filenames and tenant scoping."""

from __future__ import annotations

import io
import zipfile
from typing import Any

import pytest
from docx import Document
from fastapi.testclient import TestClient

from app import auth as auth_module
from app import db, uploads
from app import main as api
from app.auth import AuthUser

ORG_A = "11111111-1111-1111-1111-111111111111"
ORG_B = "22222222-2222-2222-2222-222222222222"


def member(org: str = ORG_A, role: str = "owner") -> AuthUser:
    return AuthUser(
        id="33333333-3333-3333-3333-333333333333",
        email="owner@example.test",
        role=role,
        department=None,
        org_id=org,
        raw_token="token",
    )


def client_for(user: AuthUser) -> TestClient:
    api.app.dependency_overrides[auth_module.current_user] = lambda: user
    return TestClient(api.app)


@pytest.fixture(autouse=True)
def clear_overrides() -> Any:
    yield
    api.app.dependency_overrides.clear()


def docx_bytes() -> bytes:
    document = Document()
    document.add_paragraph("Expense policy. Receipts are required above 25 USD within 45 days.")
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def test_text_and_markdown_are_accepted() -> None:
    parsed = uploads.extract("policy.md", b"# Policy\n\nReceipts are due within 45 days.")
    assert parsed.kind == "text"
    assert "Receipts" in parsed.text


def test_pdf_and_docx_must_match_their_extension() -> None:
    with pytest.raises(uploads.UploadError):
        uploads.extract("policy.pdf", b"just text pretending to be a pdf")
    with pytest.raises(uploads.UploadError):
        uploads.extract("policy.docx", b"PK\x03\x04not really a zip")


def test_unknown_extensions_are_rejected() -> None:
    for name in ("payload.exe", "notes.rtf", "archive.zip", "no-extension"):
        with pytest.raises(uploads.UploadError):
            uploads.extract(name, b"harmless text that is long enough to parse")


def test_path_traversal_is_reduced_to_a_safe_basename() -> None:
    name = uploads.safe_filename("../../etc/passwd")
    assert "/" not in name and "\\" not in name
    assert name == "passwd"
    assert uploads.safe_filename("..") == "upload.txt"
    assert uploads.safe_filename("a" * 400 + ".txt").endswith(".txt")


def test_oversized_file_is_rejected_before_parsing() -> None:
    with pytest.raises(uploads.UploadError) as caught:
        uploads.extract("big.txt", b"a" * (uploads.MAX_BYTES + 1))
    assert caught.value.status_code == 413


def test_html_scripts_and_styles_are_not_extracted() -> None:
    parsed = uploads.extract(
        "page.html",
        b"<html><style>body{display:none}</style><script>alert('x')</script>"
        b"<p>Receipts are due within 45 days.</p></html>",
    )
    assert "Receipts are due" in parsed.text
    assert "alert" not in parsed.text
    assert "display:none" not in parsed.text


def test_docx_zip_bomb_is_rejected_without_decompressing() -> None:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("word/document.xml", "<w:document/>")
        archive.writestr("word/huge.bin", b"\0" * (uploads.MAX_UNCOMPRESSED + 1))
    with pytest.raises(uploads.UploadError) as caught:
        uploads.extract("bomb.docx", buffer.getvalue())
    assert "expands" in str(caught.value)


def test_a_real_docx_extracts_text() -> None:
    parsed = uploads.extract("policy.docx", docx_bytes())
    assert parsed.kind == "docx"
    assert "Receipts are required" in parsed.text


def test_upload_rejects_another_orgs_document(monkeypatch: pytest.MonkeyPatch) -> None:
    async def missing(document_id: str, org_id: str) -> None:
        assert org_id == ORG_A
        return None

    monkeypatch.setattr(db, "document_detail", missing)
    response = client_for(member()).get("/documents/foreign-document")
    assert response.status_code == 404


def test_upload_requires_storage_and_rate_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.main.storage.configured", lambda settings: True)

    async def blocked(*args: Any) -> bool:
        return False

    monkeypatch.setattr(db, "upload_rate_allowed", blocked)
    response = client_for(member()).post(
        "/documents/upload",
        files={"file": ("policy.txt", b"Receipts are due within 45 days.", "text/plain")},
    )
    assert response.status_code == 429


def test_wrong_type_renamed_is_rejected_by_the_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.main.storage.configured", lambda settings: True)

    async def allowed(*args: Any) -> bool:
        return True

    monkeypatch.setattr(db, "upload_rate_allowed", allowed)
    response = client_for(member()).post(
        "/documents/upload",
        files={"file": ("policy.pdf", b"plain text, not a pdf at all", "application/pdf")},
    )
    assert response.status_code == 400
    assert "does not match" in response.json()["detail"]


def test_oversized_upload_is_stopped_while_streaming(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.main.storage.configured", lambda settings: True)

    async def allowed(*args: Any) -> bool:
        return True

    monkeypatch.setattr(db, "upload_rate_allowed", allowed)
    response = client_for(member()).post(
        "/documents/upload",
        files={"file": ("big.txt", b"a" * (uploads.MAX_BYTES + 1), "text/plain")},
    )
    assert response.status_code == 413


def test_reindex_of_a_foreign_document_is_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    async def missing(document_id: str, org_id: str) -> None:
        return None

    monkeypatch.setattr(db, "document_detail", missing)
    response = client_for(member()).post("/documents/foreign/reindex")
    assert response.status_code == 404
