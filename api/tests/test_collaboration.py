"""Invite, role and deactivation rules for workspace administration."""

from __future__ import annotations

import hashlib
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app import audit, db
from app import auth as auth_module
from app import main as api
from app.auth import AuthUser

ORG = "11111111-1111-1111-1111-111111111111"


def user(role: str, user_id: str = "33333333-3333-3333-3333-333333333333") -> AuthUser:
    return AuthUser(
        id=user_id,
        email=f"{role}@example.test",
        role=role,
        department=None,
        org_id=ORG,
        group_id=None,
        raw_token="token",
    )


def client_for(actor: AuthUser) -> TestClient:
    api.app.dependency_overrides[auth_module.current_user] = lambda: actor
    return TestClient(api.app)


@pytest.fixture(autouse=True)
def no_audit(monkeypatch: pytest.MonkeyPatch) -> Any:
    async def skip(**kwargs: Any) -> str:
        return "hash"

    monkeypatch.setattr(audit, "record", skip)
    yield
    api.app.dependency_overrides.clear()


def test_only_an_owner_can_invite_an_admin(monkeypatch: pytest.MonkeyPatch) -> None:
    async def create(**kwargs: Any) -> dict[str, Any]:
        return {
            "id": "invite-1",
            "expires_at": __import__("datetime").datetime.now(
                __import__("datetime").timezone.utc
            ),
        }

    monkeypatch.setattr(db, "create_invite", create)
    denied = client_for(user("admin")).post("/admin/invites", json={"role": "admin"})
    assert denied.status_code == 403
    allowed = client_for(user("owner")).post("/admin/invites", json={"role": "admin"})
    assert allowed.status_code == 201


def test_invite_token_is_stored_only_as_a_hash(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    async def create(**kwargs: Any) -> dict[str, Any]:
        captured.update(kwargs)
        return {
            "id": "invite-1",
            "expires_at": __import__("datetime").datetime.now(
                __import__("datetime").timezone.utc
            ),
        }

    monkeypatch.setattr(db, "create_invite", create)
    response = client_for(user("owner")).post(
        "/admin/invites", json={"role": "employee", "max_uses": 1}
    )
    assert response.status_code == 201
    token = response.json()["token"]
    assert captured["token_hash"] == hashlib.sha256(token.encode()).hexdigest()
    assert token not in captured["token_hash"]


def test_admin_cannot_change_another_admin(monkeypatch: pytest.MonkeyPatch) -> None:
    async def target(org_id: str, member_id: str) -> str:
        return "admin"

    monkeypatch.setattr(db, "member_role", target)
    response = client_for(user("admin")).patch(
        "/admin/members/another-admin", json={"status": "deactivated"}
    )
    assert response.status_code == 403


def test_self_deactivation_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    async def target(org_id: str, member_id: str) -> str:
        return "employee"

    monkeypatch.setattr(db, "member_role", target)
    actor = user("admin")
    response = client_for(actor).patch(
        f"/admin/members/{actor.id}", json={"status": "deactivated"}
    )
    assert response.status_code == 400


def test_owner_membership_cannot_be_changed(monkeypatch: pytest.MonkeyPatch) -> None:
    async def target(org_id: str, member_id: str) -> str:
        return "owner"

    monkeypatch.setattr(db, "member_role", target)
    response = client_for(user("owner")).patch(
        "/admin/members/owner-id", json={"role": "employee"}
    )
    assert response.status_code == 403
