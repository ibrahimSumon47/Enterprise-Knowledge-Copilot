# HANDOFF

How any person or AI resumes this project from zero context.

## 1. Read, in this order

1. `AGENTS.md` — rules, stack, commands, definition of done.
2. `docs/PROJECT_STATE.md` — what is done, what is blocked, the exact next step.
3. `docs/DECISIONS.md` and `docs/adr/` — why the stack looks like this.
4. `docs/features.json` — feature status with evidence.

## 2. Get the environment running

```bash
pnpm install
pnpm dev            # http://localhost:3000
pnpm lint && pnpm typecheck && pnpm test && pnpm build
```

Web environment variables (`.env.local`, never committed):

```
NEXT_PUBLIC_SUPABASE_URL=https://ctfatevadhojxycuplsh.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=...
NEXT_PUBLIC_API_BASE_URL=...
```

API environment variables (Space or any Docker host):

```
SUPABASE_URL=...
SUPABASE_DB_URL=...        # must be the Session pooler string
SUPABASE_SERVICE_ROLE_KEY=...
GROQ_API_KEY=...
GEMINI_API_KEY=...
ALLOWED_ORIGINS=https://enterprise-knowledge-copilot-wine.vercel.app
```

## 3. Deploy

- Web: pushes to `main` deploy through the linked Vercel project.
- Database: `gh workflow run db-migrate.yml` applies `supabase/migrations/*.sql`
  with the `SUPABASE_DB_URL` secret.
- Role accounts: `gh workflow run seed-users.yml` (needs `EKC_DEMO_PASSWORD`).
- API: build `api/Dockerfile` and host it anywhere with Docker. A Hugging Face
  Docker Space needs PRO, which the free-only rule forbids — see the Blocked
  section of `docs/PROJECT_STATE.md`.
- Corpus: `python scripts/build_corpus.py` regenerates `data/corpus.jsonl` from
  the checkout in `.corpus-src/` (see `docs/RUNBOOK.md`).

## 4. Ready-to-paste resume prompt

> You are continuing the Enterprise Knowledge Copilot repository. Read AGENTS.md,
> docs/PROJECT_STATE.md and docs/features.json first. The stack is Next.js 16 on
> Vercel, FastAPI in api/, Supabase Postgres with pgvector and RLS, free LLM
> providers behind a router. Do not change the access model: the permission
> predicate belongs inside the SQL. Resume from the "Next step" section in
> PROJECT_STATE.md, run `node scripts/check-done.mjs --phase P5` when the phase is
> finished, and update PROJECT_STATE.md and features.json before you stop.
