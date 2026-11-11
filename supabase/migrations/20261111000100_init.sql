-- Enterprise Knowledge Copilot — initial schema.
-- Access control is enforced twice: in the retrieval query predicate and in RLS.

create extension if not exists vector;
create extension if not exists pg_trgm;

-- ---------------------------------------------------------------------------
-- profiles: one row per auth user, written by the backend with the service key
-- ---------------------------------------------------------------------------
create table if not exists public.profiles (
  id uuid primary key references auth.users (id) on delete cascade,
  email text not null,
  full_name text,
  role text not null default 'employee'
    check (role in ('guest', 'employee', 'engineering', 'security', 'hr', 'finance', 'admin')),
  department text check (department in ('engineering', 'security', 'people', 'finance')),
  created_at timestamptz not null default now()
);

-- ---------------------------------------------------------------------------
-- documents and chunks
-- ---------------------------------------------------------------------------
create table if not exists public.documents (
  id uuid primary key default gen_random_uuid(),
  slug text not null unique,
  title text not null,
  source_url text,
  license text not null default 'CC BY-SA 4.0',
  attribution text not null default 'GitLab Handbook',
  access_level text not null
    check (access_level in ('public', 'employee', 'department', 'confidential')),
  department text check (department in ('engineering', 'security', 'people', 'finance')),
  is_synthetic boolean not null default false,
  version integer not null default 1,
  content_hash text not null,
  status text not null default 'active' check (status in ('active', 'archived')),
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint documents_department_required
    check (access_level <> 'department' or department is not null)
);

create table if not exists public.chunks (
  id uuid primary key default gen_random_uuid(),
  document_id uuid not null references public.documents (id) on delete cascade,
  ordinal integer not null,
  heading text,
  content text not null,
  token_count integer not null default 0,
  embedding vector(384) not null,
  tsv tsvector generated always as (
    to_tsvector('english', coalesce(heading, '') || ' ' || content)
  ) stored,
  created_at timestamptz not null default now(),
  unique (document_id, ordinal)
);

create index if not exists chunks_embedding_idx
  on public.chunks using hnsw (embedding vector_cosine_ops);
create index if not exists chunks_tsv_idx on public.chunks using gin (tsv);
create index if not exists chunks_document_idx on public.chunks (document_id);
create index if not exists documents_access_idx
  on public.documents (access_level, department, status);

-- ---------------------------------------------------------------------------
-- conversations and messages
-- ---------------------------------------------------------------------------
create table if not exists public.conversations (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users (id) on delete cascade,
  title text not null default 'New conversation',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.messages (
  id uuid primary key default gen_random_uuid(),
  conversation_id uuid not null references public.conversations (id) on delete cascade,
  role text not null check (role in ('user', 'assistant')),
  content text not null,
  citations jsonb not null default '[]'::jsonb,
  confidence text check (confidence in ('high', 'medium', 'refused')),
  refused boolean not null default false,
  latency_ms integer,
  token_count integer,
  provider text,
  created_at timestamptz not null default now()
);

create index if not exists messages_conversation_idx
  on public.messages (conversation_id, created_at);

create table if not exists public.feedback (
  id uuid primary key default gen_random_uuid(),
  message_id uuid not null references public.messages (id) on delete cascade,
  user_id uuid not null references auth.users (id) on delete cascade,
  rating smallint not null check (rating in (-1, 1)),
  reason text,
  created_at timestamptz not null default now(),
  unique (message_id, user_id)
);

-- ---------------------------------------------------------------------------
-- audit log: hash chained, append only
-- ---------------------------------------------------------------------------
create table if not exists public.audit_log (
  id bigserial primary key,
  prev_hash text not null,
  entry_hash text not null,
  actor_id uuid,
  actor_role text,
  action text not null,
  resource_type text not null,
  resource_id text,
  outcome text not null default 'ok' check (outcome in ('ok', 'denied', 'refused', 'error')),
  ip_hash text,
  detail jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists audit_log_created_idx on public.audit_log (created_at desc);

-- ---------------------------------------------------------------------------
-- operational tables
-- ---------------------------------------------------------------------------
create table if not exists public.rate_events (
  id bigserial primary key,
  user_id uuid not null,
  created_at timestamptz not null default now()
);
create index if not exists rate_events_user_time_idx
  on public.rate_events (user_id, created_at desc);

create table if not exists public.ingest_jobs (
  id uuid primary key default gen_random_uuid(),
  status text not null default 'queued'
    check (status in ('queued', 'running', 'done', 'failed')),
  progress integer not null default 0 check (progress between 0 and 100),
  stats jsonb not null default '{}'::jsonb,
  error text,
  created_by uuid,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.eval_runs (
  id uuid primary key default gen_random_uuid(),
  mode text not null default 'subset' check (mode in ('subset', 'full')),
  commit_sha text,
  metrics jsonb not null default '{}'::jsonb,
  passed boolean not null default false,
  created_at timestamptz not null default now()
);

-- Permission-aware answer cache: the key includes the access scope, so a
-- privileged answer can never be served to a less privileged caller.
create table if not exists public.answer_cache (
  cache_key text primary key,
  access_scope text not null,
  answer jsonb not null,
  created_at timestamptz not null default now()
);

-- ---------------------------------------------------------------------------
-- access helpers (security definer so RLS policies can read the profile)
-- ---------------------------------------------------------------------------
create or replace function public.current_role_name()
returns text
language sql
stable
security definer
set search_path = public
as $$
  select coalesce((select role from public.profiles where id = auth.uid()), 'guest');
$$;

create or replace function public.current_department()
returns text
language sql
stable
security definer
set search_path = public
as $$
  select coalesce((select department from public.profiles where id = auth.uid()), '');
$$;

create or replace function public.can_read(level text, dept text)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select case public.current_role_name()
    when 'admin' then true
    when 'guest' then level = 'public'
    else case
      when level = 'public' then true
      when level = 'employee' then true
      when level = 'department' then dept is not null and dept = public.current_department()
      when level = 'confidential' then false
      else false
    end
  end;
$$;

-- ---------------------------------------------------------------------------
-- row level security
-- ---------------------------------------------------------------------------
alter table public.profiles enable row level security;
alter table public.documents enable row level security;
alter table public.chunks enable row level security;
alter table public.conversations enable row level security;
alter table public.messages enable row level security;
alter table public.feedback enable row level security;
alter table public.audit_log enable row level security;
alter table public.rate_events enable row level security;
alter table public.ingest_jobs enable row level security;
alter table public.eval_runs enable row level security;
alter table public.answer_cache enable row level security;

drop policy if exists profiles_self_read on public.profiles;
create policy profiles_self_read on public.profiles
  for select using (id = auth.uid() or public.current_role_name() = 'admin');

drop policy if exists documents_read on public.documents;
create policy documents_read on public.documents
  for select using (status = 'active' and public.can_read(access_level, department));

drop policy if exists chunks_read on public.chunks;
create policy chunks_read on public.chunks
  for select using (
    exists (
      select 1 from public.documents d
      where d.id = chunks.document_id
        and d.status = 'active'
        and public.can_read(d.access_level, d.department)
    )
  );

drop policy if exists conversations_own on public.conversations;
create policy conversations_own on public.conversations
  for all using (user_id = auth.uid()) with check (user_id = auth.uid());

drop policy if exists messages_own on public.messages;
create policy messages_own on public.messages
  for all using (
    exists (
      select 1 from public.conversations c
      where c.id = messages.conversation_id and c.user_id = auth.uid()
    )
  )
  with check (
    exists (
      select 1 from public.conversations c
      where c.id = messages.conversation_id and c.user_id = auth.uid()
    )
  );

drop policy if exists feedback_own on public.feedback;
create policy feedback_own on public.feedback
  for all using (user_id = auth.uid()) with check (user_id = auth.uid());

drop policy if exists audit_admin_read on public.audit_log;
create policy audit_admin_read on public.audit_log
  for select using (public.current_role_name() = 'admin');

drop policy if exists eval_read on public.eval_runs;
create policy eval_read on public.eval_runs
  for select using (auth.uid() is not null);

drop policy if exists ingest_admin_read on public.ingest_jobs;
create policy ingest_admin_read on public.ingest_jobs
  for select using (public.current_role_name() = 'admin');

-- ---------------------------------------------------------------------------
-- hybrid retrieval with the permission predicate inside the query
-- ---------------------------------------------------------------------------
create or replace function public.search_chunks(
  query_embedding vector(384),
  query_text text,
  caller_role text,
  caller_department text,
  match_count integer default 20
)
returns table (
  chunk_id uuid,
  document_id uuid,
  title text,
  heading text,
  content text,
  access_level text,
  department text,
  is_synthetic boolean,
  source_url text,
  license text,
  attribution text,
  rrf_score double precision
)
language sql
stable
as $$
  with allowed as (
    select d.id, d.title, d.access_level, d.department, d.is_synthetic, d.source_url, d.license, d.attribution
    from public.documents d
    where d.status = 'active'
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
    select c.id,
           row_number() over (order by c.embedding <=> query_embedding) as rank_v
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
  select c.id,
         c.document_id,
         a.title,
         c.heading,
         c.content,
         a.access_level,
         a.department,
         a.is_synthetic,
         a.source_url,
         a.license,
         a.attribution,
         coalesce(1.0 / (60 + v.rank_v), 0) + coalesce(1.0 / (60 + t.rank_t), 0) as rrf_score
  from public.chunks c
  join allowed a on a.id = c.document_id
  left join vector_hits v on v.id = c.id
  left join text_hits t on t.id = c.id
  where v.id is not null or t.id is not null
  order by rrf_score desc
  limit match_count;
$$;
