-- Workspace identity and admin analytics inputs.
alter table public.organizations
  add column if not exists logo_url text,
  add column if not exists accent_color text not null default '#2563eb'
    check (accent_color ~ '^#[0-9A-Fa-f]{6}$'),
  add column if not exists allowed_domains text[] not null default '{}';
