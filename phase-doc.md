# ProspectIQ v3.0 — 4-Phase Migration & Revamp Roadmap (`phase-doc.md`)

> **Goal:** Transform ProspectIQ from a local CLI scraper with data-quality bugs into a garbage-free, automated, 100% free-tier cloud agency prospecting & portfolio platform (GitHub Actions + Supabase + Vercel).

---

## Phase Overview

| Phase | Focus | Primary Target | Status |
| :--- | :--- | :--- | :--- |
| **Phase 1** | Core Engine Overhaul & "Garbage In, Garbage Out" Fixes | Local Python Engine | `[x] Verified & Complete` |
| **Phase 2** | Supabase Cloud Migration & GitHub Actions Auto-Scraper | Cloud DB + CI/CD Automation | `[~] Live Cloud Verified — Pending GitHub Secrets & CI Smoke Run` |
| **Phase 3** | Figma Pro Frontend Integration & Vercel Deployment | `web/` Vite + Vercel Functions | `[ ] Not Started` |
| **Phase 4** | Production QA, Scoring Calibration & Portfolio Launch | Full Stack + Live Data Audit | `[ ] Not Started` |

---

## Phase 1: Core Engine Overhaul & Garbage-Data Elimination

**Objective:** Fix every single data-quality, DNS, quota-waste, and security bug identified in the v2.0 forensic audit — verified locally before touching the cloud.

### Tasks
- [x] **1.1 Security Fix (Immediate):** Add URL/header query-parameter secret redaction (`api_key`, `token`, `key`) to `stealth.py` and `logger.py`. *(User still needs to rotate exposed `HUNTER_API_KEY`.)*
- [x] **1.2 Fix DNS & Validation Accuracy (`stealth.py`, `validator.py`):**
  - Fix the `curl: (6) Could not resolve host` bug by resolving via `dnspython` public DNS and passing `CurlOpt.RESOLVE` + `www.` toggle recovery.
  - Strip all `utm_*`, `fbclid`, `gclid`, and GMB query tracking junk into clean canonical URLs.
  - Upgrade website classification to 5 states: `LIVE`, `WAF_PROTECTED` (403/503/Cloudflare), `PARKED` (GoDaddy/Sedo/Namecheap parking detection), `BROKEN` (404/5xx/DNS dead), `NO_WEBSITE`.
  - Return the fetched HTML body from `validator.py` (`SiteAudit.html_body`, excluded from serialization) to eliminate homepage double-fetching.
  - Add zero-extra-request **Digital Health Audit** inside `validator.py`: `has_ssl`, `is_mobile_friendly`, `cms_platform`, `has_analytics`, `has_meta_pixel`, `load_time_ms`.
- [x] **1.3 Rich & Clean Discovery (`discovery.py`):**
  - Capture full SerpApi Google Maps fields: `place_id`, `phone`, `address`, `rating`, `reviews_count`, `business_status`.
  - Filter out permanently closed businesses (`CLOSED_PERMANENTLY`) and apply `AGGREGATOR_DOMAINS` filtering to **both** SerpApi and Brave results.
  - Implement **Social-as-Website splitting**: route `facebook.com`/`instagram.com` GBP website links straight to social fields and set `website_url = None` (`NO_WEBSITE`).
  - Add `start` pagination parameter support + franchise/chain flag detection (`is_franchise`).
- [x] **1.4 Precision Contact Extraction (`extractor.py`):**
  - Flip waterfall to **Free-First**: JSON-LD (`application/ld+json`) + Homepage HTML -> dynamic `<a href>` Contact/About nav link discovery (max 2 fetches) -> **Hunter.io fallback ONLY if still missing**.
  - Never query Hunter.io for blacklisted/social/aggregator domains.
  - Implement email ranking (domain-matched > business-matched generic > discard `noreply`/privacy/webmaster/agency domains) + **MX record check via `dnspython`**.
  - Harden social link extraction (`sameAs` priority + reject post/share/agency-footer URLs + DDG brand-token check).
- [x] **1.5 Agency Opportunity Scorer & Data Contracts (`scorer.py`, `models.py`):**
  - Create `scorer.py` computing `opportunity_score` (0–100), `pitch_tier` (`HOT`/`WARM`/`COLD`), `pitch_angle`, and human-readable `pitch_summary`.
  - Expand `models.py` with strict-typed `RawCandidate`, `SiteAudit`, `ContactEnrichment`, `LeadScore`, and `BusinessLead`.
- [x] **1.6 Pre-Scrape Dedup & True UPSERT (`database.py`, `main.py`):**
  - Move `root_domain` + `place_id` deduplication *before* `validator.py` and `extractor.py`.
  - Replace `INSERT OR IGNORE` with true `ON CONFLICT DO UPDATE` preserving non-null enriched fields and CRM notes, plus safe `ALTER TABLE` migration for existing `leads.db`.
  - Add offline unit test suite `tests/test_phase1_engine.py`.

### Phase 1 Definition of Done (DoD)
- [x] Offline `--mock` run passes with 0 errors and populates full Digital Audit + Opportunity Scores (verified `python main.py`: migrated 64-row v2.0 `leads.db`, inserted 2 scored hot leads, skipped 3 pre-scrape domain duplicates, 0 API credits spent).
- [x] Unit tests verify: social-as-website splitting, `403 -> WAF_PROTECTED`, UTM stripping, secret redaction in logs, MX check, free-before-Hunter order, blacklisted-domain Hunter guard, and true UPSERT preserving CRM notes (`16/16` passing in `tests/test_phase1_engine.py`).
- [ ] *(Optional before Phase 4, requires explicit user confirmation per `rule.md`)* A small controlled `--live` test (1 city × 1 niche, ~10 leads) produces 0 false `facebook.com` websites, 0 leaked API keys in logs, and accurate live/WAF classification.

---

## Phase 2: Supabase Cloud DB & GitHub Actions Auto-Scraper

**Objective:** Eliminate local-only storage (`leads.db`, `usage_tracker.json`) and automate hands-free daily scraping + on-demand runs using 100% free tiers.

### Tasks
- [~] **2.1 Supabase Provisioning (`shared-apps` Multi-Schema Hub — `https://hlxkgikqmljthjsbhzhq.supabase.co`, `prospectiq` Schema):**
  - [x] Authored idempotent, hub-safe `supabase/prospectiq_schema.sql` matching the exact `shared-apps` contract alongside live sibling app `cadence` (`https://kamal-cadence.vercel.app`):
    - Strictly scoped to `prospectiq.*` (zero `public.*` objects, zero `CREATE EXTENSION`, zero `cadence.*` edits, zero `db reset`).
    - Zero triggers on shared `auth.users` — `prospectiq.profiles` is lazily provisioned via idempotent `upsert(..., { onConflict: "id" })`.
    - Explicit PostgREST schema grants (`GRANT USAGE ON SCHEMA prospectiq TO anon, authenticated, service_role`, table/sequence/function grants to `authenticated, service_role`, `REVOKE ALL` on tables/sequences/functions from `PUBLIC, anon`).
    - Fail-closed `prospectiq.is_owner()` UUID-scoped RLS on all tables + owner-gated atomic RPCs (`upsert_lead`, `check_and_increment_quota`, `advance_target_cursor`) so publishable key + Owner JWT works with **zero `service_role` key** anywhere.
    - Idempotent Realtime wiring on `prospectiq.leads` and `prospectiq.scrape_jobs`, plus starter `target_queue` & `exclusions` seeds.
  - [x] **User Provisioning Step (on `shared-apps`):**
    1. Ran `supabase/prospectiq_schema.sql` in `shared-apps` SQL Editor.
    2. Appended `prospectiq` in **Project Settings -> Data API -> Exposed schemas** -> `public, cadence, prospectiq`.
    3. Configured Muhammad Kamal's Owner UID (`bc477ad2-5f94-451a-a186-f89caac09cb6`) in `prospectiq.app_config`.
    4. Appended `http://localhost:5173/auth/callback` in **Authentication -> URL Configuration -> Redirect URLs** (preserving Cadence URLs).
  - [x] **Monorepo Cleanup:** Organized backend into `engine/` (with root `main.py` shim) and cleaned Figma Make export into `web/` (removed `.figma/`, boilerplate files, bloated Vite plugins).
- [x] **2.2 Cloud Persistence Adapters (`config.py`, `database.py`, `tracker.py`, `main.py`, `requirements.txt`, `.env.example`):**
  - Added dual-mode Supabase PostgREST (`supabase>=2.15.0`, targeting `client.schema(get_supabase_schema())`) using **publishable key (`sb_publishable_...`) + Owner Auth JWT ONLY** (zero `service_role` key anywhere; immune to local `supabase/` folder import shadowing), with lazy `prospectiq.profiles` upsert and automatic SQLite fallback offline.
  - Migrated `tracker.py` to owner-gated atomic `prospectiq.check_and_increment_quota` RPC with local `usage_tracker.json` fallback.
  - Added `scrape_jobs` lifecycle tracking (`QUEUED -> RUNNING -> COMPLETED/PARTIAL/FAILED`), `target_queue` pagination cursor advancement (`next_page_offset += 20`), CLI `--queue`/`--queue-limit`/`--job-id`/`--trigger-source` flags, and comma-safe JSON/pipe city parsing.
  - Added offline Phase 2 test suite `tests/test_phase2_cloud.py` (25/25 tests passing across Phase 1 & Phase 2).
- [x] **2.3 GitHub Actions Automation (`.github/workflows/auto-scrape.yml`):**
  - Configured daily `08:00 UTC` cron (`--live --queue --queue-limit 2 --trigger-source CRON`) to respect free quotas and keep `shared-apps` active.
  - Configured `workflow_dispatch` inputs (`mode`, `cities`, `niches`, `max_results`, `start`, `queue_limit`, `job_id`, `trigger_source`) passed safely via `env:` with `concurrency` guard.
  - [ ] **User Secrets Step:** Add GitHub Secrets (`SERPAPI_API_KEY`, `BRAVE_API_KEY`, `HUNTER_API_KEY` [rotated], `SUPABASE_URL`, `SUPABASE_ANON_KEY` [`sb_publishable_...`], `SUPABASE_OWNER_EMAIL`, `SUPABASE_OWNER_PASSWORD`, optional `SUPABASE_SCHEMA=prospectiq`). **Do NOT add `service_role` key.**

### Phase 2 Definition of Done (DoD)
- Manual GitHub Actions `workflow_dispatch` run executes cleanly against Staging Supabase, advances `target_queue.next_page_offset`, logs stats to `scrape_jobs`, updates `api_quotas`, and writes verified scored leads to `leads`.
- Scheduled cron trigger verified active on Production Supabase.

---

## Phase 3: Figma Pro Frontend Integration & Vercel Deployment

**Objective:** Generate the high-craft UI in Figma Pro using the prompt in `design.md`, integrate it into `web/`, connect Supabase + GitHub dispatch, and deploy live on Vercel.

### Tasks
- [ ] **3.1 Generate & Import Frontend (`web/`):**
  - Generate UI screens in Figma Pro using the exact prompt in `design.md`.
  - Scaffold Next.js App Router + TypeScript + Tailwind in `web/` and integrate exported Figma Pro components cleanly.
- [ ] **3.2 Supabase Data & Realtime Wiring:**
  - Build SSR + Client Supabase helpers (`@supabase/ssr`).
  - Wire **Command Center** KPIs, conversion funnel, quota meters, and recent jobs feed.
  - Wire **Lead Explorer** server-backed search, multi-facet filtering, sorting, pagination, bulk CSV export, and inline Outreach Status updates.
  - Wire **Lead Intelligence Drawer** (Digital Health Audit, Copy Email/Phone, Outreach Notes save, Re-Enrich action).
  - Wire Supabase Realtime subscription so new leads and job progress update live without page refresh.
- [ ] **3.3 On-Demand Scraper Bridge & Single-Owner Auth Gate:**
  - Create `/api/scrape/trigger` Next.js Route Handler: verifies authenticated Supabase JWT AND checks `user.id === OWNER_SUPABASE_USER_ID` -> inserts `QUEUED` row in `prospectiq.scrape_jobs` -> calls GitHub Actions `workflow_dispatch` API.
  - Implement **Dummy-Data Public Showcase vs. Private Owner Workspace:**
    - **No Public Sign-Up:** Login modal supports `signInWithPassword` only (for Muhammad Kamal's single pre-created Owner account).
    - **Logged-Out Visitors:** Render 100% static curated client-side dummy data with full interactive demo UX (filters, drawer, simulated scrape) and ZERO Supabase DB calls.
    - **Logged-In Owner:** Switches seamlessly to live `prospectiq.*` Supabase data, Realtime job streams, CRM notes/status saves, and real GitHub Actions triggers.
- [ ] **3.4 Vercel Free Hobby Deployment:**
  - Connect GitHub repo to Vercel with Root Directory set to `web/` (skip Vercel's optional "Supabase Integration" button and add env vars manually).
  - Add Vercel environment variables: `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY` (`sb_publishable_...`), `NEXT_PUBLIC_SUPABASE_SCHEMA=prospectiq` (all Type = `Config`, NOT `Secret`), plus server-side `OWNER_SUPABASE_USER_ID`, `GITHUB_DISPATCH_TOKEN`, `GITHUB_REPO_OWNER`, `GITHUB_REPO_NAME` (**NEVER** add `service_role` key).
  - Append localhost & production Vercel `/auth/callback` URLs to `shared-apps` Supabase Auth -> URL Configuration -> Redirect URLs (preserving `cadence` URLs) and pass explicit `redirectTo` / `emailRedirectTo` in all Auth calls.

### Phase 3 Definition of Done (DoD)
- Live production URL on `*.vercel.app` loads cleanly on desktop and mobile.
- Unauthenticated visitors experience the full interactive UI powered strictly by static dummy data — zero real agency leads leaked and zero DB calls made.
- Signing in as Muhammad Kamal (Owner UUID) unlocks real `prospectiq.*` Supabase data, CRM notes, and live GitHub Actions scrape dispatching with Realtime job streaming.

---

## Phase 4: Production QA, Calibration & Agency Launch

**Objective:** Verify data precision at scale, polish UX edge cases, and add high-ROI agency outreach accelerators.

### Tasks
- [ ] **4.1 100-Lead Live Quality Audit:**
  - Scrape 100+ leads across 3 high-value US agency niches (e.g., Plumbing, Roofing, HVAC).
  - Audit precision benchmarks: `< 2%` false `NO_WEBSITE` classifications, `0%` social-as-website leaks, `> 90%` MX-valid emails, `0` franchise false-hot scores.
  - Calibrate `scorer.py` weights based on real agency conversion criteria.
- [ ] **4.2 Production Hardening & Documentation:**
  - Lighthouse performance & accessibility sweep on Vercel deployment.
  - Update `README.md` with live Vercel demo link, screenshots, and v3.0 cloud architecture badges.
- [ ] **4.3 Optional High-Impact Stretch Features (Post-MVP):**
  - Free-tier AI Cold Email / Loom Opener Generator per lead (using Gemini / Groq free API grounded in the lead's actual Digital Audit signals).
  - Instant Hot-Lead Webhook Alerts (Discord / Telegram notification whenever an `opportunity_score >= 90` lead is discovered by the nightly cron).

### Phase 4 Definition of Done (DoD)
- System runs hands-free on daily cron, generating clean, agency-ready client prospects every week at **$0/month** infrastructure cost, while serving as a flagship live portfolio showcase.
