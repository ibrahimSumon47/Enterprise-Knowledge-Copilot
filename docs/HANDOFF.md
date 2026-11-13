# HANDOFF

How a person or an AI resumes this project from zero context.

## 1. Read, in this order

1. `AGENTS.md` — rules, stack, commands, definition of done.
2. `docs/PROJECT_STATE.md` — what is done, what is blocked, the next step.
3. `docs/features.json` — feature status with evidence.
4. `docs/DEMO_SCRIPT.md` — the 90-second walkthrough a reviewer will follow.

## 2. Get the environment running

```bash
pnpm install
pnpm dev            # http://localhost:3000
pnpm lint && pnpm typecheck && pnpm test && pnpm build
node scripts/check-done.mjs
```

Web variables (`.env.local`, never committed):

```
NEXT_PUBLIC_SUPABASE_URL=https://ctfatevadhojxycuplsh.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=...
NEXT_PUBLIC_API_BASE_URL=https://enterprise-knowledge-copilot-2u57.onrender.com
EKC_GUEST_PASSWORD=...      # server-only, powers "Open sample workspace"
```

API variables (Render): `SUPABASE_URL`, `SUPABASE_DB_URL`, `SUPABASE_SERVICE_ROLE_KEY`,
`GROQ_API_KEY`, `GEMINI_API_KEY`, `ALLOWED_ORIGINS`.

## 3. The two surfaces

- Public site: `/`, `/product`, `/security`, `/privacy`, `/terms`, `/contact`,
  `/licenses`. Product copy only; engineering evidence belongs in this repository.
- App: `/chat`, `/library`, `/admin`, `/admin/quality`. Admin quality holds the
  answer-quality report and the performance view; it is not linked publicly.

`POST /api/sample-workspace` signs a visitor into the shared guest account with
the password in `EKC_GUEST_PASSWORD` and redirects to `/chat`. Without that
variable the button falls back to `/login`.

## 4. Deploy

- Web: pushes to `main` deploy on Vercel.
- API: Render free Docker service from `render.yaml` (`buildFilter` only rebuilds
  for `api/**`, `Dockerfile`, `render.yaml`, `data/corpus.jsonl`).
- Database: `gh workflow run db-migrate.yml`.
- Accounts: `gh workflow run seed-users.yml`; ingestion: `gh workflow run ingest.yml`.
- Sign-in e2e: `.github/workflows/e2e-auth.yml` waits for the deployed build, then
  signs in as all seven roles through the real form (needs `EKC_DEMO_PASSWORD`).
- Keep-warm: `.github/workflows/keep-warm.yml` pings `/health` every ten minutes.

## 5. Ready-to-paste resume prompt

> You are continuing the Enterprise Knowledge Copilot repository. Read AGENTS.md,
> docs/PROJECT_STATE.md, docs/features.json and docs/HANDOFF.md first. The public
> site and the app are separate surfaces; do not put engineering evidence back
> into product copy. The stack is Next.js 16 on Vercel, FastAPI in `api/`,
> Supabase Postgres with pgvector and RLS, and free model providers behind a
> router. Do not change the access model: the permission predicate belongs inside
> the SQL. Resume from the next step in PROJECT_STATE.md, run
> `node scripts/check-done.mjs`, and update PROJECT_STATE.md and features.json
> before you stop.

## Exact next step (2026-11-13, paused mid-phase)

`node scripts/check-done.mjs` reads `docs/PHASES.json`. Answer quality is paused
with a measured limit: the evidence-quote verifier and the throttled harness are
shipped, but both free providers returned 429s long enough that no valid dev or
test run completed. When quota is available, run:

```bash
python eval/run_eval.py --split dev --cache-tag quality-v2 --password ... --api-url ... --supabase-url ... --anon-key ...
python eval/run_eval.py --split test --cache-tag quality-v2 --password ... # once
```

The harness refuses to publish a run with more than 5% provider errors, so an
invalid attempt never overwrites the report. Replace the quality block in README
and PROJECT_STATE only with a valid test run, then close P1 as done or a measured
limit. Phases 2 to 5 are recorded in `docs/PHASES.json` as scope limits; start
with 2a (organisations and org_id scoping) because the upload, invite and
isolation tests all depend on it.

