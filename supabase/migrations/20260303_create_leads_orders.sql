create extension if not exists pgcrypto;

create table if not exists public.leads (
  id uuid primary key default gen_random_uuid(),
  full_name text not null,
  email text not null unique,
  created_at timestamptz not null default now()
);

create table if not exists public.orders (
  id uuid primary key default gen_random_uuid(),
  full_name text not null,
  email text not null,
  stripe_session_id text not null unique,
  stripe_payment_intent_id text,
  status text not null check (status in ('pending', 'paid', 'failed')) default 'pending',
  created_at timestamptz not null default now()
);
