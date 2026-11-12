#!/usr/bin/env python3
"""Reset document access levels to the corpus baseline.

The seven role accounts are shared with reviewers, so the admin account is a
shared account too. Any access-level change it makes is reversed nightly: this
script reads `data/access_baseline.json` (generated from the corpus) and PATCHes
every document that drifted, through the normal admin API so each change lands in
the audit chain.

Environment:
  SUPABASE_URL, SUPABASE_ANON_KEY (or SUPABASE_SERVICE_ROLE_KEY), EKC_API_URL,
  EKC_DEMO_PASSWORD
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / "data" / "access_baseline.json"


def http(url: str, method: str, payload: dict | None, headers: dict[str, str]):
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            body = response.read().decode("utf-8")
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as exc:
        raise SystemExit(f"{method} {url} -> {exc.code}: {exc.read().decode('utf-8')[:200]}") from exc


def main() -> int:
    supabase = os.environ["SUPABASE_URL"].rstrip("/")
    apikey = os.environ.get("SUPABASE_ANON_KEY") or os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    api = os.environ["EKC_API_URL"].rstrip("/")
    password = os.environ["EKC_DEMO_PASSWORD"]

    session = http(
        f"{supabase}/auth/v1/token?grant_type=password",
        "POST",
        {"email": "admin@ekc.local", "password": password},
        {"apikey": apikey, "Content-Type": "application/json"},
    )
    token = session["access_token"]
    auth = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    listing = http(f"{api}/documents", "GET", None, auth)
    changed = 0
    for document in listing.get("documents", []):
        want = baseline.get(document["slug"])
        if not want:
            continue
        if (
            document["access_level"] != want["access_level"]
            or (document.get("department") or None) != (want.get("department") or None)
        ):
            http(
                f"{api}/documents/{document['id']}",
                "PATCH",
                {"access_level": want["access_level"], "department": want.get("department")},
                auth,
            )
            changed += 1
            print(f"reset {document['slug']} -> {want['access_level']}/{want.get('department') or '-'}")
    print(f"checked {len(listing.get('documents', []))} documents, reset {changed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
