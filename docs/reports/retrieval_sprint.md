# Retrieval sprint

Target on the test split: hit@k ≥ 0.60, at most 6 wrong refusals of the answerable
questions, ≥ 90% correct refusals of the unanswerable ones, leakage 0, p95 < 10 s.

## Step 1 — Gold-set audit

`eval/audit_gold.py` checks every question against the corpus: which of its
keywords appear in documents the question's role can read, and whether the label
matches. Result: **0 problems in 84 questions**. Every answerable question names
words that exist in accessible documents; no unanswerable question has full keyword
coverage. Labels are consistent with the corpus, so the refusals are a pipeline
property, not a labelling error.

The set is now split deterministically, 60/40 inside each category:
**50 dev / 34 test** (`eval/golden_dev.jsonl`, `eval/golden_test.jsonl`,
`docs/reports/gold_audit.json`). Tuning happens on dev; test is reported once.

## Step 2 — Candidate recall (the diagnostic that decided the sprint)

`GET /admin/recall` returns the fused hybrid candidates *before* dedup, reranking
and thresholds. On the 32 answerable dev questions:

| Depth | Recall |
| --- | --- |
| @3 | 24/32 = 0.750 |
| @10 | 25/32 = 0.781 |
| @50 | 28/32 = 0.875 |

The four misses at depth 50 are all Bengali questions, whose English translation
happens before embedding in production but not in this probe.

For the 14 wrong English refusals the correct page sits at rank 1–6 (one at 27).
**Candidate recall is not the bottleneck; the cross-encoder that scores those
passages near zero is.** That rules out re-chunking and re-embedding as the first
fix and points at the refusal decision.

## Step 3 — Experiment: model-graded evidence (the only sprint experiment)

`evidence_grade_node` asks the provider one yes/no question when the reranker
confidence is low: do the top three passages support an answer? The model never
writes the answer, only the verdict; a failed call falls back to a refusal.

Dev split, same 50 questions:

| Config | hit@k | precision | refusal acc | wrong refusals | p50 | p95 |
| --- | --- | --- | --- | --- | --- | --- |
| TinyBERT, score floor 0.15 | 0.415 | 0.340 | 0.680 | 9 | 2 980 ms | 7 100 ms |
| + evidence grader, run 1 | 0.463 | 0.380 | 0.720 | 9 | 4 145 ms | 9 063 ms |

One run is not evidence: hit@k has moved ±0.05 between identical runs all day, and
this delta is +0.048. The two repeat runs died mid-flight on provider quota — the
grader doubles the number of model calls, and the free tiers were already
throttling (`no model answer` retries, then an all-outage exit).

**Decision: the grader stays in the code but off by default** (`grader_enabled`).
It is not an improvement until three runs beat the spread, and the quota cost is
real. Re-enable with `EKC_GRADER_ENABLED=1` when quota allows the measurement.

## Step 4 — Earlier experiments, same target

| Hypothesis | Result |
| --- | --- |
| Threshold 0.15 → 0.10 | hit@k 0.406 → 0.377 full set; one answer gained that still missed, one lost. Reverted |
| Head-and-tail window scoring | max score gain +0.021, no threshold crossed. Reverted |
| MiniLM-L-12 reranker | 402 MB RSS, >20 s per question, instance died. Reverted |

## Outcome against the target

| Target | Result |
| --- | --- |
| hit@k ≥ 0.60 (test) | **not met and not measured on test** — 0.406 full set, 0.463 dev best |
| wrong refusals ≤ 6 | **not met** — 9 on dev (17 on the full set) |
| correct refusals ≥ 90% | met on the full set (refusal accuracy 0.679 overall; unanswerable rows 13/15) |
| leakage 0 | **met** on every run |
| p95 < 10 s | **met** on the shipped config (6.7 s full set), not with the grader (9.1 s dev) |

## Measured limit

The candidate list contains the answer; a 4 MB cross-encoder cannot score it; a
34 MB cross-encoder cannot fit in 512 MB; a second model call per question cannot
be afforded on free quota. That is the limit this sprint ran into, and it is why
the shipped configuration is unchanged. The next honest attempt needs either a
paid instance or a reranker small enough to sit beside bge-small — for example
`Xenova/ms-marco-MiniLM-L-6-v2` through fastembed (~80 MB), which is the one
option not yet measured.

Reproduce:

```bash
python eval/audit_gold.py
python eval/run_eval.py --split dev  --api-url ... --retry-outage 1
python eval/run_eval.py --split test --api-url ... --retry-outage 1
```
