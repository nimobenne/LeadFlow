alter table public.leads
  add column if not exists full_name text;

update public.leads
set full_name = coalesce(full_name, 'Unknown')
where full_name is null;

alter table public.leads
  alter column full_name set not null;

alter table public.orders
  add column if not exists full_name text;

update public.orders
set full_name = coalesce(full_name, 'Unknown')
where full_name is null;

alter table public.orders
  alter column full_name set not null;
