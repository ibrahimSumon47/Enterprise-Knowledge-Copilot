# Provider fallback and hedged requests

Four full runs of the same 84-question set against the deployed API.

| Run | Scored | hit@k | Precision | Refusal | p50 | p95 | Leakage |
| --- | --- | --- | --- | --- | --- | --- | --- |
| No working fallback | 84 | 0.29 | 0.232 | 0.595 | 3280 ms | 5047 ms | 0 |
| Gemini fallback, serial | 82 | 0.343 | 0.28 | 0.634 | 3482 ms | 24098 ms | 0 |
| Gemini fallback, hedge 3 s | 84 | 0.391 | 0.317 | 0.667 | 3541 ms | 9963 ms | 0 |
| Gemini fallback, hedge 1.5 s | 84 | **0.333** | **0.274** | **0.607** | **3125 ms** | **8960 ms** | **0** |

## Did the shorter hedge help?

| | hedge 3 s | hedge 1.5 s | Change |
| --- | --- | --- | --- |
| p50 | 3541 ms | 3125 ms | -12% |
| p95 | 9963 ms | 8960 ms | -10% |
| hit@k | 0.391 | 0.333 | -0.058 |
| Precision | 0.317 | 0.274 | -0.043 |

Latency improved about 10%, and the quality difference is inside the spread this
evaluation has shown across runs (hit@k has read 0.290, 0.333, 0.343 and 0.391 for
configurations that differ only in transport). Treat the quality delta as noise and
the latency delta as small but real.

## What the hedge actually costs

Counters from `/health` across the 1.5 s run: 55 model calls,
1 hedged (2%),
12 answered by the backup,
11 primary failures.

Almost no double-spend: a quota-limited Groq answers 429 in milliseconds, so the
"fast failure" path starts Gemini immediately and the timer rarely fires. The hedge
is a safety net for a *hanging* primary, not the normal path.

## By provider (1.5 s run)

| Provider | Questions | hit@k | Precision | Refusal | p50 ms | p95 ms |
| --- | --- | --- | --- | --- | --- | --- |
| gemini | 41 | 0.564 | 0.537 | 0.61 | 4824 | 9534 |
| groq | 1 | 1.0 | 1.0 | 1.0 | 4676 | 4676 |
| none | 42 | 0.0 | 0.0 | 0.595 | 2440 | 3079 |

`none` is not a provider: those questions were refused at retrieval and never reached
a model, so their hit@k is 0 by construction.

## Caveats

- One provider pair was measured on one day of free-tier quota; the mix of Groq vs
  Gemini answers changes with the quota window, which is why the provider split is
  reported next to the aggregate.
- hit@k moves of ±0.05 appear between runs of the same configuration; only the
  p95 halving (24 s -> 10 s) is large enough to attribute to the change.
