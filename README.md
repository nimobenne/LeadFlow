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

3. Install and run:

```bash
npm install
npm run dev
```

## Required DB schema (run in Supabase SQL editor)

```sql
create extension if not exists pgcrypto;

create table if not exists public.leads (
  id uuid primary key default gen_random_uuid(),
  email text not null unique,
  created_at timestamptz not null default now()
);

create table if not exists public.orders (
  id uuid primary key default gen_random_uuid(),
  email text not null,
  stripe_session_id text not null unique,
  stripe_payment_intent_id text,
  status text not null check (status in ('pending', 'paid', 'failed')) default 'pending',
  created_at timestamptz not null default now()
);
```

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
