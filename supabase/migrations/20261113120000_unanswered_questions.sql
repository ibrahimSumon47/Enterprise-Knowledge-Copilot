-- Questions the copilot refused, so an admin can close the knowledge gap.
create table if not exists public.unanswered_questions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references auth.users(id) on delete set null,
  role text,
  question text not null,
  reason text,
  closest jsonb not null default '[]'::jsonb,
  created_at timestamptz not null default now(),
  resolved_at timestamptz,
  resolved_by uuid references auth.users(id) on delete set null
);

create index if not exists unanswered_questions_open_idx
  on public.unanswered_questions (created_at desc)
  where resolved_at is null;

alter table public.unanswered_questions enable row level security;

-- The API reads and writes this table with the service role. No policy is
-- granted to anon or authenticated, so RLS denies direct client access.
