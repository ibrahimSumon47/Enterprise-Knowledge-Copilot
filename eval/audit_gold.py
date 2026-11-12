#!/usr/bin/env python3
"""Audit the golden set against the corpus, then split it into dev and test.

Two questions per item:

1. Is the question answerable from the corpus *for that role*? Every keyword is
   looked up in the documents the role can read. If none of them appears, the
   label and the corpus disagree and the item cannot be scored honestly.
2. Is the label the right way round? An item marked `answerable: false` whose
   keywords all appear in accessible documents may be answerable after all.

The split is stratified by category and deterministic (a hash of the id), so the
same question never moves between dev and test.

Usage: python eval/audit_gold.py [--write-split]
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GOLD = ROOT / "eval" / "golden_set.jsonl"
CORPUS = ROOT / "data" / "corpus.jsonl"
OUT = ROOT / "docs" / "reports" / "gold_audit.json"
DEV = ROOT / "eval" / "golden_dev.jsonl"
TEST = ROOT / "eval" / "golden_test.jsonl"

ACCESS = {
    "guest": {"public"},
    "employee": {"public", "employee"},
    "engineering": {"public", "employee", "department:engineering"},
    "security": {"public", "employee", "department:security"},
    "hr": {"public", "employee", "department:people"},
    "finance": {"public", "employee", "department:finance"},
    "admin": {"public", "employee", "department:engineering", "department:security",
              "department:people", "department:finance", "confidential"},
}


def visible(document: dict, role: str) -> bool:
    allowed = ACCESS.get(role, {"public"})
    level = document.get("access_level") or "public"
    if level in {"public", "employee"}:
        return level in allowed
    if level == "department":
        return f"department:{document.get('department')}" in allowed
    if level == "confidential":
        return "confidential" in allowed
    return False


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def assign_split(gold: list[dict]) -> dict[str, str]:
    """60% dev / 40% test, ranked inside each category so both halves keep every kind."""
    assignment: dict[str, str] = {}
    by_category: dict[str, list[str]] = {}
    for item in gold:
        by_category.setdefault(item["category"], []).append(item["id"])
    for ids in by_category.values():
        ordered = sorted(ids)
        cutoff = round(len(ordered) * 0.6)
        for rank, item_id in enumerate(ordered):
            assignment[item_id] = "dev" if rank < cutoff else "test"
    return assignment


def split_of(item_id: str, assignment: dict[str, str]) -> str:
    if item_id in assignment:
        return assignment[item_id]
    digest = hashlib.sha256(item_id.encode("utf-8")).hexdigest()
    return "dev" if int(digest[:8], 16) % 5 < 3 else "test"


def main() -> int:
    corpus = load_jsonl(CORPUS)
    gold = load_jsonl(GOLD)
    haystacks: dict[str, list[tuple[str, str]]] = {}
    for document in corpus:
        text = f"{document.get('title', '')}\n{document.get('text', '')}".lower()
        for role in ACCESS:
            if visible(document, role):
                haystacks.setdefault(role, []).append((document.get("slug", ""), text))

    assignment = assign_split(gold)
    problems: list[dict] = []
    for item in gold:
        role = item.get("role", "employee")
        keywords = [k.lower() for k in item.get("expect", {}).get("keywords", [])]
        docs = haystacks.get(role, [])
        hits = {keyword: sum(1 for _, text in docs if keyword in text) for keyword in keywords}
        answerable = bool(item.get("expect", {}).get("answerable"))
        covered = [keyword for keyword, count in hits.items() if count]
        if answerable and not covered:
            problems.append({"id": item["id"], "kind": "no keyword in any accessible document", "hits": hits})
        elif answerable and len(covered) < max(1, len(keywords) // 2):
            problems.append({"id": item["id"], "kind": "weak keyword coverage", "hits": hits})
        elif not answerable and len(covered) == len(keywords) and keywords:
            problems.append({"id": item["id"], "kind": "marked unanswerable but every keyword is present", "hits": hits})

    split = Counter(split_of(item["id"], assignment) for item in gold)
    by_category: dict[str, Counter] = {}
    for item in gold:
        by_category.setdefault(item["category"], Counter())[split_of(item["id"], assignment)] += 1

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps(
            {
                "questions": len(gold),
                "corpus_documents": len(corpus),
                "split": dict(split),
                "split_by_category": {k: dict(v) for k, v in by_category.items()},
                "problems": problems,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    DEV.write_text("".join(json.dumps(i, ensure_ascii=False) + "\n" for i in gold if split_of(i["id"], assignment) == "dev"), encoding="utf-8")
    TEST.write_text("".join(json.dumps(i, ensure_ascii=False) + "\n" for i in gold if split_of(i["id"], assignment) == "test"), encoding="utf-8")

    print(f"questions: {len(gold)}  corpus: {len(corpus)} documents")
    print(f"split: {dict(split)}")
    for category, counts in sorted(by_category.items()):
        print(f"  {category:12} dev {counts.get('dev', 0):2}  test {counts.get('test', 0):2}")
    print(f"problems: {len(problems)}")
    for problem in problems:
        print(f"  {problem['id']}: {problem['kind']} {problem['hits']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
