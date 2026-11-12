# Model-free retrieval evaluation

Date: 2026-11-12. Endpoint: `/admin/retrieval?all_candidates=true` on the deployed
API. No language model is called: the endpoint embeds the question, runs the hybrid
SQL, reranks with the local TinyBERT cross-encoder and returns every scored passage.
`eval/retrieval_eval.py` turns those passages into ranking and refusal metrics.

This exists because the free LLM quota is the bottleneck for `eval/run_eval.py`.
Ranking quality and the refusal threshold are measurable without a single token.

## What each configuration means

| Name | Order | Refusal score |
| --- | --- | --- |
| `fused` | reciprocal-rank fusion only, no cross-encoder | n/a (RRF scale) |
| `rerank` | TinyBERT cross-encoder score | reranker score |
| `blend-0.5/1.0/2.0` | min-max normalised RRF + weight × reranker | blended score, normalised to 0..1 |

`hit@k` counts a question as a hit when the first passage whose title, heading or
snippet contains the label's keyword appears in the top k. `recall@k` over
documents is the same number here because passages are deduplicated per document.

## Dev split, 50 questions (32 answerable, 18 unanswerable), 3 passes

Mean ± spread over the three passes. Spread is 0.000 everywhere: retrieval is
deterministic, so the run-to-run spread belongs to the model, not to ranking.

| Config | hit@3 | hit@10 | MRR | answer rate @0.15 | unanswerable refused | AUC |
| --- | --- | --- | --- | --- | --- | --- |
| fused | 0.688 ± 0.000 | 0.719 ± 0.000 | 0.601 ± 0.000 | n/a | n/a | n/a |
| rerank | 0.688 ± 0.000 | 0.781 ± 0.000 | 0.686 ± 0.000 | 0.438 | 0.833 | 0.667 |
| blend-0.5 | 0.719 ± 0.000 | 0.719 ± 0.000 | 0.652 ± 0.000 | 1.000 | 0.056 | 0.560 |
| blend-1.0 | 0.688 ± 0.000 | 0.719 ± 0.000 | 0.669 ± 0.000 | 1.000 | 0.056 | 0.563 |
| blend-2.0 | 0.688 ± 0.000 | 0.719 ± 0.000 | 0.669 ± 0.000 | 1.000 | 0.056 | 0.565 |

## Test split, 34 questions (21 answerable, 13 unanswerable), 3 passes

| Config | hit@3 | hit@10 | MRR | answer rate @0.15 | unanswerable refused | AUC |
| --- | --- | --- | --- | --- | --- | --- |
| fused | 0.857 ± 0.000 | 0.857 ± 0.000 | 0.833 ± 0.000 | n/a | n/a | n/a |
| rerank | 0.857 ± 0.000 | 0.857 ± 0.000 | 0.809 ± 0.000 | 0.476 | 0.846 | 0.687 |
| blend-0.5 | 0.857 ± 0.000 | 0.857 ± 0.000 | 0.833 ± 0.000 | 1.000 | 0.000 | 0.593 |
| blend-1.0 | 0.857 ± 0.000 | 0.857 ± 0.000 | 0.809 ± 0.000 | 1.000 | 0.000 | 0.597 |
| blend-2.0 | 0.857 ± 0.000 | 0.857 ± 0.000 | 0.809 ± 0.000 | 1.000 | 0.000 | 0.597 |

Dev chose the configuration, test confirmed it once: the cross-encoder improves
MRR and hit@10 on dev (0.601 → 0.686, 0.719 → 0.781) and ties on test; blending
never beats it on ordering and separates answerable from unanswerable worse
(AUC 0.56–0.60 versus 0.69). The deployed configuration stays fused retrieval +
TinyBERT rerank, and the blend is not used.

## Refusal calibration on dev

Threshold sweep over the reranker score (32 answerable, 18 unanswerable):

| Threshold | Wrong refusals (of 32) | Unanswerable refused | Refusal precision |
| --- | --- | --- | --- |
| 0.04 | 16.0 | 0.778 | 0.467 |
| 0.12 | 17.0 | 0.833 | 0.469 |
| **0.15 (deployed)** | **18.0** | **0.833** | **0.467** |
| 0.28 | 19.0 | 0.944 | 0.472 |

No threshold meets both targets. A threshold high enough to refuse 90% of the
unanswerable questions refuses 19 of 32 answerable ones; a threshold low enough
to refuse only six refuses most of the unanswerable questions too. The cause is
the separation itself: AUC 0.667 on dev and 0.687 on test, i.e. the top reranker
score overlaps heavily between the two classes. Ordering is not the problem —
hit@3 is 0.857 on test — the refusal decision is.

The configured 0.15 stays. It is the point in the sweep where the refusal
precision stops improving, and moving it either way trades one target for the
other. The evidence grader in `api/app/pipeline.py` is the lever that could
separate the classes, and it is off by default because it doubles model calls.

## Targets against the test split

| Target | Result | Verdict |
| --- | --- | --- |
| hit@k ≥ 0.60 | retrieval hit@3 0.857 | met (model-free) |
| wrong refusals ≤ 6 of the answerable questions | 10.0 of 21 at 0.15 | **missed — measured limit** |
| ≥ 90% of unanswerable refused | 0.846 | **missed — measured limit** |
| leakage exactly 0 | 0 in the last full end-to-end run | met |
| p95 < 10 s | 6 687 ms (last full run, 84 questions) | met |

The end-to-end `hit@k` (answer text against the label) is still the 0.406 of the
last full run; these numbers explain where it is lost. Retrieval puts the right
document first 85.7% of the time on test, and the refusal policy then throws away
about half of the answerable questions before the model ever sees them.

## Reproduce

```bash
python eval/retrieval_eval.py --split dev --repeat 3 \
  --api-url https://enterprise-knowledge-copilot-2u57.onrender.com \
  --supabase-url https://ctfatevadhojxycuplsh.supabase.co \
  --anon-key "$ANON" --password "$EKC_DEMO_PASSWORD"
```

Raw output: `docs/reports/retrieval_eval.json` (last run), plus the per-split
passes in `.tmp/` during development.
