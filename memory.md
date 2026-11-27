# ProspectIQ — Project Memory & Decision Log (`memory.md`)

> **Purpose:** Persistent cross-session memory capturing current state, locked architectural decisions, audited bugs, and next actions. Update after every completed phase or major decision.

---

## 1. Current Project Snapshot

- **Last Updated:** 2026-11-27
- **Active Workspace:** `C:\Users\Asif Computers\Desktop\TriSyn Media\prospectiq-main`
- **Current Version on Disk:** v3.0 Production Launch Complete (`engine/` + `web/` + `supabase/` + `.github/workflows/` + `tests/` + v3.0 `README.md`)
- **Target Version:** v3.0 (Garbage-Free Agency Prospecting Engine + `shared-apps` Supabase Postgres/Auth/Realtime `prospectiq.*` + GitHub Actions Auto-Scraper + Vercel Dashboard)
- **Active Phase:** **All 4 MVP Phases Complete & Live at `https://kamal-prospectiq.vercel.app/`** -> 102-lead live production audit passed (`0%` social/UTM/franchise leaks, `95.7%` MX valid, `58.6%` free-first email savings, 4 consecutive daily cron runs green), round-robin queue & timeout/enterprise scorer calibrations applied, dynamic KPI badges & v3.0 `README.md` shipped.

---

## 2. Locked-In Product & Architecture Decisions

| Date | Decision | Rationale |
| :--- | :--- | :--- |
| 2026-11-22 | **Hybrid Agency Tool + Portfolio Showcase** | Primary goal is winning real agency clients (web design, SEO, marketing) for Muhammad Kamal while keeping a clean dummy-data portfolio preview on Vercel. |
| 2026-11-22 | **Shared Supabase Project `shared-apps` (`https://hlxkgikqmljthjsbhzhq.supabase.co`) — Publishable Key Only & Zero `auth.users` Triggers** | Co-hosted alongside live sibling app **Cadence** (`https://kamal-cadence.vercel.app`, schema `cadence`). Exposed schemas: `public, cadence, prospectiq`. Confirmed Owner account: `muhammad.kamal.hq@gmail.com` (`auth.uid() = bc477ad2-5f94-451a-a186-f89caac09cb6`). Strictly ZERO `public.*` objects, ZERO `cadence.*` edits, ZERO triggers on shared `auth.users` (lazy idempotent `prospectiq.profiles` upsert instead), and **PUBLISHABLE KEY (`sb_publishable_...`) ONLY** across frontend, Vercel, `.env`, and GitHub Actions (Owner Auth JWT + `prospectiq.is_owner()` RLS/RPC guards; NEVER use `service_role` so `cadence.*` stays protected). |
| 2026-11-22 | **Strictly Single-Owner Real Data + Dummy-Data Public Experience** | No public signup flow. Only Muhammad Kamal (exact Supabase `auth.uid()`) can read/write real data in `prospectiq.*` (`anon` has ZERO DB grants). Unauthenticated visitors landing on the live site interact with 100% static client-side dummy data to experience the full product safely. |
| 2026-11-22 | **GitHub Actions for Automated Scraping** | Avoids Vercel Hobby's 10s serverless timeout & ephemeral disk. Runs Python 3.12 + `curl_cffi` natively via both cron schedule and UI-triggered `workflow_dispatch`. |
| 2026-11-22 | **Figma Make Vite SPA + Vercel Serverless Functions** | Figma export (`Design ProspectIQ SaaS Dashboard`) is React 19 + TypeScript + Vite 8 + Tailwind v4 with 1:1 `BusinessLead` types. Keeping Vite + Vercel `/api/scrape-trigger.ts` avoids unnecessary Next.js rewrite while keeping pixel-identical UI and secure server-side GitHub dispatch. |
| 2026-11-22 | **5-File Workflow Practice Adopted** | Standard project workflow driven by `ARCHITECTURE.md`, `rule.md`, `phase-doc.md`, `design.md`, and `memory.md` (preserving existing `AGENTS.md` hard stops). |
| 2026-11-22 | **Free-First Contact Waterfall** | Flipped `extractor.py` to run JSON-LD + Homepage + Nav Contact scraping BEFORE Hunter.io (50/mo) so free Hunter credits stretch 4–5× further. |

---

## 3. Phase 1 Implementation Log (`2026-11-22`)

All 6 audited v2.0 bugs + secret leak have been fixed in code:
- `config.py`: Added centralized `AGGREGATOR_DOMAINS`, `SOCIAL_ONLY_WEBSITE_DOMAINS`, `FRANCHISE_BRANDS`, `PARKED_DOMAIN_SIGNATURES`, `EMAIL_DOMAIN_BLACKLIST`, `EMAIL_LOCAL_BLACKLIST_PREFIXES`, `TRACKING_QUERY_PARAMS`, `SECRET_QUERY_PARAMS`.
- `logger.py` & `stealth.py`: Added `SecretRedactingFilter` + `redact_url()` (no plaintext API keys in `logs/app.log`); fixed `curl: (6)` DNS resolution via `dnspython` -> `CurlOpt.RESOLVE` + `www.` toggle fallback + HTTPS SSL fallback to HTTP.
- `models.py`: Added strict Pydantic v2 models (`RawCandidate`, `SiteAudit` with `exclude=True` on `html_body`, `ContactEnrichment`, `LeadScore`, and full v3.0 `BusinessLead`).
- `discovery.py`: Added full SerpApi Maps metadata (`place_id`, `phone`, `address`, `rating`, `reviews_count`, `business_status`), `start` pagination, permanently-closed filtering, franchise flagging, Social-as-Website splitting (`m.facebook.com` -> `facebook` social + `NO_WEBSITE`), and aggregator filtering on BOTH SerpApi and Brave.
- `validator.py`: Added 5-state classification (`LIVE`, `WAF_PROTECTED`, `PARKED`, `BROKEN`, `NO_WEBSITE`), UTM stripping, zero-extra-request Digital Health Audit (SSL, mobile viewport, CMS, GA/GTM, Meta Pixel, load time), and `html_body` handoff.
- `extractor.py`: Flipped to Free-First waterfall (JSON-LD -> Homepage DOM -> max 2 nav-discovered Contact/About pages -> Hunter.io fallback ONLY), agency/noreply filtering, domain-matched ranking, cached `dnspython` MX validation, and brand-checked DDG social fallback.
- `scorer.py`: Created deterministic 0–100 Opportunity Scorer (`HOT`/`WARM`/`COLD`), `pitch_angle`, and factual `pitch_summary`.
- `database.py` & `main.py`: Added safe additive `ALTER TABLE` SQLite migration, pre-scrape `place_id`/`(name,city)`/`root_domain` dedup, true `ON CONFLICT DO UPDATE` UPSERT preserving CRM notes, `--max-results`/`--start` CLI flags, and `tests/test_phase1_engine.py`.

**Verification & Bug Fixes Completed (`2026-11-22`):**
1. `extractor.py` & `discovery.py`: Fixed `_clean_social_url()` / `_clean_social_profile()` to strip `www.`, `m.`, and `mobile.` subdomains consistently (e.g., `https://www.instagram.com/...` -> `https://instagram.com/...`).
2. `database.py`: Wrapped all `sqlite3.connect()` calls with `contextlib.closing()` to prevent open-handle `[WinError 32]` file lock errors on Windows during temp DB cleanup.
3. `extractor.py` & `tests/test_phase1_engine.py`: Added `EMAIL_DOMAIN_BLACKLIST` check to `_query_hunter_api()` so blacklisted/mock domains (`example.com`, `example.org`, etc.) never burn Hunter.io credits; added unit test `test_blacklisted_domain_never_calls_hunter_or_burns_quota`.
4. `logger.py`: Wrapped `FileHandler` initialization in `try/except OSError` for graceful console fallback in read-only environments.
5. **Verified Green:**
   - `python -m unittest tests/test_phase1_engine.py -v` -> **16/16 tests PASSED** (`0.050s`).
   - `python main.py` (offline mock mode) -> **Exit 0**, migrated 64-row legacy `leads.db` (+23 v3.0 columns), processed 2 new HOT leads (`Bayou City Rooter` 85/`NO_WEBSITE`, `Plumb Masters TX` 95/`SOCIAL_ONLY` via `m.facebook.com` split), skipped 3 pre-scrape domain duplicates (`example.com`, `httpbin.org`, `example.org`), **0 API credits used**, **0 leaked secrets** in `logs/app.log`.

---

## 3b. Phase 2 Implementation Log (`2026-11-22`)

All Phase 2 code, SQL schema, CI workflow, and offline cloud tests are implemented & updated to the exact `shared-apps` multi-schema contract (`https://hlxkgikqmljthjsbhzhq.supabase.co`, co-hosted with `cadence`):
- `supabase/prospectiq_schema.sql`: 100% idempotent DDL strictly scoped to `prospectiq.*` (zero `public.*` objects, zero `CREATE EXTENSION`, zero `cadence.*` edits, zero triggers on `auth.users`). Creates `app_config`, `profiles` (lazily provisioned), `scrape_jobs`, `leads`, `target_queue`, `api_quotas`, `exclusions`; applies exact PostgREST grants (`GRANT USAGE ON SCHEMA prospectiq TO anon, authenticated, service_role`, table/sequence/function grants to `authenticated, service_role`, `REVOKE ALL` on tables/sequences/functions from `PUBLIC, anon`); enforces fail-closed `prospectiq.is_owner()` Owner-UUID RLS across all tables AND inside all 3 atomic RPCs (`upsert_lead`, `check_and_increment_quota`, `advance_target_cursor`) so Owner JWT works with zero `service_role`; wires `supabase_realtime` idempotently; seeds starter `target_queue` & `exclusions`.
- `config.py` & `database.py`: Publishable-key-only Supabase client factory (`SUPABASE_URL`/`NEXT_PUBLIC_SUPABASE_URL`, `SUPABASE_ANON_KEY`/`NEXT_PUBLIC_SUPABASE_ANON_KEY` [`sb_publishable_...`], `SUPABASE_SCHEMA`/`NEXT_PUBLIC_SUPABASE_SCHEMA=prospectiq`, `SUPABASE_OWNER_EMAIL`, `SUPABASE_OWNER_PASSWORD`) with repo-root `supabase/` shadow-safe import, Owner JWT sign-in, lazy idempotent `prospectiq.profiles` upsert (`on_conflict="id"`), and automatic SQLite fallback offline.
- `tracker.py`: Upgraded `check_and_increment()` to call owner-gated atomic `prospectiq.check_and_increment_quota` RPC in cloud mode with local `usage_tracker.json` fallback; added `get_monthly_usage()`.
- `main.py`: Added `--queue`, `--queue-limit`, `--job-id`, `--trigger-source` CLI flags, live `scrape_jobs` progress/finalization streaming, `target_queue` cursor advancement (`+20`), GitHub Actions run URL capture, and comma-safe JSON/pipe city parsing (`_parse_multi_value_arg`).
- `.github/workflows/auto-scrape.yml`: Daily `08:00 UTC` cron (`--live --queue --queue-limit 2`) + `workflow_dispatch` using **publishable key + Owner Auth ONLY** (ZERO `SUPABASE_SERVICE_ROLE_KEY`).
- `requirements.txt` & `.env.example`: Pinned `supabase>=2.15.0` (full `sb_publishable_...` support) and documented `NEXT_PUBLIC_SUPABASE_*` + Owner Auth vars with explicit warning never to store `service_role`.
- `tests/test_phase2_cloud.py`: Verified **25/25 OK** across Phase 1 & Phase 2 including publishable-key Owner sign-in, lazy `profiles` upsert, and full static audit of `prospectiq_schema.sql` & `auto-scrape.yml`.

## 3c. Monorepo Industry-Grade Cleanup (`2026-11-22`)

- Renamed `Design ProspectIQ SaaS Dashboard/` -> `web/`; removed Figma Make boilerplate (`.figma/`, `.mise.toml`, `.gitattributes`, nested `AGENTS.md`, `CLAUDE.md`) and stale `unicode_report.txt`.
- Replaced 452-line Figma Make `vite.config.ts` with clean 20-line Vite 8 + React + Tailwind v4 config (`port: 5173`, `@/` alias), cleaned `web/index.html`, renamed `web/package.json` to `prospectiq-web`, and organized `web/src/` into `components/{layout,dashboard,leads,scraper,settings}/`, `data/mockLeads.ts`, and `lib/types.ts`.
- Moved all 11 Python backend modules into `engine/` package (`config.BASE_DIR` anchored to repo root) with thin root `main.py` shim preserving `python main.py` & GitHub Actions compatibility; updated `.gitignore` for `web/node_modules/`, `web/dist/`, `.vercel/`.
- **Live `shared-apps` Cloud Smoke Test Verified (`2026-11-22`, 0 API credits spent):** Authenticated via `sb_publishable_...` + Owner JWT (`muhammad.kamal.hq@gmail.com`, `service_role_key=False`), lazily provisioned `prospectiq.profiles` (`1 ['owner']`), read `prospectiq.target_queue`, `prospectiq.exclusions`, `prospectiq.api_quotas`, and `prospectiq.leads` through `prospectiq.is_owner()` RLS with zero errors.

## 3d. Phase 3 Implementation Log (`2026-11-22`)

- `web/vite.config.ts`, `web/src/vite-env.d.ts`, `web/vercel.json`: Configured `envDir` + `envPrefix: ["VITE_", "NEXT_PUBLIC_"]` so `NEXT_PUBLIC_SUPABASE_*` env vars work identically locally and on Vercel (zero private keys exposed to browser), plus clean SPA rewrite excluding `/api/*`.
- `web/src/lib/supabase.ts` & `web/src/lib/prospectiqApi.ts`: Built publishable-key-only Supabase client routed to `{ db: { schema: getSupabaseSchema() } }` (`prospectiq`), lazy `ensureOwnerProfile()` upsert (`onConflict: "id"`, rejects non-owner `shared-apps` users cleanly via RLS), live workspace loader, CRM/queue/exclusion mutations, Supabase Realtime subscriptions on `leads` & `scrape_jobs`, and RFC-4180 CSV exporter.
- `web/api/scrape-trigger.ts`: Vercel Serverless Function verifying Owner JWT via publishable key + `OWNER_SUPABASE_USER_ID` (ZERO `service_role`), creating `QUEUED` `prospectiq.scrape_jobs` row under Owner JWT, and dispatching `.github/workflows/auto-scrape.yml`.
- Wired all views (`App.tsx`, `AuthModal.tsx`, `Sidebar.tsx`, `TopBar.tsx`, `Dashboard.tsx`, `LeadTable.tsx`, `LeadDrawer.tsx`, `ScraperView.tsx`, `SettingsView.tsx`, `QuotaGuard.tsx`) with strict logged-out static dummy preview (`mockLeads.ts`, `mockWorkspace.ts`, zero DB calls) vs logged-in Owner live `prospectiq.*` workspace.
- `web/src/components/layout/AuthModal.tsx`: Removed accidentally prefilled owner email & internal `shared-apps`/`prospectiq.*` copy from public modal; audited entire codebase (`web/src/**`, `web/api/*`, `engine/*`, `supabase/*`) confirming 0 hardcoded personal emails or UIDs.
- **Dark / Light Theme Switch (`2026-11-23`):** Added Sun/Moon toggle in `TopBar.tsx`, persisted `prospectiq-theme` in `localStorage` defaulting to **Light theme** with zero-flicker bootstrap in `web/index.html`, built full high-contrast `[data-theme="light"]` token + component theme in `web/src/index.css`, and made Recharts/QuotaGuard accents theme-aware.
- Verified green: `pnpm --dir web exec tsc --noEmit` (0 errors), `pnpm --dir web run build` (`1.91s`), `python -m unittest discover -s tests -v` (25/25 OK).
- **Git Checkpoint:** Commit `fb4192d` pushed to `origin/main` (`https://github.com/kamal-hq/prospectiq`). Includes Phase 3 live Supabase wiring, Light-default theme switch, ProspectIQ Radar SVG+PNG favicon (`8b7502e`), `scrape-trigger.ts` `VITE_SUPABASE_*` fallback & exact missing-var diagnostics (`cc41eed`), and `auto-scrape.yml` `NEXT_PUBLIC_SUPABASE_*` secret fallback + CI ephemeral-SQLite guardrail (`fb4192d`).
- **First Live End-to-End Scrape Verified (`2026-11-23`):** Dispatched via `https://kamal-prospectiq.vercel.app/` -> `/api/scrape-trigger` -> GitHub Actions -> `shared-apps` (`prospectiq.*`) -> Realtime UI: **10 verified leads**, **1 HOT (`NO_WEBSITE`)**, **7 MX-verified emails (100% deliverability)**, **0 garbage**.

## 3e. Phase 4 Live 102-Lead Audit & Production Launch Polish (`2026-11-27`)

- **Live 102-Lead Audit (`shared-apps` `prospectiq.*`, 0 credits spent):**
  - `102` live leads across `7` completed runs (`4` autonomous daily `CRON` + `3` `MANUAL_UI`): `NO_WEBSITE=13`, `BROKEN=3`, `LIVE=69`, `WAF_PROTECTED=17`.
  - Precision benchmarks: **0** social/aggregator-as-website leaks, **0** UTM/tracking leaks, **0** franchise false-HOT leads, **67/70 (95.7%)** MX-valid emails, **41/70 (58.6%)** found 100% free via JSON-LD/DOM (only `17/250` SerpApi & `45/50` Hunter calls used across 102 leads).
- **Audit-Driven Production Fixes:**
  - `engine/database.py`: Fixed `fetch_next_targets()` round-robin starvation (`last_scraped_at ASC NULLS FIRST, priority ASC`) so Dallas Roofing, Miami Landscaping, Atlanta Auto Detailing, and San Antonio Plumbing rotate fairly instead of starving behind priority 1 & 2.
  - `engine/scorer.py`: Calibrated `BROKEN (TIMEOUT)` sites to pitch `REDESIGN_SSL` (not false `NO_WEBSITE`) and added `-25` mega-enterprise penalty for `reviews_count >= 2500` (prevents 11k-review enterprises like `Village Plumbing` from crowding out SMB HOT pitches); added unit test in `tests/test_phase1_engine.py`.
  - Cleaned up stale Run #1 `QUEUED` `scrape_jobs` row (`06e69720-e3dc-4aec-a12b-c2d79d4ab2a2`) on `shared-apps` so live Sidebar accurately shows `Worker online / Cron`.
- **Dashboard & Portfolio Polish:**
  - `web/src/components/dashboard/KpiCard.tsx` & `Dashboard.tsx`: Replaced static `↗ 12.4%` placeholder with live dynamic telemetry badges (`Live`, `${hotPct}%`, `${mxPct}% MX`, `${repliedDeals} replied`).
  - `README.md`: Rewrote for v3.0 showcasing `https://kamal-prospectiq.vercel.app/`, `$0/month` cloud architecture, anti-garbage highlights, and monorepo setup.

---

## 4. Forensic Audit Findings (v2.0 Bugs Resolved in Phase 1)

1. **[SECURITY — URGENT]** `stealth.py` logged full Hunter.io URLs containing plaintext `HUNTER_API_KEY` into `logs/app.log` (line 1064+). **Action:** Redact query secrets in `stealth.py`/`logger.py` and user should rotate the Hunter API key.
2. **[GARBAGE DATA]** `discovery.py` skipped `AGGREGATOR_DOMAINS` filtering in `_search_serpapi()`. Result: `m.facebook.com/plumb.masters/` was saved as a LIVE website, burned a Hunter credit on `domain=facebook.com`, and scraped `facebook.com/contact`.
3. **[FALSE DEAD SITES]** `stealth.py` tried `pycurl.DNS_SERVERS` (`pycurl` not installed) and discarded `dnspython` pre-resolved IPs -> dozens of live Texas businesses failed with `curl: (6) Could not resolve host`. Meanwhile `validator.py` classified Cloudflare `403`s (`serviceexperts.com`) as `Website DEAD`.
4. **[DISCARDED MAPS DATA + NO PAGINATION]** `discovery.py` discarded `phone`, `address`, `rating`, `reviews_count`, `place_id`, and `business_status` from SerpApi, and lacked `start` pagination (re-runs burned credits fetching the same top 10 duplicates).
5. **[LATE DEDUP + FAKE UPSERT]** Domain dedup ran *after* Hunter.io + 5 page scrapes (`reliantplumbing.com` burned 2 Hunter calls). `upsert_lead()` used `INSERT OR IGNORE` instead of `ON CONFLICT DO UPDATE`.
6. **[DOUBLE-FETCH & WEAK CONTACT HYGIENE]** `validator.py` discarded fetched HTML (forcing `extractor.py` to re-fetch homepage), blindly probed 4 hardcoded paths, ignored JSON-LD `LocalBusiness`, didn't verify email MX records, and stored raw `?utm_*` tracking URLs.

---

## 5. Historical Baseline (Pre-Revamp)
- `2026-08-23`: v2.0 pre-commit audit completed — updated `.gitignore` (SQLite, logs, `.env`, `usage_tracker.json`) and rewrote `README.md` for v2.0.
- `2026-08-23`: Last recorded local quota usage (`usage_tracker.json` for `2026-08`): SerpApi `8/250`, Brave `1/1000`, Hunter `22/50`.

---

## 6. Post-MVP Backlog (Optional Stretch Features)

1. **Optional Governance Doc Sync (Requires User Approval per `AGENTS.md` Hard Stops):**
   - Sync `ARCHITECTURE.md` & `rule.md` to replace legacy `SUPABASE_SERVICE_ROLE_KEY` & Next.js references with the final `shared-apps` publishable-key + Vite `web/` architecture.
2. **Optional Stretch Features (`phase-doc.md` Task 4.3):**
   - Instant **Discord / Telegram Hot-Lead Webhook Alerts** when nightly cron discovers `opportunity_score >= 85` leads.
   - Free-tier **AI Cold Email / Loom Pitch Opener Generator** inside `LeadDrawer` (Gemini / Groq free API grounded in live audit signals).
3. **Monthly Reminder (`2026-12-23`):** Rotate `GITHUB_DISPATCH_TOKEN` fine-grained PAT in Vercel before its Dec 23, 2026 expiration date.
