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

## Evidence

- Run [43565180117](https://github.com/ibrahimSumon47/Enterprise-Knowledge-Copilot/actions/runs/43565180117):
  `checks=8 violations=0` on commit `078eab1`.
- Production sign-up and onboarding: Sign-in e2e run on `53d7308`.
- Database policies and owner constraint: DB migrate run on `3721dc6`.
## Upload attacks (2b)

Run [43566997507](https://github.com/ibrahimSumon47/Enterprise-Knowledge-Copilot/actions/runs/43566997507)
adds a renamed PDF, an oversized upload, a traversal filename, a zip-bomb DOCX
and another tenant's document id to the same suite: `checks=13 violations=0`.
`api/tests/test_uploads.py` covers each guard directly, including HTML scripts
and styles never reaching the corpus.

