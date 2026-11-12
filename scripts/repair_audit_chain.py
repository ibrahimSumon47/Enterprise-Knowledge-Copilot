#!/usr/bin/env python3
"""Recompute the audit hash chain over the rows already stored.

Why this exists: entries written before 2026-11-12 hashed a `created_at` string
that was never persisted (the column defaulted to now() with microseconds), so no
stored row could ever reproduce its own hash. The verifier was right to call the
chain broken; the rows themselves were not edited.

This script re-hashes content that is already there, in id order, and writes back
only `prev_hash` and `entry_hash`. It saves the previous hashes to a local backup
file before touching anything. It does not delete rows.

Usage:
  SUPABASE_URL=... SUPABASE_SERVICE_ROLE_KEY=... python scripts/repair_audit_chain.py --dry-run
  SUPABASE_URL=... SUPABASE_SERVICE_ROLE_KEY=... python scripts/repair_audit_chain.py --apply
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

GENESIS = "genesis"
COLUMNS = (
    "id,prev_hash,entry_hash,actor_id,actor_role,action,resource_type,"
    "resource_id,outcome,ip_hash,detail,created_at"
)


def canonical(payload: dict) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def compute(prev_hash: str, payload: dict) -> str:
    return hashlib.sha256(f"{prev_hash}|{canonical(payload)}".encode("utf-8")).hexdigest()


def request(url: str, method: str, key: str, payload: object | None = None) -> list[dict]:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal",
    }
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    with urllib.request.urlopen(req, timeout=120) as response:
        body = response.read().decode("utf-8")
    return json.loads(body) if body.strip() else []


def fetch_all(base: str, key: str) -> list[dict]:
    rows: list[dict] = []
    offset = 0
    while True:
        query = urllib.parse.urlencode(
            {
                "select": COLUMNS,
                "order": "id.asc",
                "limit": "1000",
                "offset": str(offset),
            }
        )
        batch = request(f"{base}/rest/v1/audit_log?{query}", "GET", key)
        rows.extend(batch)
        if len(batch) < 1000:
            return rows
        offset += 1000


def payload_of(row: dict) -> dict:
    created = row["created_at"]
    if isinstance(created, str):
        created = datetime.fromisoformat(created.replace("Z", "+00:00")).isoformat(timespec="seconds")
    detail = row.get("detail") or {}
    if isinstance(detail, str):
        detail = json.loads(detail)
    return {
        "action": row["action"],
        "resource_type": row["resource_type"],
        "resource_id": row.get("resource_id"),
        "actor_id": str(row["actor_id"]) if row.get("actor_id") else None,
        "actor_role": row.get("actor_role"),
        "outcome": row["outcome"],
        "ip_hash": row.get("ip_hash"),
        "detail": detail,
        "created_at": created,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="write the recomputed hashes")
    parser.add_argument("--dry-run", action="store_true", help="only report what would change")
    args = parser.parse_args()

    base = os.environ.get("SUPABASE_URL", "").rstrip("/")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not base or not key:
        print("missing SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY", file=sys.stderr)
        return 2

    rows = fetch_all(base, key)
    print(f"rows: {len(rows)} ({rows[0]['id']}..{rows[-1]['id']})" if rows else "no rows")

    backup = Path(".tmp") / f"audit_chain_backup_{datetime.now().strftime('%Y%m%dT%H%M%S')}.json"
    backup.parent.mkdir(parents=True, exist_ok=True)
    backup.write_text(
        json.dumps(
            [{"id": r["id"], "prev_hash": r["prev_hash"], "entry_hash": r["entry_hash"]} for r in rows],
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"backup: {backup}")

    prev = GENESIS
    updated = 0
    for row in rows:
        entry = compute(prev, payload_of(row))
        if row["prev_hash"] != prev or row["entry_hash"] != entry:
            if args.apply:
                request(
                    f"{base}/rest/v1/audit_log?id=eq.{row['id']}",
                    "PATCH",
                    key,
                    {"prev_hash": prev, "entry_hash": entry},
                )
            updated += 1
        prev = entry
    print(f"{'rewrote' if args.apply else 'would rewrite'} {updated} of {len(rows)} rows")
    print("head:", prev)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
