#!/usr/bin/env python3
"""Model-free retrieval evaluation.

Calls `/admin/retrieval?all_candidates=true`, which reranks with the local
cross-encoder and returns every scored passage, and computes ranking and refusal
metrics without a single language-model call. That makes it immune to the free
quota that kills the end-to-end runs.

Usage:
  python eval/retrieval_eval.py --split dev --repeat 3
  python eval/retrieval_eval.py --split test --repeat 3
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPLITS = {"dev": ROOT / "eval" / "golden_dev.jsonl", "test": ROOT / "eval" / "golden_test.jsonl"}
REPORT = ROOT / "docs" / "reports" / "retrieval_eval.json"

ROLE_EMAILS = {
    "guest": "guest@ekc.local",
    "employee": "employee@ekc.local",
    "engineering": "engineering@ekc.local",
    "security": "security@ekc.local",
    "hr": "hr@ekc.local",
    "finance": "finance@ekc.local",
    "admin": "admin@ekc.local",
}


def http_json(url: str, method: str, payload: dict | None, headers: dict[str, str], timeout: int = 120):
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(url, data=data, method=method, headers=headers)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def sign_in(supabase: str, apikey: str, email: str, password: str) -> str:
    body = http_json(
        f"{supabase.rstrip('/')}/auth/v1/token?grant_type=password",
        "POST",
        {"email": email, "password": password},
        {"apikey": apikey, "Content-Type": "application/json"},
        timeout=30,
    )
    return str(body["access_token"])


def get_with_retry(url: str, token: str, attempts: int = 6) -> dict | None:
    """Retry the shared free instance, and never kill a run over one question.

    The host answers 403/429 when a batch arrives too fast and 502 while it wakes
    up; both are transport, not a verdict about retrieval.
    """
    for attempt in range(attempts):
        request = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if exc.code not in (403, 429, 502, 503) or attempt == attempts - 1:
                print(f"  giving up after {exc.code}: {url.split('question=')[1][:60]}", file=sys.stderr)
                return None
            time.sleep(8 * (attempt + 1))
        except Exception as exc:  # noqa: BLE001 - the record is better than the crash
            if attempt == attempts - 1:
                print(f"  giving up after {exc}", file=sys.stderr)
                return None
            time.sleep(5 * (attempt + 1))
    return None


def relevant(candidate: dict, keywords: list[str]) -> bool:
    haystack = " ".join(
        str(candidate.get(key, "")) for key in ("title", "heading", "snippet")
    ).lower()
    return any(keyword in haystack for keyword in keywords)


def ranks(candidates: list[dict], key: str) -> list[dict]:
    return sorted(candidates, key=lambda item: item.get(key, 0.0), reverse=True)


def blend_order(candidates: list[dict], weight: float, rrf_weight: float = 1.0) -> list[dict]:
    if not candidates:
        return []
    rrf_values = [item.get("rrf_score", 0.0) for item in candidates]
    rerank_values = [item.get("rerank_score", 0.0) for item in candidates]

    def norm(value: float, values: list[float]) -> float:
        low, high = min(values), max(values)
        return 0.0 if high == low else (value - low) / (high - low)

    scored = [
        {
            **item,
            "_blend": (
                rrf_weight * norm(item.get("rrf_score", 0.0), rrf_values)
                + weight * norm(item.get("rerank_score", 0.0), rerank_values)
            )
            / (rrf_weight + weight),
        }
        for item in candidates
    ]
    return sorted(scored, key=lambda item: item["_blend"], reverse=True)


def evaluate_order(order: list[dict], keywords: list[str], depths=(3, 10)) -> dict:
    first = next((index + 1 for index, item in enumerate(order) if relevant(item, keywords)), None)
    metrics = {"mrr": 1.0 / first if first else 0.0, "top1": 1 if first == 1 else 0}
    for depth in depths:
        metrics[f"hit@{depth}"] = 1 if first and first <= depth else 0
        metrics[f"recall@{depth}"] = metrics[f"hit@{depth}"]
    metrics["first_rank"] = first
    return metrics


def auc(answerable: list[float], unanswerable: list[float]) -> float | None:
    """Probability that a random answerable question scores above a random unanswerable one."""
    if not answerable or not unanswerable:
        return None
    wins = 0.0
    for value in answerable:
        for other in unanswerable:
            wins += 1.0 if value > other else 0.5 if value == other else 0.0
    return wins / (len(answerable) * len(unanswerable))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", choices=["dev", "test"], default="dev")
    parser.add_argument("--repeat", type=int, default=3)
    parser.add_argument("--api-url", required=True)
    parser.add_argument("--supabase-url", required=True)
    parser.add_argument("--anon-key", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--threshold", type=float, default=0.15)
    args = parser.parse_args()

    questions = [
        json.loads(line)
        for line in SPLITS[args.split].read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    # The debug endpoint is admin-only, so the caller is the admin account; the
    # `role` query parameter is what varies the corpus slice under test.
    admin_token = sign_in(
        args.supabase_url, args.anon_key, ROLE_EMAILS["admin"], args.password
    )
    passes: list[dict] = []

    for iteration in range(args.repeat):
        rows: list[dict] = []
        failures = 0
        for item in questions:
            role = item.get("role", "employee")
            query = urllib.parse.urlencode(
                {"question": item["question"], "role": role, "all_candidates": "true"}
            )
            response = get_with_retry(
                f"{args.api_url.rstrip('/')}/admin/retrieval?{query}", admin_token
            )
            if response is None:
                failures += 1
                print(f"  failed {item['id']} role={role}", file=sys.stderr)
                continue
            time.sleep(0.4)
            candidates = response.get("candidates") or []
            keywords = [keyword.lower() for keyword in item["expect"].get("keywords", [])]
            answerable = bool(item["expect"].get("answerable"))
            top_rerank = max((c.get("rerank_score", 0.0) for c in candidates), default=0.0)
            rows.append(
                {
                    "id": item["id"],
                    "category": item["category"],
                    "answerable": answerable,
                    "candidates": candidates,
                    "keywords": keywords,
                    "top_rerank": top_rerank,
                }
            )
        passes.append({"iteration": iteration + 1, "rows": rows, "failures": failures})
        print(f"pass {iteration + 1}/{args.repeat}: {len(rows)} questions", file=sys.stderr)

    configs = {
        "fused": lambda candidates: ranks(candidates, "rrf_score"),
        "rerank": lambda candidates: ranks(candidates, "rerank_score"),
        "blend-0.5": lambda candidates: blend_order(candidates, 0.5),
        "blend-1.0": lambda candidates: blend_order(candidates, 1.0),
        "blend-2.0": lambda candidates: blend_order(candidates, 2.0),
    }

    summary: dict[str, dict] = {}
    for name, build in configs.items():
        per_pass = []
        for run in passes:
            answerable_scores: list[float] = []
            unanswerable_scores: list[float] = []
            answered_ok = refused_ok = answered_total = refused_total = 0
            hits: dict[str, list[int]] = {"hit@3": [], "hit@10": []}
            mrr_values: list[float] = []
            for row in run["rows"]:
                order = build(row["candidates"])
                metrics = evaluate_order(order, row["keywords"])
                if row["answerable"]:
                    mrr_values.append(metrics["mrr"])
                    for key in hits:
                        hits[key].append(metrics[key])
                # Fused order is ranked by RRF, whose scale is not the rerank scale,
                # so its answer/refusal numbers would compare two different rulers.
                top_score = (
                    order[0].get("rerank_score", 0.0)
                    if name == "rerank"
                    else order[0].get("_blend", 0.0)
                )
                decision_answered = top_score >= args.threshold
                if name == "fused":
                    continue
                if row["answerable"]:
                    answerable_scores.append(top_score)
                    answered_total += 1
                    answered_ok += 1 if decision_answered else 0
                else:
                    unanswerable_scores.append(top_score)
                    refused_total += 1
                    refused_ok += 1 if not decision_answered else 0
            per_pass.append(
                {
                    "hit@3": sum(hits["hit@3"]) / max(1, len(hits["hit@3"])),
                    "hit@10": sum(hits["hit@10"]) / max(1, len(hits["hit@10"])),
                    "mrr": sum(mrr_values) / max(1, len(mrr_values)),
                    "answer_rate": answered_ok / max(1, answered_total),
                    "refusal_recall": refused_ok / max(1, refused_total),
                    "separation_auc": auc(answerable_scores, unanswerable_scores),
                    "answerable_median": statistics.median(answerable_scores)
                    if answerable_scores
                    else None,
                    "unanswerable_median": statistics.median(unanswerable_scores)
                    if unanswerable_scores
                    else None,
                }
            )
        keys = [key for key in per_pass[0] if per_pass[0][key] is not None]
        summary[name] = {
            key: {
                "mean": round(statistics.mean([run[key] for run in per_pass]), 4),
                "spread": round(
                    max([run[key] for run in per_pass]) - min([run[key] for run in per_pass]),
                    4,
                ),
            }
            for key in keys
        }

    # Threshold sweep on the rerank score: the refusal target is "refuse at
    # least 90% of unanswerable questions while refusing as few answerable ones
    # as possible", and that trade-off is decided here, on dev only.
    sweep = []
    for index in range(31):
        threshold = round(index * 0.02, 2)
        refused_answerable = refused_unanswerable = answerable_total = unanswerable_total = 0
        for run in passes:
            for row in run["rows"]:
                order = ranks(row["candidates"], "rerank_score")
                top = order[0].get("rerank_score", 0.0) if order else 0.0
                refused = top < threshold
                if row["answerable"]:
                    answerable_total += 1
                    refused_answerable += 1 if refused else 0
                else:
                    unanswerable_total += 1
                    refused_unanswerable += 1 if refused else 0
        recall = refused_unanswerable / max(1, unanswerable_total)
        precision = refused_unanswerable / max(1, refused_unanswerable + refused_answerable)
        sweep.append(
            {
                "threshold": threshold,
                "wrong_refusals": refused_answerable / max(1, len(passes)),
                "refusal_recall": round(recall, 4),
                "refusal_precision": round(precision, 4),
            }
        )
    meeting = [row for row in sweep if row["refusal_recall"] >= 0.9]
    best_threshold = min(meeting, key=lambda row: row["wrong_refusals"]) if meeting else None

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(
        json.dumps(
            {
                "split": args.split,
                "repeat": args.repeat,
                "summary": summary,
                "threshold_sweep": sweep,
                "best_threshold": best_threshold,
                "failures": [run["failures"] for run in passes],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"\n{args.split} split, {args.repeat} passes, model-free")
    header = f"{'config':10} {'hit@3':>12} {'hit@10':>12} {'MRR':>12} {'answer%':>12} {'refusal%':>12} {'AUC':>12}"
    print(header)
    for name, metrics in summary.items():
        def cell(key: str) -> str:
            if key not in metrics:
                return "—"
            return f"{metrics[key]['mean']:.3f}±{metrics[key]['spread']:.3f}"

        print(
            f"{name:10} {cell('hit@3'):>12} {cell('hit@10'):>12} {cell('mrr'):>12} "
            f"{cell('answer_rate'):>12} {cell('refusal_recall'):>12} {cell('separation_auc'):>12}"
        )
    if best_threshold:
        print(
            f"dev threshold with >=90% unanswerable refused: {best_threshold['threshold']} "
            f"(wrong refusals {best_threshold['wrong_refusals']:.1f})"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
