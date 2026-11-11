# Runbook

## Origins

| Piece | Origin | Health |
| --- | --- | --- |
| Web | https://enterprise-knowledge-copilot-wine.vercel.app | `/` returns the landing page |
| API | https://enterprise-knowledge-copilot-2u57.onrender.com | `/health` returns `{"status":"ok",…}` |
| Database | Supabase `ctfatevadhojxycuplsh`, `ap-south-1` | `/ready` checks pool, schema and corpus |

## Deploy

- Web: push to `main`; Vercel builds from the repository root. `.vercelignore`
  keeps `api/`, `data/`, `eval/`, `docs/`, `supabase/` out of the bundle.
- API: Render web service, Docker runtime, root `Dockerfile`, `PORT` injected by
  Render. Auto-deploy on commit; otherwise **Manual Deploy**.
- Schema: `gh workflow run db-migrate.yml` applies `supabase/migrations/*.sql`
  with `psql "$SUPABASE_DB_URL"`.

## Re-index the corpus

The free API instance is too slow to embed 754 documents. Run ingestion on a
build runner instead:

```bash
gh workflow run ingest.yml --ref main
gh run watch
```

Progress is visible in `public.ingest_jobs` (`status`, `progress`, `stats`).
Re-running is safe: documents upsert by slug, chunks are replaced.

## Rotate secrets

| Secret | Where it is used | How to rotate |
| --- | --- | --- |
| `EKC_DEMO_PASSWORD` | seven role accounts | update the GitHub secret, `gh workflow run seed-users.yml` |
| `GROQ_API_KEY` / `GEMINI_API_KEY` | API host | rotate at the provider, update Render env vars, redeploy |
| `SUPABASE_SERVICE_ROLE_KEY` | API host only | rotate in Supabase, update Render, redeploy |
| `SUPABASE_DB_URL` | migrations, ingestion, keep-alive | rotate the database password, update the GitHub secret |

## Diagnosis

**Chat returns 502 and `/health` is briefly empty.** The instance restarted,
usually memory. Confirm with `/health` → `rss_mb`. Keep
`EKC_RERANK_ENABLED=1` on the 512 MB host: bge-small leaves room for the TinyBERT
reranker (about 380 MB RSS with both loaded). Set it to 0 only to debug memory
only where it fits.

**`/ready` fails.** Read the payload: it names the failing check (pool, schema,
corpus). A missing corpus usually means the image was built from a commit
without `data/corpus.jsonl`.

**Ingestion job says `failed`.** Read `ingest_jobs.error`. Past causes: corpus
path inside the container, `stats` sent as a dict instead of JSON text.

**Web build fails.** Run `pnpm build` locally; check `.vercelignore` did not
exclude something the build imports (an unanchored `supabase/` once hid
`lib/supabase`).

## Rollback

Vercel: redeploy the previous deployment from the dashboard. Render: pick the
previous deploy in the Deploys tab and redeploy. Schema changes are additive; no
migration in this repository drops a table.
