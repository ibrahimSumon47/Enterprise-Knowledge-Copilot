# Provider fallback and hedged requests

Full runs of the same 84-question set against the deployed API. Each row changes
one transport setting; retrieval is identical.

| Run | Scored | hit@k | Precision | Refusal | p50 | p95 | max | Leakage |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| No working fallback | 84 | 0.29 | 0.232 | 0.595 | 3280 ms | 5047 ms | 10359 ms | 0 |
| Gemini fallback, serial | 82 | 0.343 | 0.28 | 0.634 | 3482 ms | 24098 ms | 49687 ms | 0 |
| Hedge 3 s | 84 | 0.391 | 0.317 | 0.667 | 3541 ms | 9963 ms | 15700 ms | 0 |
| Hedge 1.5 s | 84 | 0.333 | 0.274 | 0.607 | 3125 ms | 8960 ms | 14417 ms | 0 |
| Hedge 1.5 s + Gemini capped at 12 s | 84 | 0.406 | 0.333 | 0.679 | 2980 ms | 6687 ms | 12137 ms | 0 |

## Bounding the tail

Before the cap two of 84 answers took longer than 12 s (14.4 s and 13.0 s); after
it the slowest answer is 12137 ms, of which 12137 ms
is the single Groq call. p95 fell from 9963 ms to 6687 ms
(-33%).

**No answers were lost**: 84 questions scored and
0 were excluded. That is partly the evaluation's own retry —
a real client without a retry would see a refusal where a 14 s answer used to be.
The cap trades a rare slow answer for a predictable one.

## By provider (final run)

| Provider | Questions | hit@k | Precision | Refusal | p50 ms | p95 ms |
| --- | --- | --- | --- | --- | --- | --- |
| gemini | 41 | 0.692 | 0.659 | 0.756 | 4177 | 7100 |
| groq | 1 | 1.0 | 1.0 | 1.0 | 12137 | 12137 |
| none | 42 | 0.0 | 0.0 | 0.595 | 2258 | 3103 |

`none` is not a provider: those questions were refused at retrieval and never reached
a model, so their hit@k is 0 by construction.

## Caveats

- hit@k across these runs reads 0.290, 0.333, 0.343, 0.391 and 0.406 for changes that
  should not affect retrieval, so only the latency deltas are attributable.
- Two providers on free tiers in one day: the Groq/Gemini mix depends on the quota
  window, which is why the provider split is reported next to the aggregate.
