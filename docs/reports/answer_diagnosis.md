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

## Slice 1: the pre-model refusals

Measured on the deployed API with `all_candidates=true` for every test question.
None of the 34 questions returns zero candidates, so the access predicate, the
translation step and query length are not the cause. The cause is the score floor:
these 19 questions have a top rerank score below the old 0.01 threshold, the
pipeline marked them low confidence, and with the grader disabled it refused before
any model call. The 16 refusals in the report are the subset that was counted that
run; the same mechanism covers 19.

| id | role | answerable | own candidates | own all_candidates | admin all_candidates | top rerank |
| --- | --- | --- | --- | --- | --- | --- |
| a22 | finance | yes | 3 | 10 | 12 | 0.00510 |
| a24 | employee | yes | 3 | 6 | 9 | 0.00307 |
| a27 | employee | yes | 3 | 21 | 21 | 0.00748 |
| a28 | security | yes | 3 | 8 | 12 | 0.00008 |
| a29 | employee | yes | 3 | 12 | 12 | 0.00211 |
| u10 | employee | no | 3 | 15 | 13 | 0.00004 |
| u11 | employee | no | 3 | 21 | 21 | 0.00005 |
| u12 | employee | no | 3 | 16 | 16 | 0.00307 |
| u15 | employee | no | 3 | 10 | 13 | 0.00013 |
| b08 | finance | yes | 3 | 19 | 13 | 0.00003 |
| b09 | employee | yes | 3 | 19 | 11 | 0.00003 |
| b10 | employee | yes | 3 | 19 | 13 | 0.00002 |
| b11 | employee | yes | 3 | 15 | 13 | 0.00002 |
| b12 | guest | no | 3 | 19 | 11 | 0.00003 |
| x10 | guest | no | 3 | 13 | 17 | 0.00073 |
| x11 | employee | no | 3 | 14 | 21 | 0.00030 |
| x12 | employee | no | 3 | 17 | 19 | 0.00035 |
| x14 | hr | no | 3 | 12 | 19 | 0.00010 |
| x15 | employee | no | 3 | 14 | 21 | 0.00055 |

Evidence for the named causes:

- **Access predicate:** not the cause. Every question returns 3 default candidates and 6–21 with `all_candidates=true`; the admin role also returns 6–21.
- **Empty retrieval:** not the cause. Zero questions have empty candidate lists.
- **Timeout / translation:** not the cause. These counts come from the retrieval-only endpoint, which does no model and no translation call.
- **Query too short:** not the cause. `classify()` only marks a question unclear below two words; none of these are.
- **Score floor:** the cause. All 19 rows are below 0.01, and the refusal path was `grade -> evidence_grade (grader disabled) -> refuse`.

Fix: `route_after_grade` sends every non-empty candidate set to the grounded call; the score floor only guards the no-candidate case. Regression test: `test_low_scores_still_reach_the_model_when_the_grader_is_off`.
