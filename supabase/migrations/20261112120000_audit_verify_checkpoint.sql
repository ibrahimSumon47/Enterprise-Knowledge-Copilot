-- Incremental audit verification: the last row a verified run reached.
-- One row only; verification advances it and never moves it backwards.
create table if not exists public.audit_verify_checkpoint (
  id boolean primary key default true check (id),
  last_id bigint not null,
  head text not null,
  entries bigint not null,
  anchored_at_genesis boolean not null default true,
  updated_at timestamptz not null default now()
);

alter table public.audit_verify_checkpoint enable row level security;
