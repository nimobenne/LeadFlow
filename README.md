# MentalCore PDF Store (Next.js + Supabase + Stripe)

Production-ready Vercel-compatible App Router project for selling a private digital PDF product.

## Stack

- Next.js 14+ (App Router)
- TypeScript
- Supabase Postgres + private Storage bucket
- Stripe Checkout + webhook
- Vercel serverless route handlers (`app/api/**/route.ts`)

## Setup

1. Copy env file:

```bash
cp .env.example .env.local
```

2. Fill env vars:

- `NEXT_PUBLIC_SUPABASE_URL`
- `NEXT_PUBLIC_SUPABASE_ANON_KEY`
- `SUPABASE_SERVICE_ROLE_KEY`
- `STRIPE_SECRET_KEY`
- `STRIPE_WEBHOOK_SECRET`
- `NEXT_PUBLIC_SITE_URL`
- `STRIPE_PRICE_ID`
- `SUPABASE_PDF_BUCKET` (private bucket name)
- `SUPABASE_PDF_PATH` (path to PDF in bucket)
- `SUPABASE_LEADS_TABLE` (optional; defaults to `leads`)

3. Install and run:

```bash
npm install
npm run dev
```


### Lead table name

If your Supabase table is named `email` instead of `leads`, set:

```bash
SUPABASE_LEADS_TABLE=email
```

The API also includes fallback attempts (`email`, `emails`, `leads`) to reduce setup friction.

## Required DB schema (run in Supabase SQL editor)

```sql
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
```



### If your tables already exist (add name columns)

Run this migration in Supabase SQL editor:

```sql
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
```



## Apply table changes in Supabase

You can apply migrations from the Supabase Dashboard SQL Editor using files in `supabase/migrations/`:

- `20260303_create_leads_orders.sql` (fresh setup)
- `20260303_add_name_columns.sql` (existing tables)

> Important: a **publishable key** (starts with `sb_publishable_...`) is client-side only and cannot alter database schema.
> To edit tables, use Supabase Dashboard SQL Editor or server credentials (service role / database password) in a secure environment.

## API routes

- `POST /api/lead`: saves normalized email lead, deduplicated.
- `POST /api/checkout`: creates Stripe Checkout session + pending order.
- `POST /api/stripe/webhook`: verifies Stripe signature and marks order as paid.

## Secure delivery flow

- PDF is stored in **private** Supabase bucket.
- `/success?session_id=...` checks DB for `paid` status (set only by webhook).
- If paid, app generates short-lived signed download URL.

## Vercel deployment

1. Push to GitHub.
2. Import repo in Vercel.
3. Add all env vars in Vercel Project Settings.
4. Configure Stripe webhook endpoint:
   - `https://YOUR_DOMAIN/api/stripe/webhook`
   - event: `checkout.session.completed`


## Troubleshooting Vercel deploy failures

If deployment fails, check these first:

1. **TypeScript path aliases**
   - This project imports modules using `@/...`.
   - Alias resolution must be defined in `tsconfig.json` (`baseUrl` + `paths`).

2. **Missing environment variables in Vercel**
   - Ensure all variables from `.env.example` are added in Vercel Project Settings.
   - Most frequent misses: `SUPABASE_SERVICE_ROLE_KEY`, `STRIPE_PRICE_ID`, `NEXT_PUBLIC_SITE_URL`.

3. **Supabase schema or storage setup incomplete**
   - Run the SQL schema in this README.
   - Create a **private** bucket matching `SUPABASE_PDF_BUCKET`.
   - Upload the PDF file at `SUPABASE_PDF_PATH`.

4. **Stripe webhook not configured in production**
   - Add webhook endpoint: `https://YOUR_DOMAIN/api/stripe/webhook`
   - Subscribe to `checkout.session.completed`.

### Note about MCP setup

Adding the Supabase MCP server in Codex helps assistant tooling, but it is **not required** for Vercel deployment runtime. Vercel deploys your app using project code + environment variables + external service configs.
