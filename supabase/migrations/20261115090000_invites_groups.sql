-- Invites, group membership and group-scoped documents.

alter table public.documents
  add column if not exists group_id uuid references public.groups (id) on delete set null;
create index if not exists documents_group_idx on public.documents (group_id);

create table if not exists public.invites (
  id uuid primary key default gen_random_uuid(),
  org_id uuid not null references public.organizations (id) on delete cascade,
  token_hash text not null unique,
  role text not null check (role in ('admin', 'guest', 'employee', 'engineering', 'security', 'hr', 'finance')),
  group_id uuid references public.groups (id) on delete set null,
  created_by uuid references auth.users (id) on delete set null,
  created_at timestamptz not null default now(),
  expires_at timestamptz not null,
  max_uses integer not null default 1 check (max_uses between 1 and 100),
  use_count integer not null default 0,
  revoked_at timestamptz,
  last_used_at timestamptz
);
create index if not exists invites_org_idx on public.invites (org_id, created_at desc);
alter table public.invites enable row level security;

drop policy if exists invites_admin_read on public.invites;
create policy invites_admin_read on public.invites
  for select using (
    public.is_org_member(org_id)
    and public.current_org_role(org_id) in ('admin', 'owner')
  );

-- Invite acceptance writes one membership. SECURITY DEFINER so a signed-up
-- invitee without a membership can call it; the token hash and single-use check
-- are the authorisation.
create or replace function public.accept_invite(token_hash text)
returns uuid
language plpgsql
security definer
set search_path = public
as $$
declare
  invite public.invites%rowtype;
  caller uuid := auth.uid();
begin
  if caller is null then
    raise exception 'not authenticated';
  end if;
  select * into invite from public.invites
  where token_hash = accept_invite.token_hash
    and revoked_at is null
    and expires_at > now()
    and use_count < max_uses
  for update;
  if not found then
    raise exception 'invite is invalid, expired or used';
  end if;
  if exists (
    select 1 from public.org_members
    where org_id = invite.org_id and user_id = caller
  ) then
    raise exception 'already a member of this workspace';
  end if;
  insert into public.org_members (org_id, user_id, role, group_id, status)
  values (invite.org_id, caller, invite.role, invite.group_id, 'active');
  update public.invites
  set use_count = use_count + 1, last_used_at = now()
  where id = invite.id;
  return invite.org_id;
end;
$$;

-- Retrieval with organisation AND group predicates before the role predicate.
create or replace function public.search_chunks_grouped(
  query_embedding vector(384),
  query_text text,
  caller_org uuid,
  caller_role text,
  caller_department text,
  caller_group uuid,
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
      and (d.group_id is null or d.group_id = caller_group)
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
