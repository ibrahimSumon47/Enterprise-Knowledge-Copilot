"""Owner sits above admin; ownership cannot be granted by a request."""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.auth import AuthUser, require_admin, require_owner


def user(role: str) -> AuthUser:
    return AuthUser(
        id="33333333-3333-3333-3333-333333333333",
        email="member@example.test",
        role=role,
        department=None,
        org_id="11111111-1111-1111-1111-111111111111",
        raw_token="token",
    )


def test_owner_passes_both_gates() -> None:
    assert require_admin(user("owner")).role == "owner"
    assert require_owner(user("owner")).role == "owner"


def test_admin_is_not_an_owner() -> None:
    assert require_admin(user("admin")).role == "admin"
    with pytest.raises(HTTPException) as caught:
        require_owner(user("admin"))
    assert caught.value.status_code == 403


def test_members_are_neither_admin_nor_owner() -> None:
    for role in ("employee", "guest", "engineering"):
        with pytest.raises(HTTPException):
            require_admin(user(role))
        with pytest.raises(HTTPException):
            require_owner(user(role))
