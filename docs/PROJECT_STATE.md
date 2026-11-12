# PROJECT STATE

Updated at the end of every phase. An AI resuming this repo should read
`AGENTS.md`, then this file, then `docs/HANDOFF.md`.

**Last updated:** 2026-11-12 (last improvement sprint)

## Where it runs

| Thing | Where | State |
| --- | --- | --- |
| Web | https://enterprise-knowledge-copilot-wine.vercel.app | live, auto-deploy on `main`, `ignoreCommand` skips builds that touch no web file |
| API | https://enterprise-knowledge-copilot-2u57.onrender.com | live, Render free Docker service, 512 MB, cold start ~50 s |
| Data | Supabase project `ctfatevadhojxycuplsh` | Postgres 17, pgvector, RLS, 754 documents / 12 032 chunks |
| Corpus | `data/corpus.jsonl` | GitLab Handbook (CC BY-SA 4.0) + 12 labelled synthetic documents |

Vercel has `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY` and
`NEXT_PUBLIC_API_BASE_URL` set for Production and Preview; `/chat` and `/admin`
answer 307 to `/login` when signed out, so the variables are in place. The seven
role accounts sign in through the normal form.

## Model-free retrieval evaluation (2026-11-12, this sprint)

Measured through `/admin/retrieval?all_candidates=true` with no LLM call;
`eval/retrieval_eval.py`, three passes per split, spread 0.000 everywhere.

| Split | Config | hit@3 | hit@10 | MRR |
| --- | --- | --- | --- | --- |
| dev (32 answerable) | fused only | 0.688 | 0.719 | 0.601 |
| dev | + TinyBERT rerank | 0.688 | 0.781 | 0.686 |
| test (21 answerable) | fused only | 0.857 | 0.857 | 0.833 |
| test | + TinyBERT rerank | 0.857 | 0.857 | 0.809 |

The reranker helps ordering on dev and ties on test; a fused/rerank blend was
tested and did not beat either on ordering or separation. Refusal at the
configured 0.15 answers 0.476 of answerable test questions and refuses 0.846 of
unanswerable ones; the dev sweep found no threshold that refuses 90% of
unanswerable questions while refusing fewer than 19 of 32 answerable ones, because
the score distributions overlap (AUC 0.667 dev, 0.687 test). That is the measured
limit behind the end-to-end hit@k. Full report: `docs/reports/retrieval_eval.md`.

Memory, measured on the deployed 512 MB instance with both ONNX models loaded and
five concurrent retrieval requests: 386 MB, settling at 402 MB across three
rounds; no restarts. There is no torch in the image — `fastembed` and `flashrank`
run on onnxruntime (`api/requirements.txt`).

Permission difference verified live on the same question ("engineering salary
bands"): role=guest returns zero synthetic documents; role=admin returns
"Engineering salary bands (synthetic)" at score 1.0. Evidence in
`.tmp/permission_check.json` during the run, reproducible with the command in the
report.

## Current quality (last full run, 2026-11-12)

| Metric | Value |
| --- | --- |
| Questions scored | 84 / 84 (0 excluded as provider outage) |
| hit@k | 0.406 |
| citation precision | 0.333 |
| refusal accuracy | 0.679 |
| p50 / p95 / slowest | 2 980 / 6 687 / 12 137 ms |
| permission leakage | **0** (hard gate) |

Provider path: Groq primary, Gemini `gemini-3.1-flash-lite` backup with
`gemini-3.5-flash-lite` behind it, hedged at 1.5 s and capped at 12 s.
`/health` exposes `providers.calls/hedged/backup_won/failed_over`.
Retrieval: `bge-small-en-v1.5` (ONNX, 384 dims), hybrid pgvector + full-text with
RRF, `ms-marco-TinyBERT-L-2-v2` cross-encoder, 24 candidates / 192 tokens,
answer floor 0.15.

Reports: `docs/reports/eval.md`, `eval_providers.md` (five transport runs),
`retrieval_refusals.md` (why 42 questions are refused), `reranker_upgrade.md`
(the larger cross-encoder that does not fit).

## Phase status

| Phase | Scope | Status |
| --- | --- | --- |
| P0 | repo, rules, hooks, CI, deploy | **done** — CI green on `main`, web live |
| P1 | auth, roles, seeded accounts | **done** — seven role accounts, RLS, sign-in on the web |
| P2 | ingestion and corpus | **done** — 754 documents, 12 032 chunks |
| P3 | permission-aware retrieval | **done** — predicate inside `search_chunks` and RLS, leakage 0 |
| P4 | pipeline, citations, refusal, providers | **done** — `/chat` answers, hedged providers, citations verified |
| P5 | chat UI, source drawer, palette | **done** — palette on Cmd+K, cold-start banner |
| P6 | admin, audit log, traces | **done** — ingestion, audit chain, document access editor and a real `/traces` view |
| P7 | evaluation suite | **done** — 84-question set, runner, report, CI subset |
| P8 | security hardening and documentation | **done** — threat model, security report, scanners |
| P9 | polish, README, handoff | **done** — ADR, facts, `llms.txt`, credits |

`node scripts/check-done.mjs` prints DONE for every phase; it validates artefacts,
not behaviour, so treat this table as the behavioural view.

## Known limits (measured, not guessed)

- **Refusal separation.** AUC 0.667/0.687 means the top score cannot separate
  answerable from unanswerable questions well enough to hit both refusal targets.
  The evidence grader in the pipeline is the lever, and it is off by default
  because it doubles model calls against a free quota.
- **`langgraph` 0.2.x advisories.** Accepted risk, explained in
  `docs/reports/security.md`; fixing means a 1.x migration.
- **Audit chain repair.** Entries written before 2026-11-12 could not verify:
  the hash covered a `created_at` the insert never stored. `db.insert_audit` now
  persists it, `audit.verify_chain` decodes jsonb and anchors the window, and
  `scripts/repair_audit_chain.py` re-hashed the existing rows (backup in `.tmp/`).
  `/audit/verify` on the deployed API is the check that matters.

1. **Recall is the weak point.** 14 answerable questions retrieve the right
   document at rank 1 and are still scored near zero by TinyBERT
   (`docs/reports/retrieval_refusals.md`).
2. **A bigger reranker does not fit.** MiniLM-L-12 reached 402 MB RSS and the
   instance died within a few requests. TinyBERT is the ceiling on 512 MB.
3. **Free quotas throttle.** Groq answers 429 in milliseconds, so the hedge timer
   rarely fires (1 in 55 calls); long evaluations can still be rate-limited.
4. **Cold start is honest but slow.** The free instance sleeps; the first request
   after idle takes ~50 s while the image and ONNX models load.
5. **Evaluation noise.** hit@k has read 0.290 – 0.406 across runs of the same
   retrieval configuration, so only latency and memory deltas are attributable.

## Open work

1. **Retrieval target missed and documented.** Gold audit is clean, recall@50 is
   0.875 on dev, and the blocker is the cross-encoder, not the candidate list;
   `docs/reports/retrieval_sprint.md` has the numbers, the grader experiment and the
   exact reason the target was not reached.
2. **One reranker option left unmeasured:** `Xenova/ms-marco-MiniLM-L-6-v2` through
   fastembed (~80 MB). It needs an eval with enough free quota to run three times.
3. **Query rewriting** before retrieval (one extra model call) is the other untried
   lever; the evidence grader showed how quickly a second call eats the quota.

Done in this sprint: admin document editor with audit entries, `/traces` with real
audit data, Cmd+K palette, cold-start banner, nightly reset workflow and the
delete lock on the shared admin account.

## Deployment notes

- Render rebuilds only when `api/**`, `Dockerfile`, `render.yaml` or
  `data/corpus.jsonl` change (`buildFilter`); a docs commit no longer restarts it.
- Render injects `PORT`; the image runs `uvicorn --workers 1` because the ONNX
  models are per-process.
- Migrations: `gh workflow run db-migrate.yml`. Accounts: `seed-users.yml`.
  Ingest: `ingest.yml` (754 documents, rate-limited).
- Hugging Face Docker Spaces are retired for this project: free Docker Spaces now
  require PRO (HTTP 402), which the free-only rule forbids.

## Evidence

| Thing | Where |
| --- | --- |
| Live web | https://enterprise-knowledge-copilot-wine.vercel.app |
| API health | https://enterprise-knowledge-copilot-2u57.onrender.com/health |
| Repo | https://github.com/ibrahimSumon47/Enterprise-Knowledge-Copilot |
| Evaluation | `docs/reports/eval.json`, `eval.md` |
| Refusal analysis | `docs/reports/retrieval_refusals.md` |
| Lessons | `docs/LESSONS.md` |
