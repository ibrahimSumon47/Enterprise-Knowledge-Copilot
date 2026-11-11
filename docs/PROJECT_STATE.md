# PROJECT STATE

Updated at the end of every phase. An AI resuming this repo should read
`AGENTS.md`, then this file, then `docs/HANDOFF.md`.

**Last updated:** 2026-11-11 (phase P0–P4 partial)

## Blocked

**Hugging Face Docker Spaces are no longer free.** Creating the Space returns
HTTP 402: *"Static Spaces are free for everyone, but hosting Gradio and Docker
Spaces on free cpu-basic requires a PRO subscription."*

- Impact: the FastAPI service in `api/` cannot be hosted on the planned free
  tier, so the deployed web app has no live API behind it yet.
- The service itself is complete and ready to run anywhere that builds the
  image: `Dockerfile` (or `scripts/prepare_space.sh` for a Space).
- Options for the owner (pick one, no code change needed):
  1. HF PRO subscription (paid — not allowed by the free-only rule).
  2. A free static Space cannot run FastAPI. Use another free Docker host
     (for example Render's free web service) and set `NEXT_PUBLIC_API_BASE_URL`
     to it; the image is portable.
  3. Run the API locally with `uvicorn app.main:app --port 7860` and point
     `NEXT_PUBLIC_API_BASE_URL` at it for local review.
- Everything else that does not need the API was continued: schema, migrations,
  corpus, CI, evaluation harness, docs and the web shell.

## Phase status

| Phase | Scope | Status |
| --- | --- | --- |
| P0 | repo, rules, hooks, CI, deploy | **done** — CI green on `main`, web live on Vercel |
| P1 | auth, roles, seeded accounts | **code done, cannot sign in on the web** — seven role accounts authenticate against Supabase; the web app needs the two `NEXT_PUBLIC_SUPABASE_*` variables in the Vercel dashboard |
| P2 | ingestion and corpus | **done** — `ingest.yml` run 43038984299 finished 754/754 documents, 12,032 chunks (11,987 rows in the database) |
| P3 | permission-aware retrieval | **code done** — the predicate lives inside `search_chunks` and in RLS; the zero-leakage count is not measured yet |
| P4 | pipeline, citations, refusal, providers | **code done, not serving** — the 512 MB host restarts while loading the encoder, so `/chat` returns 502 |
| P5 | chat UI, source drawer, palette | **partial** — page, citation cards, refusals and error states ship; the command palette is not built |
| P6 | admin, audit log, traces | **partial** — admin starts ingestion, polls the job and verifies the audit chain; `/traces` is a redirect and there is no document-level editor |
| P7 | evaluation suite | **partial** — 84-question golden set, runner and offline CI subset; no report written |
| P8 | security hardening and documentation | **done** — threat model, security report, runbook, `security.txt`, CI scanners |
| P9 | polish, README, handoff | **done** — ADR, project facts, `llms.txt`, credits page |

`node scripts/check-done.mjs` numbers phases differently: its P8 is the evaluation
report, and it is the only phase that fails (`docs/reports/eval.json` and
`docs/reports/gold.json` missing). P0-P7 and P9 print DONE.

## Done and verified

- **Database migrations applied for real.** `DB migrate` run 43018866865 succeeded; the verify step listed `audit_log, chunks, documents, eval_runs, profiles` and extensions `vector, pg_trgm` in the live Supabase project.
- **Role accounts seeded** through `seed-users.yml` (run 43019244493 succeeded) using the `EKC_DEMO_PASSWORD` repository secret.
- **Vercel environment variables are NOT set.** The CLI's non-interactive `env add` stored values in the wrong slot once, so the mis-stored entry was removed rather than left in place. Add these three in the Vercel dashboard (Settings → Environment Variables, Production and Preview): `NEXT_PUBLIC_SUPABASE_URL` = `https://ctfatevadhojxycuplsh.supabase.co`, `NEXT_PUBLIC_SUPABASE_ANON_KEY` = the project's publishable/anon key, `NEXT_PUBLIC_API_BASE_URL` = the API host once one exists.

- GitHub repo `main`, husky hook stripping attribution trailers, CI workflow with a
  commit-hygiene gate, CodeQL, gitleaks, DB migrate, seed, keepalive and Space-secret workflows.
- Web app: Next.js 16 + Tailwind v4 design system, dark-first command-center landing page,
  theme toggle with View Transitions, honest footer. `pnpm lint`, `pnpm typecheck`,
  `pnpm test` (6 tests), `pnpm build` all pass locally.
- Live: https://enterprise-knowledge-copilot-wine.vercel.app (Vercel project linked to the repo,
  auto-deploy on push to `main`).
- Supabase project `ctfatevadhojxycuplsh` (ap-south-1, Postgres 17) with two migrations:
  schema, helper functions, RLS policies and `search_chunks` hybrid retrieval.
- Corpus: `data/corpus.jsonl` — 754 documents, 871k words, 12 labelled synthetic confidential
  documents, GitLab Handbook CC BY-SA 4.0 attribution preserved per document.
- API service: `api/` — JWT/JWKS auth, rate limiting, hash-chained audit, provider router
  (Groq → Gemini → mock) with circuit breaker, cross-encoder rerank, citation verification,
  PII redaction, SSE streaming endpoint, admin and evaluation endpoints.
- Evaluation: `eval/golden_set.jsonl` (84 questions: answerable, unanswerable, Bangla,
  multi-document, cross-role) and `eval/run_eval.py` with a hard leakage gate.

## Deployment path

The API runs as a Docker web service on Render's free plan (`render.yaml`, root
`Dockerfile`, port from `$PORT`). The Hugging Face Space path is retired: Docker
Spaces now require a PRO plan, so `.space/` and `scripts/prepare_space.sh` are
gone. Retrieval uses ONNX Runtime (fastembed + flashrank) because 512 MB cannot
hold torch plus two transformer models.

## Open work

1. **Vercel environment variables.** Add `NEXT_PUBLIC_SUPABASE_URL`
   (`https://ctfatevadhojxycuplsh.supabase.co`) and `NEXT_PUBLIC_SUPABASE_ANON_KEY`
   (the publishable key, Settings -> API Keys) in the dashboard for Production and
   Preview, then redeploy. Until then middleware cannot guard `/chat` and `/admin`,
   and the login form cannot create a session.
2. **API memory.** The free 512 MB instance exceeds its limit while `fastembed`
   loads the multilingual encoder, with the reranker disabled, so every `/chat`
   call returns 502 and the instance restarts. Options: a smaller quantised encoder
   plus a full re-ingest, remote embeddings, or a paid 1 GB instance.
3. **Evaluation report.** `docs/reports/eval.json` and `docs/reports/gold.json`
   cannot be produced until answers work end to end.

## Resolved since the previous snapshot

- Migrations applied and verified; role accounts seeded; corpus ingested.
- Chunker heading test fixed in the code, not the assertion.
- Vercel deploys green after anchoring `.vercelignore`; `security.txt` returns 200.
- Audit, provider router, refusal and citation verification covered by unit tests.

## Evidence

| Thing | Where |
| --- | --- |
| Live web | https://enterprise-knowledge-copilot-wine.vercel.app |
| Repo | https://github.com/ibrahimSumon47/Enterprise-Knowledge-Copilot |
| Supabase project | `ctfatevadhojxycuplsh` (ap-south-1) |
| HF Space | **blocked** — HTTP 402, PRO required for Docker Spaces |
| Corpus manifest | `data/corpus_manifest.json` |

## Snapshot 2026-11-11 (latest)

**Working, with evidence**

- Web: `/`, `/login`, `/chat`, `/admin`, `/trust`, `/credits`, `/evals`,
  `/llms.txt` and `/.well-known/security.txt` all answer 200 on the live origin.
- API: `/health` -> `{"status":"ok","service":"ekc-api","rss_mb":…}`; all seven
  role accounts authenticate and `/me` returns the stored role and visible levels.
- Corpus: 754 documents indexed into 12,032 chunks; `documents` and `chunks` are
  queryable in the live database.
- Checks: `pnpm lint`, `pnpm typecheck`, `pnpm test` (6) and `pnpm build` exit 0;
  the latest CI run on `main` succeeded.
- Feature ledger: 12 features, 8 pass, 4 partial, 0 blocked, 0 fail.

**Known red**

- Chat: 502 on every call, measured twice, with `/health` unreachable immediately
  afterwards (memory kill, confirmed by the host's own notification).
- Login on the web: impossible until the two Supabase variables reach Vercel.
- `docs/reports/eval.json` and `docs/reports/gold.json` do not exist, so the gate's
  P8 stays open. The 84-question golden set and the harness are committed.
