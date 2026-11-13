# Organisations and isolation

## What exists after `20261113150000_organisations.sql`

- `organizations`: one row per workspace. The seeded `sample-workspace` row is
  read-only for the shared demo accounts and is flagged `is_sample`.
- `org_members`: membership, role, department, optional group and `active` or
  `deactivated` status. The primary key is `(org_id, user_id)`. The existing
  profiles were backfilled into the sample workspace with their current role.
- `groups`: group names inside an organisation; ready for invite scoping.
- `org_id` on documents, chunks, conversations, messages, feedback, audit_log and
  unanswered_questions. Existing rows were backfilled to the sample workspace.
- RLS: reads require `is_org_member(org_id)` in addition to the existing
  role/department rule. `audit_log` also requires the member's org role to be
  `admin`.
- `search_chunks_org(query_embedding, query_text, caller_org, caller_role,
  caller_department, match_count)`: the organisation predicate runs before the
  role predicate. The API switch happens in the retrieval slice.

## Applying it

`db-migrate.yml` applies every migration with `psql -v ON_ERROR_STOP=1` on push
to `main`, then runs `supabase/tests/cross_tenant.sql`. The test creates a second
organisation with a public document and chunk, assumes the `authenticated` role
with the demo admin's JWT claim, and fails if either is visible or if the sample
workspace becomes unreadable.

## Down migration

There is no automatic down file. To reverse safely:

1. Recreate the original policies from `20261111000100_init.sql` for documents,
   chunks, conversations, messages, feedback and audit_log.
2. `drop function public.search_chunks_org(...)` and the helper functions
   `public.is_org_member` and `public.current_org_role`.
3. Drop `org_id` from the seven tables, then drop `org_members`, `groups` and
   `organizations`.

Everything that moved into the sample workspace came from the single-tenant
schema, so the reverse move is a no-op once the columns are dropped.
