# Answer diagnosis

## The metric changed, the retrieval did not

`run_eval.py` used to score hit@k from retrieval ranks. It now scores it from the
**answer's citations** (`score()` builds `flags` from `response["citations"]` and
`summary["hit@k"]` averages that flag). An answer that cites one passage gets one
chance instead of fifty. That is why the same retrieval that scored 0.86 earlier
now reports 0.04–0.07: the number is a citation hit rate, not a retrieval hit rate.

Citation precision is the same measure restricted to cited passages, so the two
numbers now move together and neither describes recall. Restoring a true retrieval
hit@k needs the retrieved document ids from the API, which `/chat` does not return;
`eval/diagnose.py` records what is observable today.

## Refusal groups, test split (`--cache-tag product-v2`)

| Group | Count |
| --- | --- |
| Provider `none` (refused before a model call: floor or no candidates) | 16 / 34 |
| Provider `groq` (a model answered) | 18 / 34 |
| Refusal accuracy | 0.412 |
| Permission leakage | 0 |

The 16 pre-model refusals are the largest group. The floor is now 0.0, so those
questions reach the model. A re-run after that change (cache tag `product-v3`)
scored refusal accuracy 0.441, hit@k 0.071 and p95 4 856 ms, so the floor was not
the whole cause; the remaining refusals come from the model's answerability call
and from citation checks.

## What to fix next

1. Return the retrieved candidate ids and ranks from `/chat` (an admin-only debug
   field) so hit@k can be measured from retrieval again.
2. Pass 6–8 passages to the grounded call instead of the current truncation, then
   measure whether the model stops calling answerable questions unanswerable.
3. Treat a provider failure as `temporarily_unavailable`, never as a refusal with
   no citations, and retry across Groq and Gemini.
