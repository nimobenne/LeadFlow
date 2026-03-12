# WidgetAI PRD & Implementation Reference
**Purpose:** Reference document for Claude Code to improve the WidgetAI website and implement a lead-generation workflow for finding qualified barbershop and hair salon prospects.

---

# 1. Product Overview

## Product Name
WidgetAI

## Core Positioning
WidgetAI is a **24/7 website receptionist** for **barbershops and hair salons**.

It helps businesses:
- answer common questions instantly
- guide visitors to booking
- capture appointments after hours
- reduce manual admin work
- improve website conversion

## Core Promise
Turn more website visitors into booked appointments — 24/7.

## Core Value Proposition
WidgetAI helps barbershops and hair salons answer common questions, guide clients to booking, and capture appointments automatically — even when the shop is closed.

## Price Positioning
For UK-facing pages and outreach:
- prefer GBP pricing display
- frame pricing as “worth it if it brings in one extra booking”
- keep setup simple and low-friction
- mention cancel anytime if supported

---

# 2. Business Goal

## Primary Goal
Improve the website so it converts barbershop and hair salon owners better, and build a lead-generation workflow that finds strong-fit prospects for outreach.

## Secondary Goal
Create a repeatable system that:
- identifies businesses with clear need
- extracts high-confidence public contact information
- scores and ranks leads
- exports clean CSV/XLSX files
- supports personalized cold outreach

---

# 3. Target Market

## Recommended Initial Market
- United Kingdom
- English-speaking independent businesses

## Why UK First
- English outreach is easier
- current product/site is already English-first
- lower friction than Canada for this outbound model
- avoids broader Europe localization complexity

## Market Avoidance Note
Canada should **not** be the first cold-email market due to stricter anti-spam constraints.

## Business Type Focus
Prioritize:
- independent barbershops
- independent hair salons
- small grooming studios
- owner-led or manager-led local businesses

Deprioritize:
- chains
- franchises
- social-only businesses with no real website
- businesses with already strong booking/chat assistants

---
# 6. Ideal Customer Profile (ICP)

## Strong-Fit ICP
Independent barbershops and hair salons with:
- a real website
- no live chat or weak chat
- booking link or phone-only booking flow
- repetitive customer questions
- likely after-hours traffic
- simple admin process that could be improved

## Best-Fit Attributes
- 1 to 10 staff
- clear services listed
- local service business
- active business
- reviews / signs of demand
- website present but basic

## Low-Fit Attributes
- no website
- only Instagram / Facebook page
- chains/franchises
- already advanced booking assistant
- abandoned site
- weak online presence

---

# 7. Lead Generation Workflow PRD

## Goal
Build a workflow that finds qualified barbershop and hair salon leads and exports them into CSV/XLSX for outreach review.

## Workflow Stages
1. Campaign setup
2. Business discovery
3. Website analysis
4. Contact extraction
5. Contact validation
6. Scoring
7. Personalization generation
8. Export
9. Manual QA
10. Outreach batch testing

---

# 8. Workflow Details

## Phase 1 — Campaign Setup
Inputs:
- market = UK
- niche = barbershops + hair salons
- language = English
- business type = independent only
- lead target = configurable
- output = CSV + XLSX

## Phase 2 — Business Discovery
Sources:
1. Google Maps / local search
2. Official business websites
3. Directories only as support

Collect:
- business name
- city
- country
- website
- phone
- maps URL

Deduplicate by:
- normalized business name
- root domain
- phone number

## Phase 3 — Website Analyzer
For each website, inspect:
- homepage
- contact page
- about page
- team page
- booking page
- footer

Extract:
- email(s)
- phone number
- booking URL
- booking platform if detectable
- WhatsApp presence
- contact form presence
- chat/widget presence
- visible services
- visible pricing
- likely decision-maker names
- likely pain points

## Phase 4 — Contact Extraction
Priority order:
1. Named owner/manager with company-domain email
2. Company-domain generic email
3. Phone number/contact form if email unavailable

Look for roles:
- owner
- founder
- manager
- salon owner
- barber shop owner
- director
- operations manager

## Phase 5 — Contact Validation
Checks:
- syntax valid
- domain exists
- MX records exist
- mailbox valid if supported
- role inbox detection
- catch-all detection
- brand/domain match

Store:
- mx_valid
- mailbox_status
- catch_all
- role_based
- last_verified_at

## Phase 6 — Scoring
Calculate:
- fit_score
- confidence_score
- priority_score

## Phase 7 — Personalization Engine
Generate:
- personalization_note
- likely_missed_lead_issue
- outreach_angle

Example outputs:
- “I noticed your site relies on phone contact and a booking link, so visitors with quick questions after hours may still drop off.”
- “Your salon site looks good, but there’s no instant way for someone to ask about availability or pricing before booking.”

## Phase 8 — Export
Output files:
- widgetai_uk_barbers_salons_leads.csv
- widgetai_uk_barbers_salons_leads.xlsx

## Phase 9 — Manual QA
Review:
- top 30 leads by priority_score
- generic inbox only leads
- chat/widget detection accuracy
- brands that look too large or chain-like

## Phase 10 — Outreach Batch Testing
First send batch:
- 25 to 50 leads only

Track:
- bounce rate
- reply rate
- positive reply rate
- demo/meeting rate
- common objections

Learning loop:
1. review bounces
2. review replies
3. identify objections
4. improve scoring
5. improve outreach copy
6. tighten targeting

---

# 9. Data Model / Lead Sheet Schema

## Required Columns
- business_name
- business_type
- city
- country
- website
- google_maps_url
- address
- phone
- instagram_url
- booking_url
- booking_platform
- whatsapp_present
- has_chat_widget
- has_contact_form
- book_now_above_fold
- mobile_cta_strength
- services_visible
- pricing_visible
- language_detected
- decision_maker_name
- decision_maker_role
- personal_email
- generic_email
- email_source_url
- source_type
- domain
- mx_valid
- mailbox_status
- catch_all
- role_based
- confidence_score
- fit_score
- priority_score
- likely_missed_lead_issue
- personalization_note
- outreach_angle
- pricing_fit
- outreach_status
- last_verified_at
- notes

## Output Formats
Must support:
- CSV
- XLSX

Optional:
- Google Sheets export later
- Airtable export later

---

# 10. Scoring Model

## Fit Score
Purpose: how likely WidgetAI is clearly useful for this business.

### Positive Signals
- +20 website exists and is functional
- +15 independent shop, not a chain
- +10 English-language site
- +10 clear services / pricing / booking intent on site
- +10 mobile site is usable but basic
- +10 likely repetitive pre-booking questions
- +15 no live chat / no booking assistant
- +12 phone or contact-form only
- +12 booking link exists but weak or hidden flow
- +10 no FAQ or instant answer path
- +8 no WhatsApp / text option
- +8 no after-hours capture
- +10 premium positioning or higher-ticket services
- +8 multiple staff / chairs
- +6 visible booking link but no assistant
- +6 strong review count / active business

### Negative Signals
- -20 already has strong booking assistant / chat
- -15 chain / franchise
- -12 no real website, social-only presence
- -10 abandoned / broken site
- -8 very low-information site with no real conversion path

### Fit Tiers
- 80–100 = A
- 65–79 = B
- 50–64 = C
- below 50 = skip

## Confidence Score
Purpose: how strong the contact data is.

### Positive Signals
- +25 official website found
- +15 named owner / manager found
- +15 personal email on company domain
- +10 generic email on company domain
- +10 source URL captured
- +10 phone confirmed on site
- +10 MX valid
- +10 mailbox valid
- +5 domain matches brand exactly

### Negative Signals
- -15 generic inbox only
- -20 catch-all
- -20 unverifiable mailbox
- -25 invalid / mismatched domain
- -15 third-party directory only

### Confidence Tiers
- 75–100 = high-confidence
- 60–74 = usable
- 45–59 = manual review
- below 45 = skip

## Priority Score
Formula:
Priority score = (fit_score * 0.65) + (confidence_score * 0.35)

## Outreach Decision Rules

### Auto-approve
If:
- fit_score >= 70
- confidence_score >= 60
- official website exists
- no strong booking assistant already
- at least one usable contact route exists

### Manual Review
If:
- fit_score 60–69
- strong fit but only generic inbox
- no named contact but good business fit

### Reject
If:
- no website
- chain/franchise
- invalid or mismatched domain
- already clearly solved problem
- abandoned site

---

# 11. Pain-Point Detection Rules

## Tier 1 Pain Points
- no chat widget
- only phone number shown
- only contact form
- booking link hard to find
- no FAQ handling
- no instant response path
- no mobile-first CTA
- no quick answers for pricing / walk-ins / availability

## Tier 2 Pain Points
- no clear booking CTA above the fold
- site pushes users to Instagram for questions
- no mention of after-hours booking help
- confusing service menu
- multiple stylists but no quick routing for questions

## Tier 3 Pain Points
- outdated design
- weak mobile layout
- poor conversion flow from homepage to booking

## Outreach Angles by Pain
- missed bookings after hours
- too much manual replying
- website traffic not converting
- repetitive questions taking staff time
- visitors leaving before booking

---

# 12. Outreach Guidance

## Core Positioning for Outreach
WidgetAI is a 24/7 receptionist for barbershops and hair salons.

## Primary Outreach Promise
- answer common questions instantly
- guide visitors to booking
- capture more appointments after hours
- reduce manual admin work

## Price Framing
- low monthly price
- easy to justify if it brings one extra booking
- simple setup
- low friction

## First-Touch Angles
1. missed bookings after hours
2. less manual replying
3. better website conversion

## Base Email Direction
Hi {{first_name}},

I came across {{business_name}} and noticed {{personalization_note}}.

A lot of barbershops and hair salons lose bookings when someone visits after hours, has a quick question, and leaves before booking.

WidgetAI acts like a 24/7 website receptionist — it helps answer common questions, guide visitors to booking, and capture more appointments without adding extra work for your team.

At this price point, it usually only needs to help bring in one extra booking to be worth it.

Would you be open to seeing a quick example for your site?

Best,
{{your_name}}

---

# 13. Technical Implementation Guidance

## Confirmed Stack (decided 2026-03-12)

### Python Pipeline (runs locally)
- Playwright (async) for page browsing — Yell.com + business websites
- BeautifulSoup4 for HTML parsing
- pandas for tabular data
- openpyxl for XLSX export
- dnspython for MX/DNS validation (local only, no third-party email API)
- OpenAI GPT-4o-mini for personalization
- supabase-py for database writes

### Dashboard (hosted on Vercel)
- Next.js 14 (App Router)
- Tailwind CSS
- Supabase Realtime for live progress feed
- xlsx npm package for XLSX export

### Database
- Supabase (fresh project, separate from WidgetAI)
- Tables: jobs, leads, progress_events
- Realtime enabled on leads and progress_events

## Architecture Decision: Local Pipeline + Vercel Dashboard
The Python pipeline runs on the user's local machine (Playwright cannot run on Vercel serverless).
Coordination via Supabase job queue:
1. Dashboard writes a job record (cities, lead limit) to Supabase
2. Local daemon polls for pending jobs every 10s
3. Pipeline runs, streams progress_events and leads to Supabase in real-time
4. Dashboard subscribes via Supabase Realtime — live feed updates as pipeline runs

## Discovery Source
Primary: Yell.com (not Google Maps)
- Easier to scrape, UK-focused, structured listings
- Google Maps can be added later as an enricher

## Concurrency
5 async Playwright workers running in parallel
- Target: 100 leads in 5–10 minutes
- Random delays + user-agent rotation to stay polite

## Module Structure
```
leadflow/
├── daemon.py
├── config/settings.py
├── src/discover.py
├── src/analyze_site.py
├── src/extract_contacts.py
├── src/validate_contacts.py
├── src/score_leads.py
├── src/personalize.py
├── src/export.py
└── db/supabase_client.py

leadflow-dashboard/
├── app/dashboard/
├── app/runs/
├── app/api/export/
└── components/
```

## Key Implementation Requirements
- configurable city selection (multi-select, any UK city)
- configurable lead limit (50–200 per run)
- deduplication by domain + phone across jobs
- retry/error handling per stage (failed stage doesn't kill the lead)
- structured lead dict passed through pipeline stages
- clean CSV/XLSX export from dashboard
- deterministic score calculations
- live progress feed via Supabase Realtime
- daemon auto-recovers stale jobs on restart

## Internal Pipeline Contract
Each lead passes through stages with fields added at each step:
1. discovered
2. analyzed
3. contacts_extracted
4. validated
5. scored
6. personalized
7. exported

---

# 14. Constraints / Guardrails

## Lead Quality Principles
This is not a mass-blast tool.
It is a lead qualification workflow.

Prioritize:
- better fit
- lower bounce risk
- stronger personalization
- smaller but better lead batches

## Data Integrity Rules
Always store:
- source URL
- source type
- verification timestamp
- confidence score
- notes if uncertain

## Human Review Rules
Before outreach, always manually review:
- highest-priority leads
- generic inbox-only leads
- possible chain businesses
- uncertain chat/widget detection

---

# 15. Deliverables for Claude Code

## Website Deliverables
1. update landing page copy to support both barbershops and hair salons
2. revise hero copy and supporting sections
3. improve pricing presentation for UK audience
4. strengthen problem/ROI messaging
5. add segment examples for barbers and salons
6. improve CTA structure

## Workflow Deliverables
1. build lead discovery workflow
2. build website analyzer
3. build contact extraction logic
4. build validation logic
5. build scoring engine
6. build personalization output
7. build CSV/XLSX export
8. create a first-batch QA checklist

## Optional Later Deliverables
- booking platform detection
- CRM sync
- suppression list management
- region-specific landing pages
- owner vs manager outreach variants

---

# 16. Immediate Next Build Priority

Priority order:
1. improve landing page copy and positioning
2. define exact data structures for leads
3. implement discovery + analysis pipeline
4. implement scoring + export
5. generate outreach-ready personalization fields

---

# 17. Success Criteria

## Website Success
- clearer fit for both barbershops and hair salons
- stronger conversion messaging
- less confusion around who the product is for
- better pricing clarity for UK visitors

## Workflow Success
- produces clean lead files
- surfaces high-fit independent shops
- ranks leads clearly
- generates usable personalization
- supports small-batch outreach testing

---

# 18. Final Instruction to Claude Code

Use this document as the source of truth for:
- website copy and structure improvements
- target market assumptions
- lead qualification logic
- workflow implementation
- scoring rules
- export format
- personalization requirements

If tradeoffs arise, optimize for:
1. clarity of offer
2. lead quality
3. simplicity of implementation
4. outreach usability
5. future extensibility