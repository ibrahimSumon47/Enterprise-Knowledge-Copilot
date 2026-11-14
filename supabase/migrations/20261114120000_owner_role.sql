-- Owner role above admin. The creator of a workspace is its owner; an invite or
-- a settings change can never grant ownership. Only an owner may delete the
-- workspace, transfer ownership or remove an admin.

do $$
begin
  if exists (
    select 1 from pg_constraint
    where conrelid = 'public.org_members'::regclass
      and conname = 'org_members_role_check'
  ) then
    alter table public.org_members drop constraint org_members_role_check;
  end if;
end $$;

alter table public.org_members
  add constraint org_members_role_check
  check (role in ('owner', 'admin', 'guest', 'employee', 'engineering', 'security', 'hr', 'finance'));

alter table public.organizations
  add column if not exists created_by uuid references auth.users (id) on delete set null;

-- One owner per workspace is enough for the free tier; a transfer swaps the two
-- rows inside a transaction.
create unique index if not exists organizations_one_owner_idx
  on public.org_members (org_id)
  where role = 'owner';

-- The owner sees everything in the workspace, exactly like an admin.
create or replace function public.search_chunks_org(
  query_embedding vector(384),
  query_text text,
  caller_org uuid,
  caller_role text,
  caller_department text,
  match_count integer default 20
)
returns table (
  chunk_id uuid, document_id uuid, title text, heading text, content text,
  access_level text, department text, is_synthetic boolean, source_url text,
  license text, attribution text, rrf_score double precision
)
language sql stable as $$
  with allowed as (
    select d.id, d.title, d.access_level, d.department, d.is_synthetic,
           d.source_url, d.license, d.attribution
    from public.documents d
    where d.status = 'active'
      and d.org_id = caller_org
      and (
        caller_role in ('admin', 'owner')
        or (caller_role = 'guest' and d.access_level = 'public')
        or (
          caller_role <> 'guest'
          and (
            d.access_level = 'public'
            or d.access_level = 'employee'
            or (d.access_level = 'department' and d.department = caller_department)
          )
        )
      )
  ),
  vector_hits as (
    select c.id, row_number() over (order by c.embedding <=> query_embedding) as rank_v
    from public.chunks c
    join allowed a on a.id = c.document_id
    order by c.embedding <=> query_embedding
    limit 40
  ),
  text_hits as (
    select c.id,
           row_number() over (
             order by ts_rank_cd(c.tsv, plainto_tsquery('english', query_text)) desc
           ) as rank_t
    from public.chunks c
    join allowed a on a.id = c.document_id
    where query_text <> ''
      and c.tsv @@ plainto_tsquery('english', query_text)
    order by ts_rank_cd(c.tsv, plainto_tsquery('english', query_text)) desc
    limit 40
  )
  select c.id, c.document_id, a.title, c.heading, c.content, a.access_level,
         a.department, a.is_synthetic, a.source_url, a.license, a.attribution,
         coalesce(1.0 / (60 + v.rank_v), 0) + coalesce(1.0 / (60 + t.rank_t), 0) as rrf_score
  from public.chunks c
  join allowed a on a.id = c.document_id
  left join vector_hits v on v.id = c.id
  left join text_hits t on t.id = c.id
  where v.id is not null or t.id is not null
  order by rrf_score desc
  limit match_count;
$$;

drop policy if exists audit_admin_read on public.audit_log;
create policy audit_admin_read on public.audit_log
  for select using (
    public.is_org_member(org_id)
    and public.current_org_role(org_id) in ('admin', 'owner')
  );

-- The owner list is private to owners; members only see themselves.
drop policy if exists org_members_self_read on public.org_members;
create policy org_members_self_read on public.org_members
  for select using (
    user_id = auth.uid()
    or public.current_org_role(org_id) in ('admin', 'owner')
  );
