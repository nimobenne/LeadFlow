# LeadFlow

UK barbershop & hair salon lead generation pipeline for WidgetAI.

Finds qualified prospects on Yell.com, analyzes their websites, scores them, generates personalized outreach copy, and exports clean CSV/XLSX files for cold email campaigns.

---

## Architecture

```
pipeline/        Python pipeline — runs locally on your machine
dashboard/       Next.js dashboard — hosted on Vercel
supabase/        Database schema
```

The pipeline runs on your local machine (needs Playwright/browser automation). The dashboard on Vercel reads from Supabase and lets you trigger runs, watch live progress, and export leads.

---

## Setup

### 1. Supabase

Create a new Supabase project at [supabase.com](https://supabase.com).

Run the schema in the SQL editor:
```
supabase/schema.sql
```

### 2. Python pipeline

```bash
cd pipeline
python -m venv .venv
source .venv/bin/activate   # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
playwright install chromium

cp .env.example .env
# Fill in SUPABASE_URL, SUPABASE_KEY, OPENAI_API_KEY
```

Run the daemon:
```bash
python daemon.py
```

Keep it running in a terminal while using the dashboard.

### 3. Dashboard (local dev)

```bash
cd dashboard
npm install
cp .env.example .env.local
# Fill in NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_ANON_KEY

npm run dev
```

### 4. Deploy dashboard to Vercel

Connect this repo to Vercel. Set root directory to `dashboard`. Add env vars:
- `NEXT_PUBLIC_SUPABASE_URL`
- `NEXT_PUBLIC_SUPABASE_ANON_KEY`

---

## Usage

1. Start the daemon locally: `python pipeline/daemon.py`
2. Open the dashboard (Vercel URL or localhost:3000)
3. Go to **New Run**, select UK cities, set lead limit, click **Start Run**
4. Watch leads populate in real-time on the same page
5. Go to **Dashboard** to review, filter by fit tier, update outreach status
6. Export CSV or XLSX for your outreach tool

---

## Lead scoring

| Tier | Fit Score | Meaning |
|------|-----------|---------|
| A | 80–100 | Strong fit, auto-approve for outreach |
| B | 65–79 | Good fit, worth reviewing |
| C | 50–64 | Possible fit, manual review |
| — | <50 | Skip |

Priority score = (fit_score × 0.65) + (confidence_score × 0.35)

---

## First outreach batch

Review top 30 leads by priority score before sending. Start with 25–50 leads only. Track bounce rate and reply rate before scaling.
