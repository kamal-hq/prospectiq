# ProspectIQ v3.0 — Automated Agency Lead Intelligence Platform

> **Live Portfolio Showcase:** **https://kamal-prospectiq.vercel.app/** *(Interactive static demo preview when logged out · Private Owner workspace with live `prospectiq.*` Realtime data when authenticated)*  
> **Owner & Engineer:** **Muhammad Kamal**  
> **Infrastructure Cost:** **$0/month** (Vercel Hobby + Shared Supabase Multi-Schema Free Tier + GitHub Actions Free Tier)

---

## Overview

**ProspectIQ v3.0** is a full-stack B2B agency prospecting and web-presence intelligence platform engineered to discover local service businesses, audit their digital footprint, extract MX-verified contact details without burning paid API credits, score agency-fit opportunity (`0–100`), and stream live leads straight into a dark/light SaaS dashboard.

Unlike basic scrapers that dump broken URLs, Facebook links, franchises, and unverified emails into spreadsheets, ProspectIQ enforces strict **anti-garbage filtering**, a **Free-First contact waterfall**, and **atomic cloud quota guards** end-to-end.

---

## Live Architecture (v3.0 Cloud Stack)

```text
Browser (Light/Dark SaaS UI — https://kamal-prospectiq.vercel.app)
  │
  ├── Logged-Out Visitors ──► 100% Static Client-Side Dummy Preview (ZERO DB queries)
  │
  └── Authenticated Owner (Single-Owner RLS via Publishable Key — ZERO service_role)
        ├── Supabase Realtime + PostgREST (`prospectiq.*` isolated schema)
        │     ├── prospectiq.leads         (scored, audited, MX-verified prospects + CRM)
        │     ├── prospectiq.scrape_jobs   (live QUEUED -> RUNNING -> COMPLETED telemetry)
        │     ├── prospectiq.target_queue  (automated pagination cursor advancement)
        │     ├── prospectiq.api_quotas    (atomic row-locked monthly quota guard)
        │     ├── prospectiq.exclusions    (aggregators, franchises, junk email domains)
        │     └── prospectiq.profiles      (lazily provisioned — zero auth.users triggers)
        │
        └── POST /api/scrape-trigger (Vercel Serverless Function)
              └── Verifies Owner JWT -> Queues job -> Dispatches GitHub Actions
                    │
                    ▼
        GitHub Actions (.github/workflows/auto-scrape.yml)
        Daily 08:00 UTC Cron + On-Demand workflow_dispatch
        Python 3.12 Engine (engine/)
          1. discovery.py  -> SerpApi Maps (pagination + full metadata) -> Brave fallback
          2. database.py   -> Pre-scrape dedup (place_id, name+city, root_domain)
          3. validator.py  -> 5-state probe (LIVE | WAF_PROTECTED | PARKED | BROKEN | NO_WEBSITE)
                              + zero-extra-request Digital Health Audit (SSL, Mobile, CMS, GA4, Meta Pixel)
          4. extractor.py  -> Free-First Waterfall: JSON-LD -> Homepage DOM -> Nav Contact links
                              -> Hunter.io fallback ONLY + cached dnspython MX check
          5. scorer.py     -> Deterministic 0–100 Opportunity Score + Pitch Angle + Pitch Brief
          6. database.py   -> Atomic `prospectiq.upsert_lead` RPC (preserves verified contacts & CRM notes)
```

---

## Key Engineering Highlights

- **Anti-Garbage Web Classification (`engine/validator.py`, `engine/discovery.py`):**
  - Splits **Social-as-Website** listings (e.g., `m.facebook.com/...` pasted as a Google Maps website) into the social column and flags `NO_WEBSITE` instead of falsely marking them `LIVE` or burning Hunter credits on `facebook.com`.
  - Distinguishes **WAF/Cloudflare `403`s** (`WAF_PROTECTED`) and **Parked Domains** (`PARKED`) from genuinely broken (`BROKEN`) or missing (`NO_WEBSITE`) sites.
  - Strips `utm_*`, `fbclid`, `gclid`, and GMB tracking query strings into clean canonical URLs, rejects permanently closed listings, and penalizes national franchises (`-40` pts).
- **Free-First Email Waterfall & MX Verification (`engine/extractor.py`):**
  - Reuses homepage HTML fetched by `validator.py` (zero double-fetching), extracts JSON-LD `LocalBusiness` + DOM `mailto:` + dynamic nav-discovered Contact/About links **before** ever touching Hunter.io (`50/mo` free cap).
  - Ranks domain-matched addresses first, filters `noreply@`/agency-footer/asset-extension junk, and verifies domain MX records via `dnspython`.
- **Stealth TLS & DNS Recovery (`engine/stealth.py`, `engine/logger.py`):**
  - Sole outbound HTTP gateway using `curl_cffi` Chrome TLS fingerprinting, log-normal human delay curves, `dnspython` public-DNS `CurlOpt.RESOLVE` recovery, and automatic secret redaction across all logs.
- **Multi-Schema Shared-Supabase Security (`supabase/prospectiq_schema.sql`):**
  - Lives exclusively inside the isolated `prospectiq` schema (zero `public.*` objects, zero triggers on shared `auth.users`).
  - Uses **publishable key (`sb_publishable_...`) + Owner JWT ONLY** across frontend, Vercel serverless API, and GitHub Actions — **never** uses `service_role`, keeping sibling co-hosted schemas strictly RLS-protected.
  - Revokes all `anon` table/sequence/function privileges and gates every table and RPC with fail-closed `prospectiq.is_owner()` Owner-UUID policies.
- **Executive SaaS Dashboard (`web/`):**
  - React 19 + TypeScript (strict) + Vite 8 + Tailwind v4 + Recharts with Light-default / Dark theme switcher, Command Center KPIs & funnel charts, multi-facet Lead Explorer with slide-over Intelligence Drawer, RFC-4180 CSV export, live Target Queue & Exclusion CRUD, and Supabase Realtime updates.

---

## Repository Structure

```text
prospectiq-main/
├── .github/workflows/
│   └── auto-scrape.yml         # Daily 08:00 UTC cron + on-demand workflow_dispatch runner
├── engine/                     # Core Python prospecting & scoring package
│   ├── config.py               # Env config, quotas, anti-garbage blacklists, URL hygiene
│   ├── logger.py               # Structured logger with mandatory query/header secret redaction
│   ├── stealth.py              # Sole HTTP gateway (curl_cffi Chrome TLS + DNS recovery)
│   ├── tracker.py              # Dual-mode quota guard (Supabase atomic RPC + JSON fallback)
│   ├── discovery.py            # SerpApi Maps + Brave fallback, pagination, social splitting
│   ├── validator.py            # 5-state probe + zero-extra-request Digital Health Audit
│   ├── extractor.py            # Free-first JSON-LD/DOM -> Hunter waterfall + MX validation
│   ├── scorer.py               # Pure deterministic 0–100 Opportunity Scorer & Pitch Engine
│   ├── models.py               # Strict Pydantic v2 data contracts
│   ├── database.py             # Dual-mode Supabase (`prospectiq.*`) + SQLite adapter
│   └── main.py                 # CLI, queue cursor advancement, & scrape_jobs orchestrator
├── supabase/
│   └── prospectiq_schema.sql   # Idempotent multi-schema DDL, Owner RLS, atomic RPCs, Realtime
├── tests/
│   ├── test_phase1_engine.py   # Offline Phase 1 anti-garbage, redaction, & UPSERT unit tests
│   └── test_phase2_cloud.py    # Offline Phase 2 cloud adapter, quota RPC, & SQL security tests
├── web/                        # React 19 + Vite 8 + Tailwind v4 Frontend + Vercel API
│   ├── api/scrape-trigger.ts   # Owner-JWT-verified GitHub Actions dispatcher (zero service_role)
│   ├── public/                 # Custom ProspectIQ Radar SVG & PNG favicons
│   ├── src/
│   │   ├── components/         # layout/, dashboard/, leads/, scraper/, settings/
│   │   ├── data/               # Static dummy dataset for logged-out portfolio visitors
│   │   └── lib/                # Schema-routed Supabase client, lazy profile loader, CSV, types
│   └── vercel.json             # Vite build & SPA rewrite config
├── main.py                     # Root CLI shim forwarding to `engine.main`
├── requirements.txt
└── .env.example
```

---

## Local Setup & Development

### 1. Python Engine (Offline Mock Mode or Cloud Sync)

```bash
git clone https://github.com/kamal-hq/prospectiq.git
cd prospectiq
python -m venv .venv
# Linux/macOS: source .venv/bin/activate | Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

- **Run unit test suite (25 offline tests, 0 API credits):**
  ```bash
  python -m unittest discover -s tests -v
  ```
- **Run offline mock pipeline (0 API credits, local SQLite fallback when Supabase vars unset):**
  ```bash
  python main.py
  ```
- **Run targeted live discovery:**
  ```bash
  python main.py --live --cities "Houston, TX" --niches "Plumbing" --max-results 10
  ```
- **Run automated cloud queue mode (used by daily GitHub Actions cron):**
  ```bash
  python main.py --live --queue --queue-limit 2 --trigger-source CRON
  ```

### 2. Web Dashboard (`web/`)

```bash
pnpm --dir web install
pnpm --dir web run dev
# Opens on http://localhost:5173/ (reads NEXT_PUBLIC_SUPABASE_* from root .env or web/.env.local)
```

Typecheck & production build:

```bash
pnpm --dir web exec tsc --noEmit
pnpm --dir web run build
```

---

## Cloud Deployment Summary ($0/Month)

1. **Supabase:** Run [`supabase/prospectiq_schema.sql`](supabase/prospectiq_schema.sql), expose `prospectiq` in **Project Settings -> Data API -> Exposed schemas**, insert your Owner `auth.uid()` into `prospectiq.app_config`, and append your localhost + Vercel `/auth/callback` URLs in **Authentication -> URL Configuration**.
2. **GitHub Actions Secrets:** Add `SERPAPI_API_KEY`, `BRAVE_API_KEY`, `HUNTER_API_KEY`, `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY` (`sb_publishable_...`), `NEXT_PUBLIC_SUPABASE_SCHEMA` (`prospectiq`), `SUPABASE_OWNER_EMAIL`, and `SUPABASE_OWNER_PASSWORD` *(no `service_role` key)*.
3. **Vercel (`Root Directory = web`):** Add `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`, `NEXT_PUBLIC_SUPABASE_SCHEMA` (**Config**) + `OWNER_SUPABASE_USER_ID` and `GITHUB_DISPATCH_TOKEN` (`Actions: Read and write` fine-grained PAT) (**Secret**).

---

## Author & License

- **Developed & Maintained by:** **Muhammad Kamal**
- **Live Showcase:** https://kamal-prospectiq.vercel.app/
- **License:** [MIT License](LICENSE)
