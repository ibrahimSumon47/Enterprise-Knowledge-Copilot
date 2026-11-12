# Demo script (3–5 minutes)

Numbers below are the shipped ones: hit@k 0.406 on the 84-question set, p95 6.7 s,
permission leakage 0. Do not quote a number the site cannot reproduce.

## 0:00 — The problem (30 s)

*Screen: the landing page.*

> A company handbook is 754 documents and 871 000 words. A new hire asks a simple
> question and gets a search page. This copilot answers with citations — or says it
> does not know.

## 0:30 — A cited answer (60 s)

*Sign in as `employee@ekc.local`. Ask: "How do I submit an expense claim?"*

> The answer arrives with `[1]` markers. Open the source drawer: the passage is
> highlighted, the document title and licence are shown, and the score is printed.
> The provider is named (`groq` or `gemini`) because the router hedges between two
> free tiers.

Point at the footer of the answer: `confidence: high`, `latency`.

## 1:30 — An honest refusal (40 s)

*Ask: "What is the salary band for a staff engineer?"*

> No citation, no guess. The refusal is a decision, not a failure: the reranker
> found nothing above the floor, and the audit log records the reason
> (`best match below the answer threshold`).

## 2:10 — Permission denial (50 s)

*Sign in as `finance@ekc.local`, open `/documents`, then sign in as `employee` and ask
about a synthetic confidential document.*

> The finance account can read its department's synthetic documents; the employee
> account cannot even see them. The predicate is inside the SQL function and
> mirrored by RLS — a post-filter after retrieval would be a bug. Leakage is
> measured at 0 on every evaluation run.

## 3:00 — Traces and audit (40 s)

*Open `/traces` as admin.*

> Last 100 questions: provider, latency, refusal reason, and the hedge counters
> (`calls / hedged / backup_won / failed_over`). The audit chain is hash-linked;
> "verify" recomputes it.

## 3:40 — The evaluation (40 s)

*Open `/evals`.*

> 84 questions across answerable, unanswerable, Bengali, multi-document and
> cross-role cases. hit@k 0.406, citation precision 0.333, refusal accuracy 0.679,
> p95 6.7 s, leakage 0. The weak spot is stated plainly: 14 answerable questions
> are refused because a 4 MB cross-encoder scores the right passage near zero, and a
> bigger one does not fit the free 512 MB instance.

## 4:20 — Close (20 s)

> Free tier end to end: Vercel, Render, Supabase. No paid service, no trial, no
> fake data — twelve synthetic confidential documents are labelled as such
> everywhere they appear.
