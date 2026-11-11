# PROJECT STATE

Updated at the end of every phase. If you are an AI resuming this repo: read
`AGENTS.md`, then this file, then `docs/HANDOFF.md`.

## Now

- **Phase:** P0 — foundation
- **Status:** in progress
- **Next step:** write the web shell + design tokens, deploy the API skeleton to the HF Space, apply the first migrations through CI.

## Done

- [x] Interview recorded in `docs/OWNER_ANSWERS.md`; requirements R-01…R-34 in `docs/REQUIREMENTS_LOG.md`
- [x] GitHub repo, Vercel project linked + auto-deploy, Supabase project healthy
- [x] Minimal Next.js 16 scaffold deployed at https://enterprise-knowledge-copilot-wine.vercel.app

## Blocked

_None._ Two secrets can only be read by CI, so anything that needs their value is done by a GitHub Actions workflow: the HF Space secrets push and the SQL migrations.

## Decisions pending

- none

## Evidence

| Thing | Where |
| --- | --- |
| Live web | https://enterprise-knowledge-copilot-wine.vercel.app |
| Repo | https://github.com/ibrahimSumon47/Enterprise-Knowledge-Copilot |
| Supabase project | `ctfatevadhojxycuplsh` (ap-south-1) |
| HF Space | not created yet |
