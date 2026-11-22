# ProspectIQ — Project Memory & Decision Log (`memory.md`)

> **Purpose:** Persistent cross-session memory capturing current state, locked architectural decisions, audited bugs, and next actions. Update after every completed phase or major decision.

---

## 1. Current Project Snapshot

- **Last Updated:** 2026-11-22
- **Active Workspace:** `C:\Users\Asif Computers\Desktop\TriSyn Media\prospectiq-main`
- **Current Version on Disk:** v3.0 Clean Monorepo (`engine/` Python package + root `main.py` shim + `web/` clean React 19/Vite 8/Tailwind v4 frontend + `supabase/prospectiq_schema.sql` + `.github/workflows/auto-scrape.yml` + `tests/`)
- **Target Version:** v3.0 (Garbage-Free Agency Prospecting Engine + `shared-apps` Supabase Postgres/Auth/Realtime `prospectiq.*` + GitHub Actions Auto-Scraper + Vercel Dashboard)
- **Active Phase:** **Phase 2 Cloud Connection Verified Live on `shared-apps` (`prospectiq.*`) & Monorepo Clean (`25/25` tests green)** -> Committing & pushing to `kamal-hq/prospectiq` so user can configure GitHub Secrets and proceed to Phase 3 (`web/` live Supabase + Vercel).

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

## 6. Immediate Next Actions

1. **User Action (Run on Live `shared-apps` Supabase — `https://hlxkgikqmljthjsbhzhq.supabase.co`):**
   - Paste & run `supabase/prospectiq_schema.sql` in `shared-apps` SQL Editor.
   - **Project Settings -> Data API -> Exposed schemas:** append `prospectiq` so it becomes `public, cadence, prospectiq` (do NOT remove `cadence`!).
   - **Authentication -> Users:** reuse your existing Cadence account UID (same email works across both apps!) and run the 1-line `INSERT INTO prospectiq.app_config (key, value) VALUES ('owner_user_id', '<UID>') ...`.
   - **Authentication -> URL Configuration -> Redirect URLs:** APPEND localhost & Vercel `/auth/callback` URLs without deleting Cadence's URLs.
2. **User Action (Security & GitHub Secrets — ZERO `service_role`!):**
   - Rotate exposed `HUNTER_API_KEY` (previously logged in v2.0 `logs/app.log`).
   - Add `SERPAPI_API_KEY`, `BRAVE_API_KEY`, `HUNTER_API_KEY`, `SUPABASE_URL`, `SUPABASE_ANON_KEY` (`sb_publishable_...`), `SUPABASE_OWNER_EMAIL`, `SUPABASE_OWNER_PASSWORD` (and optional `SUPABASE_SCHEMA=prospectiq`) to GitHub Repository Secrets.
3. **Optional Governance Sync (Pending User Go Ahead per `AGENTS.md` Hard Stops):** Update `ARCHITECTURE.md` & `rule.md` to replace legacy `SUPABASE_SERVICE_ROLE_KEY` references with this exact `shared-apps` publishable-key contract.
4. **Next Build Step (Phase 3):** Build `web/` Supabase client factories (`{ db: { schema: getSupabaseSchema() } }`, lazy `prospectiq.profiles` provisioning, explicit `redirectTo` callbacks, manual Vercel env vars with `Config` type for `NEXT_PUBLIC_*`) + integrate `Design ProspectIQ SaaS Dashboard/`!
