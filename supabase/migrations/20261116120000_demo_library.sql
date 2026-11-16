-- A new workspace is intentionally empty. An owner can copy the sample corpus
-- into their own workspace to explore the product without touching the shared
-- sample workspace. The copy is idempotent: the owner may click again after an
-- interrupted request without creating duplicate documents.

create or replace function public.copy_demo_library(target_org uuid, caller uuid)
returns integer
language plpgsql
security definer
set search_path = public
as $$
declare
  sample_org uuid;
  inserted integer;
begin
  select id into sample_org
  from public.organizations
  where is_sample
  order by created_at
  limit 1;

  if sample_org is null or target_org = sample_org then
    return 0;
  end if;

  if not exists (
    select 1 from public.org_members
    where org_id = target_org
      and user_id = caller
      and role = 'owner'
      and status = 'active'
  ) then
    raise exception 'owner role required' using errcode = '42501';
  end if;

  insert into public.documents (
    org_id, slug, title, source_url, license, attribution, access_level,
    department, is_synthetic, version, content_hash, status, metadata, group_id
  )
  select
    target_org,
    'demo-' || substr(md5(target_org::text || d.id::text), 1, 16),
    d.title,
    d.source_url,
    d.license,
    d.attribution,
    d.access_level,
    d.department,
    d.is_synthetic,
    1,
    d.content_hash,
    'active',
    coalesce(d.metadata, '{}'::jsonb) || jsonb_build_object(
      'demo_copy', true,
      'demo_source_id', d.id::text
    ),
    null
  from public.documents d
  where d.org_id = sample_org
    and d.status = 'active'
  on conflict (slug) do nothing;

  get diagnostics inserted = row_count;

  insert into public.chunks (
    document_id, org_id, ordinal, heading, content, token_count, embedding
  )
  select
    copied.id,
    target_org,
    source_chunk.ordinal,
    source_chunk.heading,
    source_chunk.content,
    source_chunk.token_count,
    source_chunk.embedding
  from public.chunks source_chunk
  join public.documents source_document
    on source_document.id = source_chunk.document_id
   and source_document.org_id = sample_org
  join public.documents copied
    on copied.org_id = target_org
   and copied.metadata->>'demo_source_id' = source_chunk.document_id::text
  on conflict (document_id, ordinal) do nothing;

  return inserted;
end;
$$;

revoke all on function public.copy_demo_library(uuid, uuid) from public;
grant execute on function public.copy_demo_library(uuid, uuid) to authenticated, service_role;
