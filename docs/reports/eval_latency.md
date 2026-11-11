# Rerank cost: 40 candidates / 256 tokens vs 24 / 96

Same 84-question set, same corpus, same reranker. Only the per-question work
changed: the candidate pool and how much text the cross-encoder reads.

| Metric | 40 / 256 | 24 / 96 | Delta |
| --- | --- | --- | --- |
| Hit rate at k | 0.275 | 0.203 | -0.072 |
| Mean reciprocal rank | 0.275 | 0.203 | -0.072 |
| Citation precision | 0.22 | 0.167 | -0.053 |
| Faithfulness proxy | 1.0 | 1.0 | +0.0 |
| Refusal accuracy | 0.571 | 0.536 | -0.035 |
| p50 latency (ms) | 4404 | 1858 | -2546 |
| p95 latency (ms) | 6942 | 3819 | -3123 |
| Permission leakage | 0 | 0 | +0 |

## Reading it

p95 moved from 6942 ms to 3819 ms while hit@k
went 0.275 -> 0.203 and citation precision 0.22 -> 0.167.
Leakage stays 0 because the access predicate is in SQL, not in the reranker.
