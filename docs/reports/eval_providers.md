# Provider fallback and hedged requests

Three full runs of the same 84-question set against the deployed API.

| Run | Scored | hit@k | Precision | Refusal | p50 | p95 | Leakage |
| --- | --- | --- | --- | --- | --- | --- | --- |
| No working fallback | 84 | 0.29 | 0.232 | 0.595 | 3280 ms | 5047 ms | 0 |
| Gemini fallback, serial | 82 | 0.343 | 0.28 | 0.634 | 3482 ms | 24098 ms | 0 |
| Gemini fallback, hedged | 84 | **0.391** | **0.317** | **0.667** | **3541 ms** | **9963 ms** | **0** |

The middle run exposes the cost of waiting: a hung primary kept the whole budget, so
p95 reached 24098 ms and two questions timed out entirely. Starting the
backup on a three-second timer instead brought p95 down to 9963 ms
(-59%),
and every question in the last run got an answer.

## By provider (hedged run)

| Provider | Questions | hit@k | Precision | Refusal | p50 ms | p95 ms |
| --- | --- | --- | --- | --- | --- | --- |
| gemini | 41 | 0.675 | 0.65 | 0.732 | 4828 | 10449 |
| groq | 1 | 0.0 | 0.0 | 1.0 | 4940 | 4940 |
| none | 42 | 0.0 | 0.0 | 0.595 | 2432 | 3431 |

`none` is not a provider: those 42
questions were refused at retrieval ("best match below the answer threshold") and never
reached a model, so their hit@k is 0 by construction. Only one question in this run was
answered by Groq before the quota pushed everything to Gemini.

What the Gemini rows say: 41 answers,
hit@k 0.675, precision
0.65, refusal accuracy
0.732 — the backup model is not a
degraded stand-in, it carries the run.

## How hedging works

`ProviderRouter` starts provider *i* after `hedge_seconds * i` instead of after
provider *i-1* fails. The first success wins and the rest are cancelled; a fast
failure (429 in milliseconds) sets an event so the backup starts immediately rather
than waiting out the timer. A slow primary therefore costs at most the hedge delay,
not its own timeout.

## Caveats

- All 84 rows scored, so refusal accuracy is comparable with the pre-fallback run.
- hit@k moved 0.29 -> 0.391 across the three runs, but the question
  sets and providers changed together; treat the direction as encouraging, not as a
  precise effect size.
- The 15.7 s worst case in the hedged run is a slow Gemini answer, not a wait for a
  dead provider.
