"""Explain every answer on the golden set: retrieval, decision and cause.

Usage mirrors run_eval.py:
  python eval/diagnose.py --split test --password ... --api-url ... --supabase-url ... --anon-key ...
Writes docs/reports/answer_diagnosis.json and prints refusal groups.
"""
from __future__ import annotations

import argparse
import collections
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPLITS = {"dev": ROOT / "eval/golden_dev.jsonl", "test": ROOT / "eval/golden_test.jsonl"}
ROLE_EMAILS = {
    "guest": "guest@ekc.local", "employee": "employee@ekc.local",
    "engineering": "engineering@ekc.local", "security": "security@ekc.local",
    "hr": "hr@ekc.local", "finance": "finance@ekc.local", "admin": "admin@ekc.local",
}


def http_json(url, method, payload, headers, timeout=90):
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8") if payload is not None else None,
        method=method,
        headers=headers,
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def sign_in(supabase, anon, email, password):
    body = http_json(
        f"{supabase.rstrip('/')}/auth/v1/token?grant_type=password", "POST",
        {"email": email, "password": password},
        {"apikey": anon, "Content-Type": "application/json"}, timeout=30,
    )
    return body["access_token"]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", choices=sorted(SPLITS), default="test")
    parser.add_argument("--api-url", required=True)
    parser.add_argument("--supabase-url", required=True)
    parser.add_argument("--anon-key", required=True)
    parser.add_argument("--password", required=True)
    args = parser.parse_args()
    items = [json.loads(line) for line in SPLITS[args.split].read_text(encoding="utf-8").splitlines() if line.strip()]

    tokens = {}
    rows = []
    for item in items:
        role = item.get("role", "employee")
        if role not in tokens:
            tokens[role] = sign_in(args.supabase_url, args.anon_key, ROLE_EMAILS[role], args.password)
        started = time.perf_counter()
        try:
            response = http_json(
                f"{args.api_url.rstrip('/')}/chat", "POST", {"question": item["question"]},
                {"Authorization": f"Bearer {tokens[role]}", "Content-Type": "application/json"},
            )
        except urllib.error.HTTPError as exc:
            response = {"refused": True, "citations": [], "outage": True, "error": f"http {exc.code}"}
        except Exception as exc:  # noqa: BLE001
            response = {"refused": True, "citations": [], "outage": True, "error": str(exc)}
        latency = int((time.perf_counter() - started) * 1000)
        citations = response.get("citations") or []
        keywords = [k.lower() for k in item.get("expect", {}).get("keywords", [])]
        gold_hit = any(
            any(k in " ".join(str(c.get(k2, "")) for k2 in ("title", "snippet", "heading")).lower() for k in keywords)
            for c in citations
        )
        if response.get("outage"):
            cause = "provider error or timeout"
        elif response.get("refused") and not citations:
            cause = "floor refusal (no candidates above the minimum)"
        elif response.get("refused"):
            cause = "model said not answerable"
        elif not citations:
            cause = "citation verification failed"
        elif not gold_hit and item.get("expect", {}).get("answerable"):
            cause = "answered from a non-gold passage"
        else:
            cause = "ok"
        rows.append({
            "id": item["id"], "role": role, "answerable": bool(item.get("expect", {}).get("answerable")),
            "provider": response.get("provider"), "refused": bool(response.get("refused")),
            "cause": cause, "gold_in_citations": gold_hit, "citations": len(citations),
            "latency_ms": response.get("latency_ms", latency), "error": response.get("error"),
            "answer_prefix": str(response.get("answer", ""))[:200],
        })

    counts = collections.Counter(row["cause"] for row in rows)
    Path("docs/reports").mkdir(parents=True, exist_ok=True)
    Path("docs/reports/answer_diagnosis.json").write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(counts, indent=2))
    print("note: citations are the only rank evidence /chat exposes; retrieval hit@k is not observable here")
    return 0


if __name__ == "__main__":
    sys.exit(main())
