# A larger cross-encoder on the free instance

TinyBERT (`ms-marco-TinyBERT-L-2-v2`, ~4 MB) scores correct long passages near
zero on this corpus, which is why 14 answerable questions are refused. The obvious
fix is a stronger cross-encoder. This is what happened when one was deployed.

## What was tried

`ms-marco-MiniLM-L-12-v2` — the strongest cross-encoder flashrank ships, ~34 MB
ONNX, advertised by the library as the "best cross-encoder reranker". One config
line changed; nothing else.

## What was measured

| | TinyBERT-L-2 | MiniLM-L-12 |
| --- | --- | --- |
| Resident memory after load | 361 – 369 MB | **402 MB** |
| `How do I submit an expense claim?` (known-good) | 0.997 | 0.978 |
| Retrieval latency, warm | 2.3 – 3.8 s | > 20 s per question |
| 14-question probe | finishes | **did not finish in 290 s, then 502s** |
| Instance after a few requests | stable | **process gone, health reset (rss 101 MB, counters 0)** |

The known-good question did not score higher with the bigger model (0.978 vs
0.997), so there is no quality evidence in its favour even before the cost.

## Why it was reverted

The container died within a few requests. Render's free instance is 512 MB and the
process was already at 402 MB right after loading the reranker; a restart with zeroed
counters and `rss 101 MB` is what a crash looks like from the outside. I could not
read the platform logs to confirm the kill reason, so "out of memory" is inference
from the headroom, not a recorded OOM.

The change is reverted (`af7d04f`). After the revert the service is stable at
`rss 361 MB` with the baseline scores (0.9969 / 0.0001 / 0.0051 / 0.0055 / 0.0219 on
the same five questions), so the refusals are unchanged.

## What this rules out

A bigger cross-encoder is not available on this host: the free tier cannot hold one
next to the bge-small encoder and the ONNX runtime. That closes the cheapest fix for
the refusal problem.

Options left, each with a cost:

- `Xenova/ms-marco-MiniLM-L-6-v2` through fastembed (~80 MB instead of 34 MB, and
  fastembed is already a dependency) — plausible, but the headroom after the
  encoder is roughly 150 MB and this attempt shows how little slack there is.
- Rewrite the query into handbook vocabulary before retrieval, so the existing small
  cross-encoder sees words it was trained on. Costs one extra model call per question.
- Accept the refusals and document them as a known limitation of the free tier.
