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

## Slice status, 2026-11-13

Done and applied: 2a-1 schema. `20261113150000_organisations.sql` adds
organizations, org_members, groups, org_id on documents/chunks/conversations/
messages/feedback/audit_log/unanswered_questions, membership RLS, and
`search_chunks_org`. `db-migrate.yml` applied it and ran
`supabase/tests/cross_tenant.sql`, which passed: a sample-workspace admin sees
zero documents and zero chunks of a second organisation while its own documents
remain readable.

### 2a-2 retrieval and API (finished, 2026-11-14)

`AuthUser` now carries `org_id` from the verified `org_members` row, and a user
without active membership gets 403. `db.search_chunks` calls
`search_chunks_org` with that org first; retrieval, chat, streaming chat,
library, audit, the unanswered queue, feedback, document access changes and
conversation reads/writes all pass the same server-derived org. Feedback goes
through `db.record_feedback`, which only inserts when the message belongs to the
caller's conversation and tenant. Guessed conversation ids and foreign message
ids return 404. `api/tests/test_org_scope.py` covers a forged token org claim, a
swapped `X-Org-Id` header, guessed ids and two org identifiers at the API layer;
`supabase/tests/cross_tenant.sql` covers the database layer.

### P2a finished (2026-11-14)

Owner role, signup-created workspace, onboarding, and the real two-workspace
isolation suite are done and green. P2a is `done` in `docs/PHASES.json`; evidence
is in `docs/ISOLATION.md` (run 43565180117, checks=8, violations=0).

### Next: 2c invites, groups and deactivation

P2b is done (isolation run 43566997507, checks=13, violations=0). The one
carry-over is group-scoped documents, which belongs with invites because groups
have no members yet.

1. Migration: add `documents.group_id` referencing `groups`; add
   `invites(id, org_id, token_hash, role, group_id, created_by, expires_at,
   used_at, used_by)`; add `org_members.deactivated_at` only if the existing
   `status` column is not enough. RLS: owners/admins manage invites; a used
   invite creates one membership through a `security definer` function.
2. Retrieval: new `search_chunks_grouped(...)` taking the caller's group, with
   `(d.group_id is null or d.group_id = caller_group)` beside the org predicate;
   add `group_id` to `AuthUser` and `list_documents`. Upload accepts a group id
   only when it belongs to the caller's org.
3. API: `POST /admin/invites` returns a copyable link with role and group;
   `POST /invites/{token}/accept`; `PATCH /admin/members/{user_id}` for role and
   deactivation; `DELETE /admin/members/{user_id}` only for an owner and never
   the owner. Deactivated members fail `current_user` with 403.
4. UI: workspace settings page showing members, role, group, active state,
   invite link with copy button, deactivate/reactivate; accept page for the link.
5. Tests: foreign-org invite token, expired/used token, admin cannot invite an
   owner or remove an admin, deactivated session gets 403, group-scoped document
   is absent from another group's retrieval, isolation suite stays at zero.

Then 2d password reset and Google sign-in (`docs/OWNER_TODO.md` for console
steps), 2e analytics/queue/audit CSV/settings, P3, P4, P5.

## Earlier: 2b browser upload

1. `api/app/main.py`: add `POST /documents/upload` (multipart, 5 MB cap) that
   parses `.pdf` with `pypdf`, `.docx` with `python-docx`, `.html` by stripping
   tags and `.txt/.md` as UTF-8. Reuse `ingest.chunk_markdown`, `embed_documents`
   and `db.insert_document` with `org_id` from the caller. Add both parser
   packages to `api/requirements.txt`.
2. `DELETE /documents/{id}` currently refuses every caller. Make it owner/admin
   scoped and allow it only outside the sample workspace; add
   `POST /documents/{id}/reindex` that re-embeds the document's chunks.
3. `api/tests`: upload rejects another tenant's document id, parsing works for
   text and HTML, and the tenant is taken from membership.
4. Web: add an upload form to `/library` with file picker, progress state and
   per-document re-index/delete actions; refresh the list when done.
5. Verify on production, then mark P2b done with the run/report evidence.

### After 2b

2c invites by copyable link with role and group plus deactivation; 2d password
reset and Google sign-in with owner console steps in `docs/OWNER_TODO.md`; 2e
analytics, unanswered actions, audit CSV export and workspace settings; then P3
design, P4 buyer verification, P5 docs. `node scripts/check-done.mjs` is red only
on those phases.

## Earlier note: 2a-3 onboarding

1. `POST /onboarding` (authenticated): create `organizations` (slug from name +
   random suffix), insert `org_members` with role `owner`, and link the caller.
   Today the role check constraint has no `owner`; either add it in a migration
   or store `admin` plus an `is_owner` flag. Prefer a migration that adds
   `owner` and updates `current_org_role`/RLS to treat owner as admin.
2. A signed-up user currently gets 403 from `current_user`; allow `/onboarding`
   and `/onboarding/status` without membership while every other route keeps the
   403.
3. Web: `/onboarding` wizard — name the workspace, upload the first document
   (can reuse 2b's ingest path once it exists; until then accept a pasted title
   and text), then ask the first question and land in `/chat`.
4. Playwright against the deployed site: sign up a fresh account, finish the
   wizard, assert the workspace name and the first answer/refusal. Add the spec
   to `.github/workflows/e2e-auth.yml` with `EKC_DEMO_PASSWORD`.
5. Then 2a-4 red-team suite wired into CI and `check-done`, and only after that
   mark `P2a` done in `docs/PHASES.json`.

Remaining: 2a-3, 2a-4, 2b upload, 2c invites, 2d auth, 2e analytics, 3 design,
4 buyer flow, 5 docs. `node scripts/check-done.mjs` stays red until then and
names the open phases.

