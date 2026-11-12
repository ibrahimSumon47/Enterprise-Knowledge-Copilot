# Why questions get refused

The last full run refused 42 of 84 questions. That number is not one failure:
25 are the refusals the golden set expects and 17 are questions the set marks
answerable.

| Group (non-Bengali probes) | Questions | Top rerank score |
| --- | --- | --- |
| Answered, expected answerable | 27 | 0.296 – 0.999 (median 0.961) |
| Refused, expected answerable (the bug) | 14 | 0.000 – 0.141 (median 0.004) |
| Refused, expected refusal (correct) | 30 | 0.000 – 0.988 (median 0.001) |

## Is the 0.15 threshold too strict?

Marginally, and not in the way the count suggests. The 14 non-Bengali false
refusals are not spread over the gap, they are piled at the bottom:

| Band | What sits there |
| --- | --- |
| 0.000 – 0.025 | 13 false refusals |
| 0.141 | 1 false refusal (a18) |
| 0.268 – 0.276 | 2 questions that should be refused |
| 0.296 – 0.999 | every question that is answered |

Questions the set expects to be refused score in the same range: 24 of 31 are below 0.05. No cut can separate those from the 13
false refusals, so the threshold is not what breaks them — the cross-encoder is.

What the cut does cost is small and measurable: lowering it to 0.10 recovers
exactly one question (a18 at 0.141) and admits nothing that should be refused.
Lowering it to 0.03 recovers one more (m03 at 0.025) but starts admitting the
near-zero matches the correct refusals depend on.

The refusals trace to the score itself, not the cut. Example:
`What is the deadline for submitting receipts?` retrieves the right page
(`Faq · When do I submit my final reimbursement…`) at rank 1 with RRF 0.016,
and the cross-encoder scores it **0.0001**. The same reranker gives
`How do I submit an expense claim?` — a near-identical intent — 0.997 on a
short chunk. Long chunks, truncated at 192 tokens, lose the sentence that
answers the question, and the score collapses.

6 questions that should be refused score above 0.15
(0.268 – 0.988), so the threshold is not a safe proxy for confidentiality
either; the SQL predicate and the citation verifier hold that line, and leakage
stayed 0.

## What the audit log says

Across the last 80 chat audit entries (61 refusals): 51 were
`best match below the answer threshold` and 10 were `model declined to answer`.
The model never saw the 51; they never reached it.

## Caveats

`/admin/retrieval` calls retrieval directly, so Bengali questions bypass the
pipeline's query translation and score 0.000 against English chunks. Their 12
rows are excluded from the bands above; the three Bengali false refusals need
their own investigation.

Scores are from one probe of each question, not averaged over repeats.
