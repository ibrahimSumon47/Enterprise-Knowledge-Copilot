-- Multi-tenant workspaces: organisations, membership and org-scoped rows.
-- Down migration note: see docs/ORGANISATIONS.md. Reversing requires dropping
-- the org_id columns and membership policies first; the backfill is lossless.

create table if not exists public.organizations (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  slug text not null unique,
  is_sample boolean not null default false,
  created_at timestamptz not null default now()
);

create table if not exists public.groups (
  id uuid primary key default gen_random_uuid(),
  org_id uuid not null references public.organizations (id) on delete cascade,
  name text not null,
  created_at timestamptz not null default now(),
  unique (org_id, name)
);

create table if not exists public.org_members (
  org_id uuid not null references public.organizations (id) on delete cascade,
  user_id uuid not null references auth.users (id) on delete cascade,
  role text not null default 'employee'
    check (role in ('guest', 'employee', 'engineering', 'security', 'hr', 'finance', 'admin')),
  department text check (department in ('engineering', 'security', 'people', 'finance')),
  group_id uuid references public.groups (id) on delete set null,
  status text not null default 'active' check (status in ('active', 'deactivated')),
  created_at timestamptz not null default now(),
  primary key (org_id, user_id)
);

insert into public.organizations (name, slug, is_sample)
values ('Sample workspace', 'sample-workspace', true)
on conflict (slug) do nothing;

alter table public.documents add column if not exists org_id uuid references public.organizations (id);
alter table public.chunks add column if not exists org_id uuid references public.organizations (id);
alter table public.conversations add column if not exists org_id uuid references public.organizations (id);
alter table public.messages add column if not exists org_id uuid references public.organizations (id);
alter table public.feedback add column if not exists org_id uuid references public.organizations (id);
alter table public.audit_log add column if not exists org_id uuid references public.organizations (id);
alter table public.unanswered_questions add column if not exists org_id uuid references public.organizations (id);

do $$
declare sample uuid;
begin
  select id into sample from public.organizations where slug = 'sample-workspace';
  update public.documents set org_id = sample where org_id is null;
  update public.chunks c set org_id = d.org_id from public.documents d
    where c.document_id = d.id and c.org_id is null;
  update public.conversations set org_id = sample where org_id is null;
  update public.messages m set org_id = c.org_id from public.conversations c
    where m.conversation_id = c.id and m.org_id is null;
  update public.feedback set org_id = sample where org_id is null;
  update public.audit_log set org_id = sample where org_id is null;
  update public.unanswered_questions set org_id = sample where org_id is null;
  insert into public.org_members (org_id, user_id, role, department)
  select sample, p.id, p.role, p.department from public.profiles p
  on conflict (org_id, user_id) do update
    set role = excluded.role, department = excluded.department;
end $$;

create index if not exists documents_org_idx on public.documents (org_id);
create index if not exists chunks_org_idx on public.chunks (org_id);
create index if not exists conversations_org_idx on public.conversations (org_id);
create index if not exists messages_org_idx on public.messages (org_id);
create index if not exists feedback_org_idx on public.feedback (org_id);
create index if not exists audit_log_org_idx on public.audit_log (org_id);
create index if not exists unanswered_questions_org_idx on public.unanswered_questions (org_id);
create index if not exists org_members_user_idx on public.org_members (user_id);

create or replace function public.is_org_member(target_org uuid)
returns boolean language sql stable security definer set search_path = public as $$
  select exists (
    select 1 from public.org_members
    where org_id = target_org and user_id = auth.uid() and status = 'active'
  );
$$;

create or replace function public.current_org_role(target_org uuid)
returns text language sql stable security definer set search_path = public as $$
  select coalesce((
    select role from public.org_members
    where org_id = target_org and user_id = auth.uid() and status = 'active'
  ), 'guest');
$$;

alter table public.organizations enable row level security;
alter table public.groups enable row level security;
alter table public.org_members enable row level security;

drop policy if exists organizations_member_read on public.organizations;
create policy organizations_member_read on public.organizations
  for select using (public.is_org_member(id));

drop policy if exists groups_member_read on public.groups;
create policy groups_member_read on public.groups
  for select using (public.is_org_member(org_id));

drop policy if exists org_members_self_read on public.org_members;
create policy org_members_self_read on public.org_members
  for select using (user_id = auth.uid() or public.is_org_member(org_id));

drop policy if exists documents_read on public.documents;
create policy documents_read on public.documents
  for select using (
    status = 'active'
    and public.is_org_member(org_id)
    and public.can_read(access_level, department)
  );

drop policy if exists chunks_read on public.chunks;
create policy chunks_read on public.chunks
  for select using (
    public.is_org_member(org_id)
    and exists (
      select 1 from public.documents d
      where d.id = chunks.document_id
        and d.status = 'active'
        and public.can_read(d.access_level, d.department)
    )
  );

drop policy if exists conversations_own on public.conversations;
create policy conversations_own on public.conversations
  for all using (user_id = auth.uid() and public.is_org_member(org_id))
  with check (user_id = auth.uid() and public.is_org_member(org_id));

drop policy if exists messages_own on public.messages;
create policy messages_own on public.messages
  for all using (
    public.is_org_member(org_id)
    and exists (
      select 1 from public.conversations c
      where c.id = messages.conversation_id and c.user_id = auth.uid()
    )
  )
  with check (
    public.is_org_member(org_id)
    and exists (
      select 1 from public.conversations c
      where c.id = messages.conversation_id and c.user_id = auth.uid()
    )
  );

drop policy if exists feedback_own on public.feedback;
create policy feedback_own on public.feedback
  for all using (user_id = auth.uid() and public.is_org_member(org_id))
  with check (user_id = auth.uid() and public.is_org_member(org_id));

drop policy if exists audit_admin_read on public.audit_log;
create policy audit_admin_read on public.audit_log
  for select using (
    public.is_org_member(org_id) and public.current_org_role(org_id) = 'admin'
  );

-- Retrieval with the organisation predicate before the role predicate. The API
-- switches to this function in the next migration; the old signature stays until
-- then so the deployed build keeps working during the rollout.
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
        caller_role = 'admin'
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
