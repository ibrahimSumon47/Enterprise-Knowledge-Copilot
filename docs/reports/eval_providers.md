# Evaluation with the Gemini fallback

Full run of 84 questions against the deployed API, 82 scored and
2 excluded because neither provider answered.

## Headline

| Metric | Before fallback | With fallback |
| --- | --- | --- |
| Questions scored | 84 | 82 |
| hit@k | 0.29 | **0.343** |
| MRR | 0.29 | **0.343** |
| Citation precision | 0.232 | **0.28** |
| Refusal accuracy | 0.595 | **0.634** |
| p50 latency | 3280 ms | 3482 ms |
| p95 latency | 5047 ms | **24098 ms** |
| Permission leakage | 0 | **0** |

Relevant citations rose from 20 to 23, so the quality gain is small and within
run-to-run noise; the p95 regression is not.

## By provider

| Provider | Questions | hit@k | Precision | Refusal | p50 ms | p95 ms |
| --- | --- | --- | --- | --- | --- | --- |
| gemini | 37 | 0.657 | 0.622 | 0.73 | 9778 | 27310 |
| groq | 1 | 0.0 | 0.0 | 0.0 | 3441 | 3441 |
| none | 44 | 0.0 | 0.0 | 0.568 | 2396 | 4181 |

Provider counts over all 84 rows: {'gemini': 37, 'none': 46, 'groq': 1}.

**Read the `none` row carefully.** It is not a provider: those are questions the
pipeline refused at retrieval ("best match below the answer threshold") and never
sent to a model. Their hit@k is 0 by construction and their refusal accuracy is the
retrieval refusal rate, so the per-provider table compares "answered" against
"refused", not Gemini against Groq — only one question in this run actually reached
Groq before failing over.

## The p95 regression, and its cause

A quota-limited Groq does not always answer 429; sometimes it hangs. The fallback
only starts once the first call gives up, so a question could wait 45 s for Groq and
then 30 s more for Gemini. That is the 24098 ms tail and the 49 s
worst case in this run.

Mitigation shipped after this run: `GROQ_TIMEOUT_SECONDS=12`. That bounds the primary
at 12 s, but two serial attempts that both fail still cost roughly 42 s (12 + 30),
measured on eight live questions: p50 11.3 s, worst 42.3 s, 6 Gemini answers and 2
outages out of 8. The real fix is a hedged request (start the backup after a few
seconds instead of waiting for the primary to fail); that is not implemented.

## What this run does prove

- The fallback is exercised in production: 37 of 82 scored questions were answered by
  Gemini with a measurable quality signal (hit@k 0.657,
  precision 0.622).
- Excluding outages works on real data: two rows were dropped and the summary says so.
- Leakage is still exactly 0 with a second provider in the path.
