-- LeadFlow Supabase Schema
-- Run this in your Supabase SQL editor to set up the database

-- Enable UUID extension
create extension if not exists "uuid-ossp";

-- Jobs table
create table if not exists jobs (
  id uuid primary key default uuid_generate_v4(),
  status text not null default 'pending' check (status in ('pending', 'running', 'completed', 'failed')),
  cities text[] not null,
  lead_limit int not null default 100,
  force_refresh boolean not null default false,
  created_at timestamptz not null default now(),
  started_at timestamptz,
  completed_at timestamptz
);

-- Leads table
create table if not exists leads (
  id uuid primary key default uuid_generate_v4(),
  job_id uuid references jobs(id) on delete cascade,
  stage text not null default 'discovered',
  outreach_status text not null default 'pending' check (outreach_status in ('pending', 'contacted', 'replied', 'skipped')),
  created_at timestamptz not null default now(),

  -- Business info
  business_name text,
  business_type text,
  city text,
  country text default 'UK',
  website text,
  google_maps_url text,
  address text,
  phone text,
  instagram_url text,
  yell_listing_url text,

  -- Booking & contact
  booking_url text,
  booking_platform text,
  whatsapp_present boolean,
  has_chat_widget boolean,
  has_contact_form boolean,
  book_now_above_fold boolean,
  mobile_cta_strength text,

  -- Content signals
  services_visible boolean,
  pricing_visible boolean,
  language_detected text,

  -- Decision maker
  decision_maker_name text,
  decision_maker_role text,
  personal_email text,
  generic_email text,
  email_source_url text,
  source_type text,
  domain text,

  -- Validation
  mx_valid boolean,
  mailbox_status text,
  catch_all boolean,
  role_based boolean,
  last_verified_at timestamptz,

  -- Scores
  confidence_score int,
  fit_score int,
  priority_score numeric,
  pricing_fit text,

  -- Personalization
  likely_missed_lead_issue text,
  personalization_note text,
  outreach_angle text,

  -- Meta
  notes text
);

-- Progress events table
create table if not exists progress_events (
  id uuid primary key default uuid_generate_v4(),
  job_id uuid references jobs(id) on delete cascade,
  message text not null,
  stage text,
  business_name text,
  status text not null default 'info' check (status in ('info', 'success', 'error')),
  created_at timestamptz not null default now()
);

-- Daemon status table (single row, always id=1)
create table if not exists daemon_status (
  id int primary key default 1,
  last_seen_at timestamptz not null default now()
);
insert into daemon_status (id, last_seen_at) values (1, now()) on conflict (id) do nothing;

-- Enable Realtime on leads and progress_events
alter publication supabase_realtime add table leads;
alter publication supabase_realtime add table progress_events;

-- Unique constraint for upsert deduplication in pipeline
-- Must be a full (non-partial) index — PostgREST cannot use partial indexes as conflict targets
create unique index if not exists leads_domain_city_unique on leads(domain, city);

-- Indexes for common query patterns
create index if not exists leads_job_id_idx on leads(job_id);
create index if not exists leads_priority_score_idx on leads(priority_score desc);
create index if not exists leads_fit_score_idx on leads(fit_score desc);
create index if not exists leads_outreach_status_idx on leads(outreach_status);
create index if not exists leads_city_idx on leads(city);
create index if not exists progress_events_job_id_idx on progress_events(job_id);
create index if not exists progress_events_created_at_idx on progress_events(created_at);
