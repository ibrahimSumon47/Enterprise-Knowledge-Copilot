# Why questions get refused

The last full run refused 42 of 84 questions. That number is not one failure:
25 are the refusals the golden set expects and 17 are questions the set marks
answerable.

| Group | Questions | Top rerank score |
| --- | --- | --- |
| Answered, expected answerable | 36 | 0.000 – 0.999 (median 0.888) |
| Refused, expected answerable (the bug) | 16 | 0.000 – 0.141 (median 0.003) |
| Refused, expected refusal (correct) | 31 | 0.000 – 0.988 (median 0.001) |

## Is the 0.15 threshold too strict?

No. Among the 83 questions probed through `/admin/retrieval`, no score falls
between 0.141 and 0.296. The threshold sits in an empty band: dropping it to 0.10
changes nothing, and dropping it to 0.02 would admit the near-zero matches that
the correct refusals depend on while recovering at most one or two questions.

The refusals trace to the score itself, not the cut. Example:
`What is the deadline for submitting receipts?` retrieves the right page
(`Faq · When do I submit my final reimbursement…`) at rank 1 with RRF 0.016,
and the cross-encoder scores it **0.0001**. The same reranker gives
`How do I submit an expense claim?` — a near-identical intent — 0.997 on a
short chunk. Long chunks, truncated at 192 tokens, lose the sentence that
answers the question, and the score collapses.

Six questions that should be refused score above 0.15 (0.268 – 0.988), so the
threshold is also not a safe proxy for confidentiality; the SQL predicate and the
citation verifier are what actually hold that line, and leakage stayed 0.

## What the audit log says

Across the last 80 chat audit entries (61 refusals): 51 were
`best match below the answer threshold` and 10 were `model declined to answer`.
The model never saw the 51; they never reached it.

## Caveats

`/admin/retrieval` calls retrieval directly, so Bengali questions bypass the
pipeline's query translation and score 0.000 against English chunks. Their numbers
here are an artefact; the three Bengali false refusals need their own investigation.

Scores are from one probe of each question, not averaged over repeats.
