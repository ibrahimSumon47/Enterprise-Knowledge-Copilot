"""Two-organisation checks: the request never chooses the tenant.

Every test gives the caller a membership in org A, then tries to act on org B
through a guessed id, a forged header or a token claim. The expected result is
always the same: the server uses org A and the foreign row is not found.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
from fastapi import HTTPException, Request
from fastapi.testclient import TestClient

from app import auth as auth_module
from app import db
from app import main as api
from app.auth import AuthUser

ORG_A = "11111111-1111-1111-1111-111111111111"
ORG_B = "22222222-2222-2222-2222-222222222222"


def member(org: str = ORG_A, role: str = "admin") -> AuthUser:
    return AuthUser(
        id="33333333-3333-3333-3333-333333333333",
        email="member@example.test",
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


def test_membership_org_wins_over_a_forged_claim(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_profile(user_id: str) -> dict[str, Any]:
        assert user_id == member().id
        return {
            "id": user_id,
            "email": "member@example.test",
            "role": "employee",
            "department": None,
            "org_id": ORG_A,
            "org_role": "employee",
        }

    monkeypatch.setattr(db, "profile_for", fake_profile)
    monkeypatch.setattr(
        auth_module,
        "decode_token",
        lambda token, settings: {
            "sub": member().id,
            "email": "member@example.test",
            "org_id": ORG_B,
            "role": "admin",
        },
    )
    request = Request(
        {
            "type": "http",
            "headers": [(b"authorization", b"Bearer forged")],
        }
    )
    user = asyncio.run(auth_module.current_user(request))
    assert user.org_id == ORG_A
    assert user.role == "employee"


def test_a_user_without_membership_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_profile(user_id: str) -> dict[str, Any]:
        return {
            "id": user_id,
            "email": "lonely@example.test",
            "role": "employee",
            "department": None,
            "org_id": None,
            "org_role": None,
        }

    monkeypatch.setattr(db, "profile_for", fake_profile)
    monkeypatch.setattr(
        auth_module,
        "decode_token",
        lambda token, settings: {"sub": member().id, "email": "lonely@example.test"},
    )
    request = Request(
        {"type": "http", "headers": [(b"authorization", b"Bearer token")]}
    )
    with pytest.raises(HTTPException) as caught:
        asyncio.run(auth_module.current_user(request))
    assert caught.value.status_code == 403


def test_documents_use_membership_org_and_ignore_a_header(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    async def fake_documents(org_id: str, role: str, department: str | None) -> list[Any]:
        captured.update(org_id=org_id, role=role, department=department)
        return []

    monkeypatch.setattr(db, "list_documents", fake_documents)
    response = client_for(member()).get(
        "/documents", headers={"X-Org-Id": ORG_B, "X-Organisation": ORG_B}
    )
    assert response.status_code == 200
    assert captured["org_id"] == ORG_A


def test_audit_and_unanswered_are_scoped_to_the_member_org(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    async def fake_audit(org_id: str, limit: int = 100) -> list[Any]:
        captured["audit"] = org_id
        return []

    async def fake_queue(org_id: str, limit: int = 50) -> list[Any]:
        captured["queue"] = org_id
        return []

    monkeypatch.setattr(db, "audit_page", fake_audit)
    monkeypatch.setattr(db, "list_unanswered", fake_queue)
    client = client_for(member())
    assert client.get("/audit?limit=5", headers={"X-Org-Id": ORG_B}).status_code == 200
    assert client.get("/admin/unanswered", headers={"X-Org-Id": ORG_B}).status_code == 200
    assert captured == {"audit": ORG_A, "queue": ORG_A}


def test_a_guessed_conversation_id_from_another_org_is_not_found(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    async def fake_messages(conversation_id: str, org_id: str, user_id: str) -> list[Any]:
        captured.update(conversation_id=conversation_id, org_id=org_id)
        return []

    monkeypatch.setattr(db, "list_messages", fake_messages)
    response = client_for(member()).get(
        "/conversations/foreign-conversation/messages", headers={"X-Org-Id": ORG_B}
    )
    assert response.status_code == 404
    assert captured == {"conversation_id": "foreign-conversation", "org_id": ORG_A}


def test_feedback_on_a_foreign_message_is_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    async def fake_feedback(
        message_id: str, org_id: str, user_id: str, rating: int, reason: str | None
    ) -> bool:
        captured.update(message_id=message_id, org_id=org_id, user_id=user_id)
        return False

    monkeypatch.setattr(db, "record_feedback", fake_feedback)
    response = client_for(member()).post(
        "/feedback",
        json={"message_id": "44444444-4444-4444-4444-444444444444", "rating": -1},
        headers={"X-Org-Id": ORG_B},
    )
    assert response.status_code == 404
    assert captured["org_id"] == ORG_A


def test_search_passes_the_member_org_to_the_sql_function(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    async def fake_search(**kwargs: Any) -> list[Any]:
        captured.update(kwargs)
        return []

    monkeypatch.setattr(db, "search_chunks", fake_search)
    monkeypatch.setattr(
        "app.retrieval.embed_query", lambda text, settings: [0.1] * 384
    )
    from app.retrieval import retrieve

    asyncio.run(
        retrieve("policy?", ORG_A, "employee", None, api.get_settings())
    )
    assert captured["org_id"] == ORG_A
