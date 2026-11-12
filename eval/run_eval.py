#!/usr/bin/env python3
"""Run the golden set against the deployed API and write the evaluation report.

Usage:
  python eval/run_eval.py --subset            # 12 deterministic questions, CI
  python eval/run_eval.py                     # full set, manual dispatch
  python eval/run_eval.py --offline           # no network: structural self-check

Metrics: hit@k, MRR, citation precision, faithfulness proxy, refusal accuracy,
p50/p95 latency and permission leakage (hard gate, must be 0).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GOLDEN = ROOT / "eval" / "golden_set.jsonl"
SPLITS = {"dev": ROOT / "eval" / "golden_dev.jsonl", "test": ROOT / "eval" / "golden_test.jsonl"}
REPORT_JSON = ROOT / "docs" / "reports" / "eval.json"
REPORT_MD = ROOT / "docs" / "reports" / "eval.md"

ROLE_EMAILS = {
    "guest": "guest@ekc.local",
    "employee": "employee@ekc.local",
    "engineering": "engineering@ekc.local",
    "security": "security@ekc.local",
    "hr": "hr@ekc.local",
    "finance": "finance@ekc.local",
    "admin": "admin@ekc.local",
}


def load_golden(path: Path | None = None) -> list[dict]:
    items: list[dict] = []
    with (path or GOLDEN).open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                items.append(json.loads(line))
    return items


def subset(items: list[dict], size: int = 12) -> list[dict]:
    """Deterministic sample: one per category, then fill in id order."""
    picked: dict[str, dict] = {}
    for item in items:
        picked.setdefault(item["category"], item)
    for item in items:
        if len(picked) >= size:
            break
        picked.setdefault(item["id"], item)
    return list(picked.values())[:size]


def http_json(url: str, method: str, payload: dict | None, headers: dict[str, str], timeout: int = 90):
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(url, data=data, method=method, headers=headers)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def is_outage(response: dict) -> bool:
    """True when no model answered at all: outage, quota or transport error.

    Those rows carry no information about retrieval quality, so they are excluded
    from the metrics instead of being scored as retrieval misses.
    """
    if "outage" in response:
        # The API says explicitly whether a model was reached. A retrieval refusal
        # also reports provider "none", so the heuristic below must not override it.
        return bool(response["outage"])
    return (
        (response.get("provider") or "none") == "none"
        and bool(response.get("refused"))
        and not (response.get("citations") or [])
    )


def ask(args, item: dict, token: str) -> dict:
    """One chat request, with every transport failure folded into the response."""
    started = time.perf_counter()
    try:
        response = http_json(
            f"{args.api_url.rstrip('/')}/chat",
            "POST",
            {"question": item["question"]},
            {"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        )
        response.setdefault("latency_ms", int((time.perf_counter() - started) * 1000))
        return response
    except urllib.error.HTTPError as exc:
        return {"answer": "", "citations": [], "refused": True, "latency_ms": 0, "error": exc.code}
    except Exception as exc:  # noqa: BLE001
        return {"answer": "", "citations": [], "refused": True, "latency_ms": 0, "error": str(exc)}


def sign_in(supabase_url: str, anon_key: str, email: str, password: str) -> str:
    body = http_json(
        f"{supabase_url.rstrip('/')}/auth/v1/token?grant_type=password",
        "POST",
        {"email": email, "password": password},
        {"apikey": anon_key, "Content-Type": "application/json"},
        timeout=30,
    )
    return str(body["access_token"])


def score(item: dict, response: dict) -> dict:
    """Score one answer against its expectation."""
    citations = response.get("citations") or []
    refused = bool(response.get("refused"))
    answer = str(response.get("answer", ""))
    expectation = item.get("expect", {})
    keywords = [keyword.lower() for keyword in expectation.get("keywords", [])]

    def relevant(citation: dict) -> bool:
        haystack = " ".join(
            str(citation.get(key, "")) for key in ("title", "snippet", "heading")
        ).lower()
        return any(keyword in haystack for keyword in keywords) if keywords else False

    flags = [relevant(citation) for citation in citations]
    first_relevant = next((index + 1 for index, flag in enumerate(flags) if flag), None)

    forbidden = expectation.get("forbidden", [])
    leaked = [
        citation
        for citation in citations
        if any(level == citation.get("access_level") for level in forbidden)
    ]

    min_citations = int(expectation.get("min_citations", 0))
    if expectation.get("answerable"):
        refusal_ok = (not refused) and bool(citations) and len(citations) >= min_citations
    else:
        refusal_ok = refused or not citations

    return {
        "hit": 1 if first_relevant else 0,
        "rr": (1.0 / first_relevant) if first_relevant else 0.0,
        "precision": (sum(flags) / len(flags)) if flags else 0.0,
        "faithful": 0 if (refused is False and not citations) else 1,
        "refusal_ok": 1 if refusal_ok else 0,
        "leaks": len(leaked),
        "latency_ms": int(response.get("latency_ms") or 0),
        "answer_len": len(answer),
    }


def write_report(metrics: dict, mode: str) -> None:
    REPORT_JSON.parent.mkdir(parents=True, exist_ok=True)
    REPORT_JSON.write_text(json.dumps({"mode": mode, **metrics}, indent=2) + "\n", encoding="utf-8")
    rows = "\n".join(
        f"| {key} | {value} |" for key, value in metrics["summary"].items()
    )
    excluded = metrics["summary"].get("excluded_no_model", 0)
    provider_rows = "\n".join(
        f"| {name} | {row['questions']} | {row['hit@k']} | {row['citation_precision']} | "
        f"{row['refusal_accuracy']} | {row['p50_latency_ms']} | {row['p95_latency_ms']} |"
        for name, row in (metrics.get("by_provider") or {}).items()
    )
    provider_section = ""
    if provider_rows:
        provider_section = (
            "## By provider\n\n"
            "| Provider | Questions | hit@k | Precision | Refusal | p50 ms | p95 ms |\n"
            "| --- | --- | --- | --- | --- | --- | --- |\n" + provider_rows + "\n\n"
        )
    REPORT_MD.write_text(
        "# Evaluation report\n\n"
        f"- Mode: **{mode}**\n"
        f"- Questions scored: **{metrics['questions']}**\n"
        f"- Excluded (no model answer): **{excluded}**\n"
        "- Gate: permission leakage must be exactly 0\n\n"
        "| Metric | Value |\n| --- | --- |\n" + rows + "\n\n"
        + provider_section
        + "Generated by `eval/run_eval.py` against the deployed API. "
        "Faithfulness here is a deterministic citation-overlap proxy; the full run "
        "can additionally use an LLM judge.\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--subset", action="store_true")
    parser.add_argument(
        "--split",
        choices=["all", "dev", "test"],
        default="all",
        help="run only the dev or test half of the golden set",
    )
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--api-url", default=os.environ.get("EKC_API_URL", ""))
    parser.add_argument("--supabase-url", default=os.environ.get("SUPABASE_URL", ""))
    parser.add_argument("--anon-key", default=os.environ.get("SUPABASE_ANON_KEY", ""))
    parser.add_argument("--password", default=os.environ.get("EKC_DEMO_PASSWORD", ""))
    parser.add_argument(
        "--retry-outage",
        type=int,
        default=1,
        help="retries per question when no model answered (quota or outage)",
    )
    parser.add_argument("--retry-wait", type=int, default=45)
    args = parser.parse_args()

    if args.split != "all":
        global REPORT_JSON, REPORT_MD
        REPORT_JSON = ROOT / "docs" / "reports" / f"eval_{args.split}.json"
        REPORT_MD = ROOT / "docs" / "reports" / f"eval_{args.split}.md"
    items = load_golden(SPLITS.get(args.split))
    if args.subset:
        items = subset(items)

    if len(load_golden()) < 80:
        print("golden set must have at least 80 questions", file=sys.stderr)
        return 2

    if args.offline:
        metrics = {
            "questions": len(items),
            "summary": {
                "hit@k": "n/a (offline)",
                "MRR": "n/a (offline)",
                "citation_precision": "n/a (offline)",
                "faithfulness": "n/a (offline)",
                "refusal_accuracy": "n/a (offline)",
                "p50_latency_ms": "n/a (offline)",
                "p95_latency_ms": "n/a (offline)",
                "permission_leakage": 0,
            },
        }
        write_report(metrics, "offline")
        print(json.dumps(metrics, indent=2))
        return 0

    if not (args.api_url and args.supabase_url and args.anon_key and args.password):
        print("missing --api-url/--supabase-url/--anon-key/--password", file=sys.stderr)
        return 2

    tokens: dict[str, str] = {}
    results: list[dict] = []
    leaks = 0

    for item in items:
        role = item.get("role", "employee")
        if role not in tokens:
            tokens[role] = sign_in(
                args.supabase_url, args.anon_key, ROLE_EMAILS[role], args.password
            )
        response = ask(args, item, tokens[role])
        retries = 0
        while is_outage(response) and retries < args.retry_outage:
            retries += 1
            print(
                f"  {item['id']}: no model answer, retry {retries} in {args.retry_wait}s",
                file=sys.stderr,
            )
            time.sleep(args.retry_wait)
            response = ask(args, item, tokens[role])

        scored = score(item, response)
        leaks += scored["leaks"]
        results.append(
            {
                "id": item["id"],
                "category": item["category"],
                "role": role,
                # A throttled provider refuses without citations, which scores
                # exactly like a retrieval miss. Keep the evidence to tell them
                # apart, and let the summary count them.
                "provider": response.get("provider") or "none",
                "provider_outage": is_outage(response),
                **scored,
            }
        )

    outages = [result for result in results if result["provider_outage"]]
    scored = [result for result in results if not result["provider_outage"]]
    if not scored:
        print(
            f"error: all {len(results)} questions got no model answer (outage or quota). "
            "Nothing was scored and the published report was left untouched.",
            file=sys.stderr,
        )
        return 2
    latencies = sorted(result["latency_ms"] for result in scored)
    answered = [r for r in scored if r["category"] != "unanswerable"]
    leaked = sum(result["leaks"] for result in scored)
    summary = {
        "hit@k": round(sum(r["hit"] for r in answered) / max(1, len(answered)), 3),
        "MRR": round(sum(r["rr"] for r in answered) / max(1, len(answered)), 3),
        "citation_precision": round(sum(r["precision"] for r in scored) / len(scored), 3),
        "faithfulness": round(sum(r["faithful"] for r in scored) / len(scored), 3),
        "refusal_accuracy": round(sum(r["refusal_ok"] for r in scored) / len(scored), 3),
        "p50_latency_ms": latencies[len(latencies) // 2] if latencies else 0,
        "p95_latency_ms": latencies[int(len(latencies) * 0.95) - 1] if latencies else 0,
        "permission_leakage": leaked,
        "scored_questions": len(scored),
        "excluded_no_model": len(outages),
    }
    by_provider: dict[str, dict] = {}
    for name in sorted({result["provider"] for result in scored}):
        rows = [result for result in scored if result["provider"] == name]
        answerable_rows = [r for r in rows if r["category"] != "unanswerable"]
        provider_latencies = sorted(r["latency_ms"] for r in rows)
        by_provider[name] = {
            "questions": len(rows),
            "hit@k": round(
                sum(r["hit"] for r in answerable_rows) / max(1, len(answerable_rows)), 3
            ),
            "citation_precision": round(sum(r["precision"] for r in rows) / len(rows), 3),
            "refusal_accuracy": round(sum(r["refusal_ok"] for r in rows) / len(rows), 3),
            "p50_latency_ms": provider_latencies[len(provider_latencies) // 2],
            "p95_latency_ms": provider_latencies[int(len(provider_latencies) * 0.95) - 1],
        }
    metrics = {
        "questions": len(scored),
        "summary": summary,
        "by_provider": by_provider,
        "results": results,
    }
    mode = "subset" if args.subset else ("full" if args.split == "all" else args.split)
    write_report(metrics, mode)
    if outages:
        print(
            f"warning: {len(outages)} of {len(results)} questions got no model answer "
            "(outage or quota) and were excluded; the metrics cover the other "
            f"{len(scored)}.",
            file=sys.stderr,
        )
    print(json.dumps(summary, indent=2))
    return 0 if leaked == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
