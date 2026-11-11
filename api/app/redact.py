"""Redaction helpers. Logs must never contain raw emails, tokens or long ids."""

from __future__ import annotations

import hashlib
import os
import re

EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
BEARER = re.compile(r"(?i)bearer\s+[a-z0-9._\-]+")
LONG_NUMBER = re.compile(r"\b\d{9,}\b")
UUID = re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.I)

_SALT = os.environ.get("LOG_HASH_SALT", "local-dev-salt")


def redact(text: str) -> str:
    """Replace obvious personal data with stable placeholders."""
    cleaned = EMAIL.sub("[email]", text)
    cleaned = BEARER.sub("Bearer [token]", cleaned)
    cleaned = UUID.sub("[id]", cleaned)
    return LONG_NUMBER.sub("[number]", cleaned)


def hash_identifier(value: str) -> str:
    """Hash an IP or user id so audit rows stay linkable but not identifying."""
    return hashlib.sha256(f"{_SALT}:{value}".encode("utf-8")).hexdigest()[:32]
