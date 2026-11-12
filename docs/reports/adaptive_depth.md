# Adaptive rerank depth: tried, measured, reverted

Goal: score a shortlist when retrieval is already confident, so easy questions
cost less than the full pool, and keep the full pool for the hard tail.

## What was tried

1. **Branch agreement on RRF.** Score 8 candidates when the top passage looks like
   it was ranked first by both vector and full-text search (rrf >= 0.030) and sits
   clearly above fourth. Measured on live traffic: fired on **2 of 27** questions.
   Cause: `plainto_tsquery` ANDs every term, so the text branch usually returns
   nothing and RRF degrades to `1/(60+rank_v)`, which is nearly flat.
2. **Relative margin on RRF.** Same shortlist when the leader is 25% above fourth
   (rrf >= 0.016). Measured: fired on **1 of 46** questions, for the same reason —
   `1/61` vs `1/64` is a 4% gap, not a 25% one.
3. **Escalate on the reranker's own score.** Score 8, then score the remaining 16
   only when the best of the eight is below a bar.
   - Bar at high confidence (0.45): **14 of 15** questions escalated, so the
     shortlist saved nothing.
   - Bar at the refusal threshold (0.15): roughly a third of eval traffic took the
     shortlist. Quality of that configuration was **never measured**: every run
     returned `provider: none` with 0 tokens because the free Groq quota was
     exhausted, and a provider outage produces the same refusal text as a retrieval
     miss — the evaluation cannot tell them apart, so hit@k reads 0.0.

## Decision

Reverted. The deployed service is the single-pass configuration that was measured:
24 candidates at 192 tokens, hit@k 0.29, precision 0.232,
p95 5047 ms (`eval_latency.md`).

Shipping a retrieval change whose quality numbers are missing would break the
evidence rule this project runs on. The 0.15-escalation build is worth revisiting
once there is quota headroom to run 84 questions without throttling.

(a) is done: `/chat` returns `outage: true` when no model answered, the eval excludes
those rows and reports the counts, and an all-outage run exits 2 without overwriting
the published report. That was verified against a local stub, not against a healthy
provider — the free Groq quota is currently exhausted.
