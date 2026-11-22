# ProspectIQ v3.0 — Engineering Rules, Guardrails & Governance (`rule.md`)

> **Applies to:** All human contributors and AI coding agents working in `prospectiq-main`.  
> **Companion Document:** Preserves and extends the hard stops in `AGENTS.md`. Never delete or weaken `AGENTS.md`.

---

## 1. Hard Stops (ALWAYS Ask User Permission First)

Before performing any of the following actions, STOP and get explicit approval from Muhammad Kamal:

1. **Governance & Architecture Docs:** Modifying `ARCHITECTURE.md`, `rule.md`, or `AGENTS.md`.
2. **External APIs & Quotas:** Changing third-party API endpoints, authentication mechanisms, pagination math, or raising monthly quota ceilings (`SERPAPI_MONTHLY_QUOTA`, `BRAVE_MONTHLY_QUOTA`, `HUNTER_MONTHLY_QUOTA`).
3. **Destructive Filesystem / Schema Operations:** Deleting files, renaming top-level directories, dropping database tables, or truncating production lead data.
4. **Live Metered Runs:** Running `--live` scrapes against production APIs without explicit user confirmation of the city/niche scope and estimated credit cost.

---

## 2. Standard Agent Workflow

1. **Read First:** At the start of any coding session, read `memory.md` (current state), `phase-doc.md` (active phase), and the relevant section of `ARCHITECTURE.md`.
2. **Plan Before Coding:** For every non-trivial feature or refactor, present a concise step-by-step plan and wait for a **"go ahead"** before modifying code.
3. **Single-Responsibility Edits:** Only modify the module whose responsibility owns the change (see Section 5 of `ARCHITECTURE.md`). Never bleed scraping logic into `main.py` or DB queries into `extractor.py`.
4. **Verify Before Declaring Done:** Run automated checks/tests (offline mock mode, unit tests, `tsc --noEmit`, build checks) and confirm zero regressions before reporting completion.
5. **Update Memory:** After every completed milestone or bug fix, append a dated entry to `memory.md` and check off completed items in `phase-doc.md`.

---

## 3. Non-Negotiable Scraping & Anti-Garbage Rules

These rules directly prevent the "Garbage In, Garbage Out" failures audited in v2.0:

### A. Stealth & HTTP Routing
- **Sole HTTP Gateway:** Every outgoing HTTP request across `discovery.py`, `validator.py`, and `extractor.py` **MUST** route through `stealth.py`. Direct imports of `requests`, `urllib.request`, or raw `curl_cffi` outside `stealth.py` are strictly forbidden.
- **Session Cohesion:** Never rotate the `User-Agent` header mid-session for a single target domain.
- **Human Timing Curves:** Never use static `time.sleep(N)` intervals for scraping requests. Use `stealth.human_delay()`.
- **No Double-Fetching:** `validator.py` must return the fetched homepage HTML so `extractor.py` reuses it without hitting the homepage a second time.

### B. Security & Secret Hygiene
- **Zero Secret Leakage in Logs:** `stealth.py` and `logger.py` **MUST** redact sensitive query parameters (`api_key`, `key`, `token`, `secret`, `password`) and authorization headers before writing any `DEBUG`/`INFO`/`ERROR` log line.
- **Zero Secrets in Git:** `.env`, `*.db`, `logs/`, and `usage_tracker.json` must remain gitignored. Never hardcode API keys or Supabase `service_role` keys in source code or frontend bundles.
- **Client-Side Isolation:** `SUPABASE_SERVICE_ROLE_KEY` and `GITHUB_DISPATCH_TOKEN` may ONLY live in GitHub Actions Secrets and Vercel server-side environment variables — NEVER prefixed with `NEXT_PUBLIC_`.
- **Multi-Schema Hub & Owner-Only Security Guard:**
  - All ProspectIQ database objects MUST live strictly inside the `prospectiq` PostgreSQL schema (never `public.*`) so sibling projects co-hosted in Supabase Project #2 never collide.
  - NEVER run `supabase db reset` or drop-schema commands on shared Supabase Project #2.
  - **Zero `anon` Database Access:** `anon` MUST have ZERO privileges on `prospectiq.*`. Logged-out visitors MUST only ever see static client-side dummy data.
  - **Owner-UUID Scoped RLS & Zero Public Sign-Up:** Do NOT build a Sign-Up / Register flow. Every RLS policy on `prospectiq.*` MUST explicitly check `auth.uid() = '<OWNER_UUID>'::uuid` (NEVER a generic `authenticated` check) so users from sibling co-hosted apps have zero access.

### C. Quota Conservation & Pre-Scrape Hygiene
- **Pre-Flight Quota Check:** Every metered API call (`serpapi`, `brave`, `hunter`) MUST call `tracker.check_and_increment()` before issuing the network request.
- **Free-First Email Waterfall:** `extractor.py` **MUST** exhaust free on-site extraction (JSON-LD + Homepage + discovered `/contact` / `/about` links) BEFORE calling Hunter.io.
- **Pre-Scrape Deduplication:** `database.py` must check `place_id`, `(business_name, city)`, AND normalized `root_domain` BEFORE calling `validator.py` or `extractor.py`.
- **Canonical URLs Only:** Strip `utm_*`, `fbclid`, `gclid`, and GMB tracking query strings before storing or deduplicating URLs.

### D. Anti-Garbage Data Classification
- **Social URLs Are NOT Websites:** If discovery returns a URL on `facebook.com`, `instagram.com`, `linkedin.com`, `yelp.com`, `linktr.ee`, `square.site`, or any directory/aggregator domain, NEVER mark `website_status = 'LIVE'` and NEVER send that domain to Hunter.io. Extract any valid social handle into the social column and classify `website_status = 'NO_WEBSITE'`.
- **WAF 403 Is NOT a Dead Website:** HTTP `403` / `503` / Cloudflare challenges MUST be classified as `website_status = 'WAF_PROTECTED'`, never `NO_WEBSITE` or `BROKEN`.
- **Parked Domains Are NOT Live Agency Sites:** Detect GoDaddy/Sedo/Namecheap parking templates and classify as `website_status = 'PARKED'`.
- **Reject Permanently Closed Businesses:** Filter out `CLOSED_PERMANENTLY` listings during discovery.
- **Email Quality & MX Verification:** Reject `noreply@`, `privacy@`, `webmaster@`, placeholder, asset-extension, and web-agency domains. Rank domain-matched addresses highest and validate domain MX records via `dnspython` before setting `email_mx_valid = True`.
- **No Silent Failures:** Every exception or block must set an explicit status enum (`BLOCKED`, `QUOTA_EXHAUSTED`, `NOT_FOUND`, `BROKEN`, `WAF_PROTECTED`) and log structured context.

---

## 4. Code Quality & Contracts

### Python (`engine/`)
- Target **Python 3.10+** with full type hints on all function signatures.
- **Strict Pydantic v2 (`ConfigDict(strict=True)`):** All inter-module lead objects must validate through `models.py` before reaching `database.py`.
- **ASCII-Safe Console Output:** Avoid raw non-ASCII emojis/box-drawing characters in Windows CLI `stdout` prints (prevents `cp1252` `UnicodeEncodeError`).
- **True UPSERT:** Use PostgreSQL `ON CONFLICT DO UPDATE` (and SQLite equivalent) so re-enrichment fills previously missing fields without wiping existing verified data or CRM notes (`outreach_status`, `outreach_notes`).

### Frontend (`web/`)
- **Next.js App Router + TypeScript (strict mode) + Tailwind CSS**.
- Mirror Supabase tables with strongly typed TypeScript interfaces in `web/src/lib/types.ts`.
- **Dual-Mode UX Integrity:** Every mutation button (`Run Scrape`, `Edit Notes`, `Change Outreach Status`, `Edit Target Queue`) must gracefully indicate read-only mode for unauthenticated portfolio visitors and execute cleanly for authenticated Admin sessions.
- Keep all UI components responsive across desktop (`1440px+`), laptop (`1280px`), and tablet/mobile viewports.

---

## 5. Git & Deployment Hygiene

- Use clean conventional commits: `feat(engine): ...`, `fix(stealth): ...`, `feat(web): ...`, `docs: ...`, `ci: ...`.
- Always test scraper changes against `--mock` locally and **Supabase Account 2 (Staging)** before pointing GitHub Actions at **Supabase Account 1 (Production)**.
- Never force-push `main`.
