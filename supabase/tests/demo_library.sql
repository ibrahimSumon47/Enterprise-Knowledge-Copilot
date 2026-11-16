-- Demo-library copy check. Runs inside one transaction and rolls back, so the
-- production sample workspace and the temporary organisation are left untouched.
\set ON_ERROR_STOP on
begin;

select id as admin_id from public.profiles where email = 'admin@ekc.local'
\gset

delete from public.organizations where slug = 'demo-copy-test';
insert into public.organizations (name, slug)
values ('Demo copy test', 'demo-copy-test');

select id as target_org from public.organizations where slug = 'demo-copy-test'
\gset

insert into public.org_members (org_id, user_id, role)
values (:'target_org', :'admin_id', 'owner');

select public.copy_demo_library(:'target_org', :'admin_id') as copied
\gset

select case when :copied > 0 then 'true' else 'false' end as copied_ok \gset

\if :copied_ok
\else
  \echo 'FAIL: the demo library copy returned no documents'
  \quit
\endif

select count(*) as copied_documents
from public.documents
where org_id = :'target_org'
  and metadata->>'demo_copy' = 'true'
\gset

select count(*) as copied_chunks
from public.chunks
where org_id = :'target_org'
\gset

select case when :copied_documents > 0 then 'true' else 'false' end as documents_ok \gset
select case when :copied_chunks > 0 then 'true' else 'false' end as chunks_ok \gset

\if :documents_ok
\else
  \echo 'FAIL: the copied documents are missing'
  \quit
\endif

\if :chunks_ok
\else
  \echo 'FAIL: the copied chunks are missing'
  \quit
\endif

select public.copy_demo_library(:'target_org', :'admin_id') as second_copy
\gset

select case when :second_copy = 0 then 'true' else 'false' end as second_ok \gset

\if :second_ok
\else
  \echo 'FAIL: a second copy duplicated the demo library'
  \quit
\endif

rollback;
