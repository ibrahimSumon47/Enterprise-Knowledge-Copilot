# Cross-tenant isolation gate

Two attacks are run, one against the database and one against the deployed API.

## Database layer

`supabase/tests/cross_tenant.sql` runs inside the migration workflow. It creates
a second organisation with a public document and chunk, switches to the
`authenticated` role with the sample admin's JWT claim, and fails if either row
is visible. It also checks that the owner-role constraint, the single-owner
index and the membership policies exist.

## API and real database

`.github/workflows/isolation.yml` runs `scripts/isolation_suite.mjs` on every
push to `main`. The suite:

1. creates two accounts through the real `POST /signup` route, which also creates
   two empty organisations;
2. signs both owners in through Supabase Auth and has each add one document
   through the onboarding route;
3. tries to read tenant B as tenant A through:
   - the library listing,
   - a swapped `X-Org-Id` / `X-Organisation` header,
   - retrieval (`/admin/recall`),
   - a shared answer link (`/conversations/{id}/messages`) with a guessed id,
   - a tampered bearer token,
   - the audit log,
   - the unanswered queue (a real row is inserted for B first);
4. counts every leaked row, requires exactly zero, and exits non-zero otherwise;
5. deletes both workspaces through the owner-only `DELETE /workspace` route and
   both auth users through the Supabase admin API.

`DELETE /workspace` removes documents, chunks, conversations, messages, feedback,
unanswered questions, groups and memberships. Audit rows are kept with a null
organisation so the global hash chain stays verifiable.
