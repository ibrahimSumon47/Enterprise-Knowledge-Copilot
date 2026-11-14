"""Admin export and workspace settings guards."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app import auth as auth_module
from app import db
from app import main as api
from app.auth import AuthUser
from app.schemas import WorkspaceSettingsRequest

ORG = "11111111-1111-1111-1111-111111111111"


def owner() -> AuthUser:
    return AuthUser(
        id="33333333-3333-3333-3333-333333333333",
        email="owner@example.test",
        role="owner",
        department=None,
        org_id=ORG,
        group_id=None,
        raw_token="token",
    )


@pytest.fixture(autouse=True)
def clear_overrides() -> Any:
    yield
    api.app.dependency_overrides.clear()


def test_csv_cells_that_look_like_formulas_are_neutralised() -> None:
    for value in ("=SUM(A1)", "+1", "-2", "@cmd", "\t=1", "\r=1"):
        cell = api._csv_cell(value)
        assert cell.startswith("\"'")


def test_audit_export_neutralises_formula_cells(monkeypatch: pytest.MonkeyPatch) -> None:
    async def rows(org_id: str, limit: int = 10_000) -> list[dict[str, Any]]:
        return [
            {
                "id": 1,
                "created_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
                "actor_id": ORG,
                "actor_role": "owner",
                "action": "=HYPERLINK(\"http://evil\")",
                "resource_type": "document",
                "resource_id": "+1",
                "outcome": "ok",
                "ip_hash": "hash",
                "detail": {"note": "=cmd"},
            }
        ]

    monkeypatch.setattr(db, "audit_for_export", rows)
    api.app.dependency_overrides[auth_module.current_user] = owner
    response = TestClient(api.app).get("/audit/export")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "\"'=HYPERLINK" in response.text
    assert "\"'+1\"" in response.text


def test_allowed_domains_reject_urls_and_spaces() -> None:
    parsed = WorkspaceSettingsRequest(allowed_domains=["Example.com", "@example.com"])
    assert parsed.allowed_domains == ["example.com"]
    with pytest.raises(ValueError):
        WorkspaceSettingsRequest(allowed_domains=["not a domain"])
    with pytest.raises(ValueError):
        WorkspaceSettingsRequest(allowed_domains=["https://example.com"])


def test_accent_colour_must_be_a_hex_value() -> None:
    assert WorkspaceSettingsRequest(accent_color="#1a2b3c").accent_color == "#1a2b3c"
    with pytest.raises(ValueError):
        WorkspaceSettingsRequest(accent_color="red")
