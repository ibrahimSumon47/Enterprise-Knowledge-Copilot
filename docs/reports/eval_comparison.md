# Retrieval change: hybrid only vs cross-encoder rerank

Same 84-question golden set, same deployed API, same corpus (754 documents,
12,032 chunks). The only changes were the reranker, one citation per document
and three citations instead of six.

| Metric | Before | After | Delta |
| --- | --- | --- | --- |
| Hit rate at k | 0.217 | 0.275 | +0.058 |
| Mean reciprocal rank | 0.21 | 0.275 | +0.065 |
| Citation precision | 0.173 | 0.22 | +0.047 |
| Faithfulness proxy | 1.0 | 1.0 | +0.0 |
| Refusal accuracy | 0.524 | 0.571 | +0.047 |
| p50 latency (ms) | 712 | 4404 | +3692 |
| p95 latency (ms) | 2193 | 6942 | +4749 |
| Permission leakage | 0 | 0 | +0 |

## What changed

- `BAAI/bge-small-en-v1.5` left enough headroom to load the TinyBERT
  cross-encoder again (`EKC_RERANK_ENABLED=1`), which had been off since the
  512 MB instance ran out of memory.
- Citations are deduplicated per document and capped at three, so a second
  chunk of the same page no longer takes a citation slot.
- Confidence thresholds moved to the sigmoid scale flashrank actually returns
  (answer at 0.15, high at 0.45) instead of logit values that marked a 0.14
  weak match as high confidence.

## Cost

The cross-encoder scores 40 candidates per question on a 0.1 CPU instance, so
p95 latency rose from 2.2 s to 6.9 s. That is the honest price of the precision
gain; cutting the candidate pool or the rerank length is the next lever.

> The reranked column below is the 40-candidate / 256-token run. The shipped setting is 24 / 192; see `eval_latency.md` for that run and the cost curve.
