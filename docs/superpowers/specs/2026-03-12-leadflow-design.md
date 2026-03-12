# LeadFlow — System Design Spec
**Date:** 2026-03-12
**Status:** Approved

---

## Overview

LeadFlow is a UK-focused lead generation pipeline for WidgetAI. It scrapes barbershop and hair salon listings from Yell.com, analyzes their websites, scores and personalizes each lead, and exports results to CSV/XLSX. A Next.js dashboard hosted on Vercel lets the user configure and trigger runs, watch live progress, review leads, and export outreach files.

---

## Architecture

### Two-part system

**1. Local Python pipeline (`leadflow/`)**
Runs on the user's machine. Scrapes Yell.com, visits business websites, extracts contacts, validates email domains, scores leads, and generates personalization via GPT-4o-mini. Writes all results and progress to Supabase.

**2. Next.js dashboard (`leadflow-dashboard/`)**
Hosted on Vercel. Reads from Supabase. Lets the user trigger pipeline runs, watch live progress, review and filter leads, and export CSV/XLSX.

### Coordination via Supabase job queue

- Dashboard writes a job record to Supabase `jobs` table (cities, lead limit)
- Local daemon polls for pending jobs every 10s, picks them up, runs the pipeline
- Progress events and leads stream to Supabase in real-time
- Dashboard subscribes via Supabase Realtime — live feed and lead table update as the pipeline runs

```
LOCAL MACHINE                          VERCEL (Next.js)
─────────────────────────────          ──────────────────────────
daemon.py                              /runs   — trigger + live feed
  └── polls jobs table                 /dashboard — lead table + export
  └── runs pipeline (5 async workers)
  └── writes progress_events           Supabase Realtime subscriptions
  └── writes leads
          ▲                                      ▲
          └──────────────┬───────────────────────┘
                         │
              ┌──────────▼──────────┐
              │      SUPABASE        │
              │  - jobs              │
              │  - leads             │
              │  - progress_events   │
              └─────────────────────┘
```

### Daemon operation

The daemon is run manually in a terminal before triggering jobs from the dashboard:
```
python daemon.py
```
It stays running in the background while in use. No process manager required for v1. The daemon writes a `last_seen_at` timestamp to a `daemon_status` table every 30s. The dashboard reads this to show a "Daemon online/offline" indicator so the user knows if it's running before triggering a job.

---

## Python Pipeline

### Directory structure

```
leadflow/
├── daemon.py                  # polls Supabase jobs, orchestrates runs
├── config/
│   └── settings.py            # OpenAI key, Supabase URL/key, defaults
├── src/
│   ├── discover.py            # Playwright → Yell.com scraper
│   ├── analyze_site.py        # Playwright → business website inspector
│   ├── extract_contacts.py    # email/phone extraction from pages
│   ├── validate_contacts.py   # MX/DNS checks via dnspython
│   ├── score_leads.py         # fit/confidence/priority score calc
│   ├── personalize.py         # GPT-4o-mini personalization fields
│   └── export.py              # CSV + XLSX file generation
├── db/
│   └── supabase_client.py     # shared Supabase client + write helpers
└── requirements.txt
```

### Lead lifecycle

Each lead passes through these stages, with fields added at each step:

```
discovered → analyzed → contacts_extracted → validated → scored → personalized → exported
```

Failures at any stage are logged — the lead is saved with whatever data was collected, never silently dropped.

### Concurrency

- Uses Python `asyncio` + Playwright's async API
- 5 concurrent workers process leads in a pool
- Each worker runs the full pipeline for one lead
- Personalization (GPT-4o-mini) is called inline per lead after scoring
- Conservative throughput estimate: ~100 leads in 15–25 minutes
- Random delays (1–3s between page loads) and user-agent rotation to stay polite

### Discovery source

- Primary: **Yell.com** scraped via Playwright
- Search query pattern: `"barbershop [city]"` and `"hair salon [city]"` for each selected city
- City names are trimmed and title-cased before use (e.g., "london" → "London")
- If a city returns 0 results, a `progress_event` is logged with status `info` and the pipeline moves to the next city
- Collects: business name, address, city, phone, website URL, Yell listing URL
- Deduplicates by domain and phone before passing to analysis

### Website analysis (per lead)

Pages visited: homepage, contact, about, team, booking, footer

Extracted:
- email(s), phone, booking URL, booking platform
- WhatsApp presence, contact form presence, chat/widget presence
- visible services, visible pricing
- likely decision-maker names and roles
- likely pain points

### Contact extraction priority

1. Named owner/manager with company-domain email
2. Company-domain generic email
3. Phone/contact form if no email found

### Contact validation (local only)

- Syntax check
- Domain existence check
- MX record check via `dnspython`
- Role inbox detection (info@, admin@, etc.)
- Domain-to-brand match check

No third-party email verification API. Hook points left in `validate_contacts.py` for future integration.

### Scoring

Scoring rules match the PRD exactly:

- **Fit score** — how clearly useful WidgetAI would be (positive/negative signals, 0–100)
- **Confidence score** — how strong the contact data is (0–100)
- **Priority score** — `(fit_score * 0.65) + (confidence_score * 0.35)`

Fit tiers: A (80–100), B (65–79), C (50–64), skip (<50)
Confidence tiers: high (75–100), usable (60–74), manual review (45–59), skip (<45)

### Personalization (GPT-4o-mini)

Generates three fields per lead:
- `personalization_note` — specific observation about their site/setup
- `likely_missed_lead_issue` — the core problem WidgetAI would solve for them
- `outreach_angle` — recommended first-touch angle for cold email

Model: `gpt-4o-mini` (cheapest, fast, sufficient for structured personalization)

---

## Supabase Schema

### `jobs`
| Column | Type | Notes |
|---|---|---|
| id | uuid PK | |
| status | text | pending / running / completed / failed |
| cities | text[] | |
| lead_limit | int | |
| created_at | timestamptz | |
| started_at | timestamptz | |
| completed_at | timestamptz | |
| force_refresh | boolean | default false — bypasses deduplication |

### `leads`
| Column | Type | Notes |
|---|---|---|
| id | uuid PK | |
| job_id | uuid FK → jobs | |
| stage | text | pipeline lifecycle stage |
| outreach_status | text | pending / contacted / replied / skipped — set manually via dashboard |
| created_at | timestamptz | |
| business_name | text | |
| business_type | text | barbershop / hair salon |
| city | text | |
| country | text | UK |
| website | text | |
| google_maps_url | text | |
| address | text | |
| phone | text | |
| instagram_url | text | |
| booking_url | text | |
| booking_platform | text | |
| whatsapp_present | boolean | |
| has_chat_widget | boolean | |
| has_contact_form | boolean | |
| book_now_above_fold | boolean | |
| mobile_cta_strength | text | |
| services_visible | boolean | |
| pricing_visible | boolean | |
| language_detected | text | |
| decision_maker_name | text | |
| decision_maker_role | text | |
| personal_email | text | |
| generic_email | text | |
| email_source_url | text | |
| source_type | text | yell / website |
| domain | text | |
| mx_valid | boolean | |
| mailbox_status | text | |
| catch_all | boolean | |
| role_based | boolean | |
| confidence_score | int | |
| fit_score | int | |
| priority_score | numeric | |
| likely_missed_lead_issue | text | |
| personalization_note | text | |
| outreach_angle | text | |
| pricing_fit | text | |
| last_verified_at | timestamptz | |
| notes | text | |
| yell_listing_url | text | source URL from Yell.com |

### `progress_events`
| Column | Type | Notes |
|---|---|---|
| id | uuid PK | |
| job_id | uuid FK → jobs | |
| message | text | |
| stage | text | |
| business_name | text | |
| status | text | info / success / error |
| created_at | timestamptz | |

### `daemon_status`
| Column | Type | Notes |
|---|---|---|
| id | int PK | always 1 (single row) |
| last_seen_at | timestamptz | updated every 30s by daemon |

Supabase Realtime is enabled on `leads` and `progress_events`, filtered by `job_id`.

---

## Next.js Dashboard

### Directory structure

```
leadflow-dashboard/
├── app/
│   ├── page.tsx                    # redirect to /dashboard
│   ├── dashboard/
│   │   └── page.tsx                # lead table, filters, export
│   ├── runs/
│   │   └── page.tsx                # trigger run + live progress
│   └── api/
│       └── export/
│           └── route.ts            # CSV/XLSX download endpoint
├── components/
│   ├── LeadTable.tsx               # sortable/filterable leads table
│   ├── ScoreBadge.tsx              # A/B/C tier badge
│   ├── RunForm.tsx                 # city multi-select + lead limit slider
│   ├── ProgressFeed.tsx            # live event log
│   ├── DaemonStatus.tsx            # online/offline indicator (polls daemon_status)
│   └── StatsBar.tsx                # infographic: tier breakdown, avg scores
└── lib/
    └── supabase.ts                 # Supabase client (anon key)
```

### Views

**`/runs`**
- City multi-select (predefined list of major UK cities with free-text fallback)
- Lead limit slider (50–200)
- Daemon status indicator (green/red based on `daemon_status.last_seen_at` within 60s)
- Run button → writes job to Supabase (disabled if daemon is offline)
- Live progress feed (Supabase Realtime on `progress_events`)
- Leads populate in a preview table as they arrive

**`/dashboard`**
- Full lead table with all columns
- Sort by priority score (default), fit score, confidence score
- Filter by fit tier (A/B/C), city, outreach_status
- Inline `outreach_status` update — dropdown per row (pending / contacted / replied / skipped), written directly to Supabase from the client using the anon key (RLS disabled on the leads table for v1)
- Stats bar: total leads, tier breakdown (A/B/C counts), avg priority score
- Export button: CSV or XLSX of current filtered view

### Export API

`GET /api/export`

Query parameters:
- `format` — `csv` or `xlsx`
- `fit_tier` — comma-separated e.g. `A,B`
- `city` — comma-separated e.g. `London,Manchester`
- `outreach_status` — comma-separated e.g. `pending,contacted`
- `job_id` — optional, filter to a specific run

Returns a downloadable file with headers: `Content-Disposition: attachment; filename=leadflow-export.[csv|xlsx]`

---

## Error Handling

### Per-lead failures
- Each pipeline stage wrapped in try/except
- Failed stage logged to `progress_events`, lead saved with partial data
- Playwright timeout: 15s per page

### Yell.com blocking
- Per-worker graduated backoff: on first block, pause 30s and retry
- On second block for same worker: pause 120s and retry once more
- If a worker fails 3 times: that worker stops, remaining workers continue
- Partial runs are saved — leads already scraped are kept regardless of job outcome
- Job marked `completed` (not `failed`) if at least 50% of target leads were found; otherwise `failed`

### Daemon resilience
- Polls every 10s for pending jobs
- On restart: detects stale `running` jobs (started >2hrs ago), resets to `pending`

### Deduplication
- Before saving: checks `leads` table for matching domain or phone
- Default: skip if already exists (across any job)
- Staleness window: if existing lead was scraped >30 days ago, update it in place rather than skip
- `force_refresh` job option (checkbox in RunForm) bypasses deduplication entirely

---

## Tech Stack

| Component | Technology |
|---|---|
| Pipeline language | Python 3.11+ |
| Browser automation | Playwright (async) |
| HTML parsing | BeautifulSoup4 |
| Data handling | pandas |
| XLSX export (Python) | openpyxl |
| DNS/MX validation | dnspython |
| LLM personalization | OpenAI GPT-4o-mini |
| Database | Supabase (PostgreSQL) |
| Realtime | Supabase Realtime |
| Dashboard framework | Next.js 14 (App Router) |
| Styling | Tailwind CSS |
| XLSX export (JS) | xlsx |
| Hosting | Vercel |

---

## Constraints

- No auth on dashboard (private use only)
- Pipeline runs locally — Vercel hosts UI only
- No third-party email verification API (local DNS/MX only, hookable later)
- First outreach batch: 25–50 leads manually reviewed before sending
- Target volume: 100–200 leads per run
- Daemon must be running locally before triggering a job from the dashboard
