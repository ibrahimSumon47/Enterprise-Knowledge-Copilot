"""Supabase JWT verification through JWKS, plus the authoritative role lookup."""

from __future__ import annotations

import logging
from dataclasses import dataclass

import jwt
from fastapi import Depends, HTTPException, Request, status
from jwt import PyJWKClient

from . import db
from .config import Settings, get_settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AuthUser:
    """An authenticated caller with the role the database says they hold."""

    id: str
    email: str
    role: str
    department: str | None
    org_id: str
    raw_token: str


_jwks_client: PyJWKClient | None = None


def _client(settings: Settings) -> PyJWKClient:
    global _jwks_client
    if _jwks_client is None:
        _jwks_client = PyJWKClient(settings.jwks_url, cache_keys=True, lifespan=300)
    return _jwks_client


def decode_token(token: str, settings: Settings) -> dict:
    """Verify signature, issuer, audience and expiry. Raises HTTPException on failure."""
    try:
        signing_key = _client(settings).get_signing_key_from_jwt(token).key
        return jwt.decode(
            token,
            signing_key,
            algorithms=["RS256", "ES256"],
            audience=settings.supabase_jwt_aud,
            issuer=settings.issuer,
            options={"require": ["exp", "sub"]},
        )
    except jwt.PyJWTError as exc:  # pragma: no cover - exercised by tests with a fake client
        logger.info("jwt verification failed: %s", type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid or expired token",
        ) from exc


async def current_user(request: Request, settings: Settings = Depends(get_settings)) -> AuthUser:
    """FastAPI dependency: a verified user with their role from `profiles`."""
    header = request.headers.get("authorization", "")
    if not header.lower().startswith("bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="missing token")
    token = header.split(" ", 1)[1].strip()

    claims = decode_token(token, settings)
    user_id = str(claims.get("sub", ""))
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="token has no subject")

    profile = await db.profile_for(user_id)
    if profile is None or profile.get("org_id") is None:
        # The organisation never comes from the request: without a verified
        # membership row the caller has no workspace to read from.
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="no active workspace membership",
        )

    return AuthUser(
        id=user_id,
        email=str(profile["email"]),
        role=str(profile.get("org_role") or profile["role"]),
        department=profile["department"],
        org_id=str(profile["org_id"]),
        raw_token=token,
    )


def require_admin(user: AuthUser = Depends(current_user)) -> AuthUser:
    if user.role not in {"admin", "owner"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="admin role required")
    return user


def require_owner(user: AuthUser = Depends(current_user)) -> AuthUser:
    """Owner-only actions: delete workspace, transfer ownership, remove admins."""
    if user.role != "owner":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="owner role required")
    return user
