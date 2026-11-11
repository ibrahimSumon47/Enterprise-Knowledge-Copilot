#!/usr/bin/env python3
"""Build the corpus slice from the public GitLab Handbook plus synthetic documents.

Run after cloning the handbook into .corpus-src/handbook (see docs/RUNBOOK.md).
Output: data/corpus.jsonl and data/corpus_manifest.json.

Access labels are assigned by this project to demonstrate access control; the
handbook itself is public. Synthetic documents are invented and labelled.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HANDBOOK = ROOT / ".corpus-src" / "handbook"
OUT_JSONL = ROOT / "data" / "corpus.jsonl"
OUT_MANIFEST = ROOT / "data" / "corpus_manifest.json"

SECTIONS = ["engineering", "security", "people-group", "finance", "legal"]
TARGET_DOCS = 800
MIN_BYTES = 1200
MAX_BYTES = 45_000
RAW_BASE = "https://gitlab.com/gitlab-com/content-sites/handbook/-/blob/main"

SYNTHETIC = [
    {
        "slug": "synthetic/salary-bands-engineering",
        "title": "Engineering salary bands (synthetic)",
        "department": "engineering",
        "text": """# Engineering salary bands (SYNTHETIC)

> This document is invented for this portfolio project. It is not GitLab policy.

## Bands

| Level | Band (USD, annual) | Equity refresh |
| --- | --- | --- |
| Engineer | 92,000 - 118,000 | 8,000 |
| Senior Engineer | 128,000 - 156,000 | 14,000 |
| Staff Engineer | 168,000 - 205,000 | 22,000 |

## Notes

Bands are reviewed every twelve months. Offers above the top of a band need
written approval from the engineering director and a people partner.
""",
    },
    {
        "slug": "synthetic/salary-bands-people",
        "title": "Compensation review calendar (synthetic)",
        "department": "people",
        "text": """# Compensation review calendar (SYNTHETIC)

> Invented content for the access-control showcase.

## Calendar

- February: market data refresh, bands published to people partners only.
- April: promotion cycle decisions, effective 1 May.
- October: retention review for Staff and above.

## Restrictions

Individual compensation letters are stored in the people system, never in the
handbook. People partners may discuss band placement; they may not share another
employee's numbers.
""",
    },
    {
        "slug": "synthetic/incident-postmortem-payments",
        "title": "Post-mortem: payment retry storm (synthetic)",
        "department": "engineering",
        "text": """# Post-mortem: payment retry storm (SYNTHETIC)

> Invented post-mortem used to test confidential-document handling.

## Summary

A retry loop in the dunning worker multiplied charge attempts by 40 for two hours
on 3 March. No customer was charged twice; 1,912 charges were attempted twice and
the duplicates were voided automatically.

## Root cause

The retry budget was keyed on invoice id instead of charge id, so two workers
retried the same charge in parallel.

## Follow-ups

- Retry budget keyed on charge id (shipped 6 March).
- Alert on attempt-to-charge ratio above 3 within five minutes.
- Load test the dunning worker with duplicated messages.
""",
    },
    {
        "slug": "synthetic/incident-postmortem-auth",
        "title": "Post-mortem: session revocation delay (synthetic)",
        "department": "security",
        "text": """# Post-mortem: session revocation delay (SYNTHETIC)

> Invented security post-mortem.

## Summary

After a user was removed from a team, their existing session stayed valid for up
to 55 minutes because revocation was only checked at token refresh.

## Root cause

Access checks were cached in the edge layer with a one hour TTL and no
invalidation hook on membership change.

## Follow-ups

- Membership change publishes an invalidation event (done).
- Reduce edge cache TTL for access decisions to 60 seconds.
- Add a synthetic test that removes access and asserts denial within two minutes.
""",
    },
    {
        "slug": "synthetic/vendor-security-review",
        "title": "Vendor security review record (synthetic)",
        "department": "security",
        "text": """# Vendor security review (SYNTHETIC)

## Vendor

Northwind Analytics — log enrichment.

## Data touched

Hashed user ids, request paths, response times. No message bodies, no email
addresses.

## Findings

1. SOC 2 Type II report is 14 months old; refreshed report requested.
2. Data processing agreement missing the deletion SLA; legal to amend.
3. Sub-processor list included two providers not disclosed initially.

## Decision

Approved with conditions: no message content, 30-day retention cap, quarterly
review. Re-review in six months.
""",
    },
    {
        "slug": "synthetic/finance-forecast-fy27",
        "title": "FY27 operating plan extract (synthetic)",
        "department": "finance",
        "text": """# FY27 operating plan extract (SYNTHETIC)

## Headcount

Plan grows from 410 to 468 full-time equivalents, weighted to engineering (38)
and support (12). Contractor spend is flat.

## Spend

| Category | FY27 plan | Change |
| --- | --- | --- |
| Payroll | 41.2M | +11% |
| Cloud infrastructure | 6.8M | +18% |
| Vendors | 3.1M | -4% |

## Assumptions

Renewal rate 91%, average seat price +3%, cloud unit cost -6% from committed use.
""",
    },
    {
        "slug": "synthetic/legal-hold-procedure",
        "title": "Legal hold procedure (synthetic)",
        "department": "people",
        "text": """# Legal hold procedure (SYNTHETIC)

## When a hold applies

A hold starts when counsel sends a preservation notice. It covers email, chat,
tickets and repository history for the named custodians.

## Steps

1. Counsel records the matter id and custodians in the register.
2. IT freezes mailbox export and chat retention for those custodians.
3. Custodians are told not to delete material and not to discuss the matter.
4. The hold is released only by written notice from counsel.

## Records

Hold register entries are kept for seven years after release.
""",
    },
    {
        "slug": "synthetic/security-incident-response",
        "title": "Security incident severity matrix (synthetic)",
        "department": "security",
        "text": """# Security incident severity matrix (SYNTHETIC)

| Severity | Example | First response | Update cadence |
| --- | --- | --- | --- |
| SEV1 | Confirmed data exfiltration | 15 minutes | every 30 minutes |
| SEV2 | Privilege escalation attempt | 1 hour | every 2 hours |
| SEV3 | Single-account takeover | 4 hours | daily |
| SEV4 | Misconfiguration without exposure | next business day | weekly |

Severity is set by the on-call security engineer and can be raised by any
incident commander. Customer notification for SEV1 happens within 72 hours of
confirmation.
""",
    },
    {
        "slug": "synthetic/engineering-oncall-compensation",
        "title": "On-call compensation policy (synthetic)",
        "department": "engineering",
        "text": """# On-call compensation (SYNTHETIC)

## Allowance

Engineers on primary on-call receive a weekly allowance of 350 USD. Secondary
on-call receives 120 USD. Both are paid through payroll with the next cycle.

## Time off in lieu

A page that requires work between 22:00 and 06:00 local time earns four hours of
time off in lieu, capped at eight hours per week.

## Exclusions

Scheduled maintenance windows do not earn the allowance unless the engineer is
the named responder.
""",
    },
    {
        "slug": "synthetic/people-performance-process",
        "title": "Performance improvement process (synthetic)",
        "department": "people",
        "text": """# Performance improvement process (SYNTHETIC)

## Scope

Applies when expectations have not been met for two consecutive review periods
despite documented coaching.

## Steps

1. People partner and manager agree on three measurable outcomes.
2. Written plan shared with the employee, 30 to 60 days.
3. Weekly check-ins recorded in the people system.
4. Decision at the end: close, extend once, or exit.

## Confidentiality

Plans are visible to the employee, their manager, the people partner and the
department director. They are never stored in shared drives.
""",
    },
    {
        "slug": "synthetic/finance-travel-limits",
        "title": "Travel and expense limits (synthetic)",
        "department": "finance",
        "text": """# Travel and expense limits (SYNTHETIC)

| Region | Flight class | Hotel per night | Meals per day |
| --- | --- | --- | --- |
| North America | economy, premium over 6h | 260 USD | 75 USD |
| Europe | economy, premium over 6h | 220 EUR | 65 EUR |
| Asia Pacific | economy, business over 8h | 200 USD | 55 USD |

Receipts are required above 25 USD. Expenses submitted later than 45 days need
controller approval. Alcohol is not reimbursable.
""",
    },
    {
        "slug": "synthetic/security-key-management",
        "title": "Production key management standard (synthetic)",
        "department": "security",
        "text": """# Production key management standard (SYNTHETIC)

## Requirements

- All production secrets live in the platform secret store, never in images.
- Service credentials rotate every 90 days; database passwords every 180 days.
- Human access to production secrets requires a break-glass approval recorded in
  the audit log.
- Keys used by CI are scoped to a single repository and expire after 90 days.

## Prohibited

Printing secrets to build logs, storing them in environment files committed to
git, and sharing credentials over chat.
""",
    },
]


def slugify(path: Path) -> str:
    rel = path.relative_to(HANDBOOK)
    slug = re.sub(r"[^a-z0-9]+", "-", str(rel.with_suffix("")).lower()).strip("-")
    return slug[:120]


def title_of(text: str, path: Path) -> str:
    for line in text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()[:160]
    return path.stem.replace("-", " ").replace("_", " ").title()


def access_for(path: Path) -> tuple[str, str | None]:
    """Assign a demo access label from the path. Honest: the source is public."""
    parts = list(path.parts)
    # The checkout nests content twice (repo dir and content dir both named
    # "handbook"), so the section is the part after the last "handbook".
    section = ""
    for index in range(len(parts) - 1, -1, -1):
        if parts[index] == "handbook":
            section = parts[index + 1] if index + 1 < len(parts) else ""
            break
    lowered = str(path).lower()

    if section == "security":
        return ("department", "security")
    if section == "finance":
        return ("department", "finance")
    if section == "people-group" and any(k in lowered for k in ("compensation", "pay", "promotion")):
        return ("department", "people")
    if section == "engineering" and any(k in lowered for k in ("infrastructure", "infra", "on-call")):
        return ("department", "engineering")
    if any(k in lowered for k in ("handbook", "onboarding", "values", "communication")):
        return ("public", None)
    return ("employee", None)


SECTION_QUOTA = {
    "engineering": 420,
    "security": 190,
    "people-group": 110,
    "finance": 50,
    "legal": 30,
}


def collect(limit: int) -> list[dict]:
    if not HANDBOOK.exists():
        raise SystemExit(
            "Handbook checkout missing. Run: see docs/RUNBOOK.md corpus fetch step."
        )

    docs: list[dict] = []
    for section in SECTIONS:
        quota = min(SECTION_QUOTA.get(section, limit), limit - len(docs))
        if quota <= 0:
            break
        taken = 0
        for path in sorted((HANDBOOK / "content" / "handbook" / section).rglob("*.md")):
            if taken >= quota:
                break
            try:
                raw = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            body = re.sub(r"^---\n.*?\n---\n", "", raw, flags=re.S)
            size = len(body.encode("utf-8"))
            if size < MIN_BYTES or size > MAX_BYTES:
                continue
            if "{{" in body[:400] and "}}" in body[:400]:
                continue
            rel = path.relative_to(HANDBOOK)
            access, department = access_for(path)
            digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
            taken += 1
            docs.append(
                {
                    "slug": slugify(path),
                    "title": title_of(body, path),
                    "source_url": f"{RAW_BASE}/{rel.as_posix()}",
                    "license": "CC BY-SA 4.0",
                    "attribution": "GitLab Handbook",
                    "access_level": access,
                    "department": department,
                    "is_synthetic": False,
                    "content_hash": digest,
                    "text": body,
                }
            )
    return docs


def build(limit: int) -> None:
    docs = collect(limit)
    for item in SYNTHETIC:
        digest = hashlib.sha256(item["text"].encode("utf-8")).hexdigest()
        docs.append(
            {
                "slug": item["slug"],
                "title": item["title"],
                "source_url": None,
                "license": "Project-authored (synthetic)",
                "attribution": "Synthetic document created for this portfolio project",
                "access_level": "confidential",
                "department": item["department"],
                "is_synthetic": True,
                "content_hash": digest,
                "text": item["text"],
            }
        )

    OUT_JSONL.parent.mkdir(parents=True, exist_ok=True)
    with OUT_JSONL.open("w", encoding="utf-8") as handle:
        for doc in docs:
            handle.write(json.dumps(doc, ensure_ascii=False) + "\n")

    by_level: dict[str, int] = {}
    by_dept: dict[str, int] = {}
    for doc in docs:
        by_level[doc["access_level"]] = by_level.get(doc["access_level"], 0) + 1
        if doc["department"]:
            by_dept[doc["department"]] = by_dept.get(doc["department"], 0) + 1

    manifest = {
        "documents": len(docs),
        "synthetic": sum(1 for d in docs if d["is_synthetic"]),
        "by_access_level": by_level,
        "by_department": by_dept,
        "words": sum(len(d["text"].split()) for d in docs),
        "source": "GitLab Handbook (public, CC BY-SA 4.0)",
        "notice": "Access labels are assigned by this project to demonstrate access control.",
    }
    OUT_MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=TARGET_DOCS)
    args = parser.parse_args()
    build(args.limit)
