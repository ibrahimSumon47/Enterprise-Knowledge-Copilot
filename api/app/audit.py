"""Tamper-evident audit log. Each row hashes the previous row's hash."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from . import db

GENESIS = "genesis"


def _canonical(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def compute_hash(prev_hash: str, payload: dict[str, Any]) -> str:
    return hashlib.sha256(f"{prev_hash}|{_canonical(payload)}".encode("utf-8")).hexdigest()


async def record(
    *,
    action: str,
    resource_type: str,
    actor_id: str | None,
    actor_role: str | None,
    resource_id: str | None = None,
    outcome: str = "ok",
    ip_hash: str | None = None,
    detail: dict[str, Any] | None = None,
) -> str:
    """Append one entry, chained to the previous hash, and return its hash."""
    prev_hash = await db.last_audit_hash()
    payload = {
        "action": action,
        "resource_type": resource_type,
        "resource_id": resource_id,
        "actor_id": actor_id,
        "actor_role": actor_role,
        "outcome": outcome,
        "ip_hash": ip_hash,
        "detail": detail or {},
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    entry_hash = compute_hash(prev_hash, payload)
    await db.insert_audit({"prev_hash": prev_hash, "entry_hash": entry_hash, **payload})
    return entry_hash


def verify_chain(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Recompute hashes bottom-up. Rows are expected newest-first.

    The caller passes a window (the newest N rows), not the whole log. The first
    row of that window is an anchor: its `prev_hash` points at a row outside the
    window, so it is checked against its own payload rather than against
    `genesis`. Treating the window edge as a break reported the entire log as
    tampered once the log outgrew the page size.
    """
    ordered = sorted(rows, key=lambda row: row["id"])
    if not ordered:
        return {"entries": 0, "intact": True, "broken_ids": [], "head": GENESIS, "anchor_id": None}
    anchor = ordered[0]["prev_hash"]
    prev = anchor
    broken: list[int] = []
    for position, row in enumerate(ordered):
        payload = {
            "action": row["action"],
            "resource_type": row["resource_type"],
            "resource_id": row.get("resource_id"),
            "actor_id": str(row.get("actor_id")) if row.get("actor_id") else None,
            "actor_role": row.get("actor_role"),
            "outcome": row["outcome"],
            "ip_hash": row.get("ip_hash"),
            "detail": row.get("detail") or {},
            "created_at": row["created_at"].isoformat(timespec="seconds")
            if hasattr(row["created_at"], "isoformat")
            else str(row["created_at"]),
        }
        expected = compute_hash(row["prev_hash"], payload)
        linked = position == 0 or row["prev_hash"] == prev
        if not linked or expected != row["entry_hash"]:
            broken.append(int(row["id"]))
        prev = row["entry_hash"]
    return {
        "entries": len(ordered),
        "intact": not broken,
        "broken_ids": broken,
        "head": prev,
        "anchor_id": int(ordered[0]["id"]),
        "anchored_at_genesis": anchor == GENESIS,
    }
