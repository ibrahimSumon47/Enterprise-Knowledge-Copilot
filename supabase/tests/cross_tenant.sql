-- Database-level tenant isolation check. Runs as an authenticated admin who is
-- a member of the sample workspace only; a document and chunk in another
-- organisation must be invisible.
\set ON_ERROR_STOP on
begin;

select count(*) as policy_count
from pg_policies
where schemaname = 'public'
  and policyname in ('documents_read', 'chunks_read')
\gset
\if :policy_count
\else
  \echo 'membership policies are missing'
  \quit 1
\endif

insert into public.organizations (name, slug)
values ('Isolation test', 'isolation-test')
on conflict (slug) do nothing;

select id as other_org from public.organizations where slug = 'isolation-test'
\gset

delete from public.documents where slug = 'isolation-test-document';
insert into public.documents
  (slug, title, access_level, content_hash, org_id)
values
  ('isolation-test-document', 'Other tenant document', 'public', 'hash', :'other_org');

insert into public.chunks (document_id, ordinal, content, embedding, org_id)
select id, 1, 'other tenant secret passage',
       array_fill(0::real, array[384])::vector, :'other_org'
from public.documents where slug = 'isolation-test-document';

select id as admin_id from public.profiles where email = 'admin@ekc.local'
\gset
select set_config('request.jwt.claims', json_build_object('sub', :'admin_id')::text, true);

set local role authenticated;

select count(*) as leaked_documents from public.documents where org_id = :'other_org'
\gset
\if :leaked_documents
  \echo 'FAIL: cross-tenant documents are visible'
  \quit 1
\endif

select count(*) as leaked_chunks from public.chunks where org_id = :'other_org'
\gset
\if :leaked_chunks
  \echo 'FAIL: cross-tenant chunks are visible'
  \quit 1
\endif

select count(*) as own_documents
from public.documents
where org_id = (select id from public.organizations where slug = 'sample-workspace')
\gset
\if :own_documents
  \echo 'sample workspace still readable'
\else
  \echo 'FAIL: sample workspace is unreadable to its member'
  \quit 1
\endif

rollback;
