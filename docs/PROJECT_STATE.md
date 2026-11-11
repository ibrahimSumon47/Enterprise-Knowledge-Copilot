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
  image: `api/Dockerfile` (or `scripts/prepare_space.sh` for a Space).
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
| P0 | repo, rules, hooks, CI, scaffolds, deploy | **done** (web live on Vercel) |
| P1 | auth, roles, seeded accounts, admin shell | **partial** — Supabase clients, middleware, auth pages and the seed workflow exist; role pages not built |
| P2 | ingestion and corpus | **partial** — 754-document slice + 12 synthetic docs committed; ingestion code complete; not executed (needs the API host) |
| P3 | permission-aware retrieval | **code done** — SQL predicate + `search_chunks` + RLS policies; leakage tests not yet executed against a live database |
| P4 | LangGraph pipeline, citations, refusal, providers | **code done** — graph, verification, refusal, provider router with breaker; live run blocked with the API host |
| P5 | chat UI, source drawer, palette | **not started** |
| P6 | admin, audit log, traces | **not started** |
| P7 | evaluation suite and dashboard | **partial** — 84-question golden set + runner + offline CI job |
| P8 | security hardening and documentation | **partial** — CI scanners, security headers middleware; threat model not written |
| P9 | final polish, README, diagrams, handoff | **not started** |

## Done and verified

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

## Next step (exact)

1. Choose a free Docker host for `api/` (see Blocked) and set `NEXT_PUBLIC_API_BASE_URL`
   in Vercel for production and preview.
2. Run `gh workflow run db-migrate.yml`, then `gh workflow run seed-users.yml`
   (needs the `EKC_DEMO_PASSWORD` secret, already set) so the seven role accounts exist.
3. Build the chat UI (P5) against the API, then admin/audit/traces (P6), then run the full
   evaluation (P7) and write the security documentation (P8).

## Evidence

| Thing | Where |
| --- | --- |
| Live web | https://enterprise-knowledge-copilot-wine.vercel.app |
| Repo | https://github.com/ibrahimSumon47/Enterprise-Knowledge-Copilot |
| Supabase project | `ctfatevadhojxycuplsh` (ap-south-1) |
| HF Space | **blocked** — HTTP 402, PRO required for Docker Spaces |
| Corpus manifest | `data/corpus_manifest.json` |
