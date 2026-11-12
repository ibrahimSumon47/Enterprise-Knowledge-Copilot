# Rerank cost curve

Same 84 questions, same corpus, same reranker. Only the per-question work
changed: candidates scored, tokens the cross-encoder reads, characters sent
to it. The middle row is the over-correction that lost hit@k; the last row is
the shipped setting.

| Candidates / tokens / chars | hit@k | MRR | Precision | Refusal | p50 ms | p95 ms | Leakage |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 40 / 256 / 2000 | 0.275 | 0.275 | 0.22 | 0.571 | 4404 | 6942 | 0 |
| 24 / 96 / 900 | 0.203 | 0.203 | 0.167 | 0.536 | 1858 | 3819 | 0 |
| 24 / 192 / 1400 | 0.29 | 0.29 | 0.232 | 0.595 | 3280 | 5047 | 0 |

## Reading it

Cutting the token window to 96 was the wrong lever: it saved ~3.1 s of p95 but
dropped hit@k to 0.203, because the answer sentence often sits in the
second half of a passage. Widening it back to 192 recovered the quality and kept
most of the saving: p95 6942 ms -> 5047 ms (-27%), p50 4404 ms -> 3280 ms.

hit@k 0.275 -> 0.29 and precision 0.22 -> 0.232 are within run-to-run noise on 84 questions, so the honest
claim is **no measurable precision loss**, not a gain.

## Why 2 s is out of reach with the reranker on

The fixed cost is the LLM round trip plus encode and search (~1.2 s at p50 on a
0.1 CPU instance); the cross-encoder is the rest. Reaching p95 <= 3 s would need
the pool near 8 candidates, which is where quality goes with it. The alternative
is `EKC_RERANK_ENABLED=0`: p95 back to ~2.2 s, hit@k back to ~0.22. The shipped
default buys ~0.07 hit@k for ~2.9 s of p95; that is a product call, not a bug.
