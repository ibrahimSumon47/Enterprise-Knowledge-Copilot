# Enterprise Knowledge Copilot

**Ask the handbook. Get answers with proof.**

An enterprise-grade RAG copilot over a public company handbook (GitLab Handbook,
CC BY-SA 4.0) with:

- role-based document access (RBAC) enforced by Supabase Row Level Security
- cited answers — every claim points to a document and section
- refusal when retrieval confidence is low, instead of guessing
- audit log of every question, role, source and latency
- an evaluation dashboard for retrieval and refusal quality

## Stack

| Layer | Choice |
| --- | --- |
| Web app | Next.js 16 (App Router) on Vercel |
| API | FastAPI on a free Hugging Face Space |
| Data | Supabase — Postgres, pgvector, Auth, RLS |
| LLM | Groq (main) + Gemini (backup), both free tiers |

Everything runs on free tiers and in the cloud; nothing is paid.

## Status

Deploy skeleton only. The copilot features above are built on top of this
scaffold — see `docs/REQUIREMENTS_LOG.md` for the requirement list and
`docs/OWNER_ANSWERS.md` for the agreed decisions.

## Local development

```bash
pnpm install
pnpm dev
```

`pnpm build` must pass before pushing; Vercel runs the same build.

## Environment variables

Copy `.env.example` to `.env.local` and fill in your own values — never commit
them. Values live in GitHub repository secrets for CI and in Vercel project
settings for deployments.

## License note

Retrieved handbook content is GitLab's, licensed CC BY-SA 4.0; attribution is
preserved in retrieved chunks and citations.
