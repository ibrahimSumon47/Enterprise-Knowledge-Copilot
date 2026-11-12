#!/usr/bin/env python3
"""Verify the deployed audit hash chain and fail when it does not hold.

Signs in as the admin demo account, calls `/audit/verify` and exits non-zero when
the API reports a break, a non-200 status or a malformed body. Used by
`.github/workflows/audit-integrity.yml`, and runnable by hand.

Environment:
  SUPABASE_URL, SUPABASE_ANON_KEY, EKC_DEMO_PASSWORD   required
  EKC_API_URL    default https://enterprise-knowledge-copilot-2u57.onrender.com
  EKC_ADMIN_EMAIL default admin@ekc.local
  GITHUB_STEP_SUMMARY  written when set, so the run page shows the numbers
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_API = "https://enterprise-knowledge-copilot-2u57.onrender.com"
DEFAULT_EMAIL = "admin@ekc.local"
# The weekly run and a manual dispatch can force a pass from genesis, so a
# forged checkpoint cannot hide an old edit from every scheduled run.
FULL = "--full" in sys.argv[1:]
TIMEOUT = 120
# The free API instance sleeps after 15 idle minutes; the first request of a
# scheduled run can land while it wakes, so transport errors are retried.
RETRIES = 5
RETRY_WAIT = 20
# The cadence is not duplicated here: the panel, this summary and the workflow
# cron all derive from audit-cadence.json (lib/audit.test.ts pins the cron).
CADENCE_FILE = Path(__file__).resolve().parent.parent / "audit-cadence.json"


def check_interval_hours() -> float:
    try:
        raw = json.loads(CADENCE_FILE.read_text(encoding="utf-8"))
        return float(raw["check_interval_hours"])
    except (OSError, KeyError, TypeError, ValueError):
        print("::warning::audit-cadence.json unreadable; assuming a 6 h interval")
        return 6.0


def age_text(seconds: float) -> str:
    minutes = int(seconds // 60)
    if minutes < 1:
        return "just now"
    if minutes < 60:
        return f"{minutes} min ago"
    hours = minutes / 60
    if hours < 24:
        return f"{hours:.1f} h ago"
    return f"{hours / 24:.1f} d ago"


def http_json(url: str, method: str, payload: dict | None, headers: dict[str, str]) -> dict:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(url, data=data, method=method, headers=headers)
    with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
        return json.loads(response.read().decode("utf-8"))


def sign_in(supabase_url: str, anon_key: str, email: str, password: str) -> str:
    body = http_json(
        f"{supabase_url.rstrip('/')}/auth/v1/token?grant_type=password",
        "POST",
        {"email": email, "password": password},
        {"apikey": anon_key, "Content-Type": "application/json"},
    )
    token = body.get("access_token")
    if not token:
        raise RuntimeError("sign-in returned no access token")
    return str(token)


def summarize(summary: str) -> None:
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if path:
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(summary + "\n")


def main() -> int:
    api = os.environ.get("EKC_API_URL", DEFAULT_API).rstrip("/")
    supabase_url = os.environ.get("SUPABASE_URL", "")
    anon_key = os.environ.get("SUPABASE_ANON_KEY", "")
    password = os.environ.get("EKC_DEMO_PASSWORD", "")
    email = os.environ.get("EKC_ADMIN_EMAIL", DEFAULT_EMAIL)

    missing = [
        name
        for name, value in (
            ("SUPABASE_URL", supabase_url),
            ("SUPABASE_ANON_KEY", anon_key),
            ("EKC_DEMO_PASSWORD", password),
        )
        if not value
    ]
    if missing:
        print(f"::error::missing configuration: {', '.join(missing)}")
        return 2

    try:
        token = sign_in(supabase_url, anon_key, email, password)
    except Exception as exc:  # noqa: BLE001 - the reason belongs in the annotation
        print(f"::error::admin sign-in failed: {type(exc).__name__}: {str(exc)[:160]}")
        return 1

    result: dict | None = None
    for attempt in range(1, RETRIES + 1):
        try:
            result = http_json(
                f"{api}/audit/verify{'?full=true' if FULL else ''}",
                "POST",
                {},
                {"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            )
            break
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", "replace")[:200]
            if exc.code in (502, 503, 504) and attempt < RETRIES:
                print(f"  attempt {attempt}: HTTP {exc.code}, retrying in {RETRY_WAIT}s")
                time.sleep(RETRY_WAIT)
                continue
            print(f"::error::/audit/verify returned HTTP {exc.code}: {body}")
            return 1
        except Exception as exc:  # noqa: BLE001 - network failures must fail the run too
            if attempt < RETRIES:
                print(f"  attempt {attempt}: {type(exc).__name__}, retrying in {RETRY_WAIT}s")
                time.sleep(RETRY_WAIT)
                continue
            print(f"::error::/audit/verify unreachable: {type(exc).__name__}: {str(exc)[:160]}")
            return 1

    if result is None:
        print("::error::/audit/verify returned no body after retries")
        return 1

    entries = result.get("entries")
    intact = result.get("intact")
    broken = result.get("broken_ids") or []
    anchor = result.get("anchor_id")
    genesis = result.get("anchored_at_genesis")
    complete = result.get("complete", True)
    mode = result.get("mode", "full")
    verified_now = result.get("verified_now", entries)
    checkpoint = result.get("checkpoint_id")
    checkpoint_at = result.get("checkpoint_at")
    interval = check_interval_hours()
    checkpoint_age = None
    if isinstance(checkpoint_at, str):
        try:
            stamped = datetime.fromisoformat(checkpoint_at.replace("Z", "+00:00"))
            checkpoint_age = max(0.0, (datetime.now(timezone.utc) - stamped).total_seconds())
        except ValueError:
            checkpoint_age = None
    stale = checkpoint_age is not None and checkpoint_age > interval * 3600
    age_label = age_text(checkpoint_age) if checkpoint_age is not None else "unknown"
    first_id = result.get("first_id")
    last_id = result.get("last_id")

    if not isinstance(entries, int) or not isinstance(intact, bool):
        print(f"::error::unexpected /audit/verify body: {json.dumps(result)[:200]}")
        return 1

    print(
        f"audit chain: mode={mode} rows={first_id}..{last_id} entries={entries} "
        f"verified_now={verified_now} checkpoint={checkpoint} age={age_label} "
        f"stale={stale} intact={intact} "
        f"broken={len(broken)} complete={complete} at_genesis={genesis} anchor={anchor}"
    )
    summarize(
        "## Audit chain\n\n"
        f"- entries: **{entries}** total, **{verified_now}** hashed this run ({first_id}..{last_id})\n"
        f"- intact: **{intact}**\n"
        f"- broken rows: **{len(broken)}**\n"
        f"- whole log checked: **{complete}**\n"
        f"- anchored at genesis: **{genesis}** (anchor #{anchor})\n"
        f"- checkpoint: **#{checkpoint if checkpoint is not None else 'none'}**, "
        f"last advanced **{age_label}** (stale after {interval:g} h: **{stale}**)\n"
    )

    if not intact:
        first = ", ".join(str(row) for row in broken[:10])
        print(f"::error::audit chain is broken at {len(broken)} rows (first: {first})")
        return 1
    if not complete:
        print("::error::audit verification stopped at the row ceiling; the log was not fully checked")
        return 1
    if not genesis:
        print("::error::audit chain does not start at genesis; the oldest rows are missing")
        return 1
    if FULL and mode != "full":
        print(f"::error::--full was requested but the API verified in {mode} mode")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
