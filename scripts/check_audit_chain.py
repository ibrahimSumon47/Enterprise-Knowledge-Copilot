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
import time
import urllib.error
import urllib.request

DEFAULT_API = "https://enterprise-knowledge-copilot-2u57.onrender.com"
DEFAULT_EMAIL = "admin@ekc.local"
TIMEOUT = 120
# The free API instance sleeps after 15 idle minutes; the first request of a
# scheduled run can land while it wakes, so transport errors are retried.
RETRIES = 5
RETRY_WAIT = 20


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
                f"{api}/audit/verify",
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

    if not isinstance(entries, int) or not isinstance(intact, bool):
        print(f"::error::unexpected /audit/verify body: {json.dumps(result)[:200]}")
        return 1

    print(
        f"audit chain: entries={entries} intact={intact} broken={len(broken)} "
        f"anchor={anchor} at_genesis={genesis}"
    )
    summarize(
        "## Audit chain\n\n"
        f"- entries checked: **{entries}**\n"
        f"- intact: **{intact}**\n"
        f"- broken rows: **{len(broken)}**\n"
        f"- window anchor: #{anchor} (genesis: {genesis})\n"
    )

    if not intact:
        first = ", ".join(str(row) for row in broken[:10])
        print(f"::error::audit chain is broken at {len(broken)} rows (first: {first})")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
