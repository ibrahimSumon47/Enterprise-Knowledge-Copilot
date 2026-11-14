-- Browser uploads: original in Storage, parsing state on the document, and a
-- per-user upload rate. Originals are private and path-prefixed by organisation.

alter table public.documents
  add column if not exists uploaded_by uuid references auth.users (id) on delete set null,
  add column if not exists file_size bigint not null default 0,
  add column if not exists storage_path text,
  add column if not exists mime_type text,
  add column if not exists progress integer not null default 0,
  add column if not exists error text;

do $$
begin
  if exists (
    select 1 from pg_constraint
    where conrelid = 'public.documents'::regclass
      and conname = 'documents_status_check'
  ) then
    alter table public.documents drop constraint documents_status_check;
  end if;
end $$;

alter table public.documents
  add constraint documents_status_check
  check (status in ('active', 'archived', 'processing', 'failed'));

create table if not exists public.upload_events (
  id bigint generated always as identity primary key,
  user_id uuid not null references auth.users (id) on delete cascade,
  org_id uuid not null references public.organizations (id) on delete cascade,
  created_at timestamptz not null default now()
);
create index if not exists upload_events_user_time_idx
  on public.upload_events (user_id, created_at);
alter table public.upload_events enable row level security;

-- Private bucket. Objects live at <org_id>/<document_id>/<safe-file-name>.
insert into storage.buckets (id, name, public)
values ('documents', 'documents', false)
on conflict (id) do update set public = false;

drop policy if exists documents_storage_read on storage.objects;
create policy documents_storage_read on storage.objects
  for select using (
    bucket_id = 'documents'
    and public.is_org_member(((storage.foldername(name))[1])::uuid)
  );

drop policy if exists documents_storage_write on storage.objects;
create policy documents_storage_write on storage.objects
  for insert with check (
    bucket_id = 'documents'
    and public.is_org_member(((storage.foldername(name))[1])::uuid)
    and public.current_org_role(((storage.foldername(name))[1])::uuid)
      in ('owner', 'admin', 'employee', 'engineering', 'security', 'hr', 'finance')
  );

drop policy if exists documents_storage_delete on storage.objects;
create policy documents_storage_delete on storage.objects
  for delete using (
    bucket_id = 'documents'
    and public.current_org_role(((storage.foldername(name))[1])::uuid) in ('owner', 'admin')
  );
