# System Architecture & Technical Documentation

## Version 2.0 — Redesigned Architecture

> ⚠️ **Agent Instruction:** Before modifying any file, read this document in full. Every module has a defined single responsibility. Do not add logic to a module that belongs in another. Do not bypass stealth.py for any outgoing HTTP request. Do not pass raw dicts between modules — all data must flow through models.py.

---

## 1. Overview

The **Lead Generation & Web Presence Validation Engine** is an automated prospecting system that identifies, extracts, evaluates, and segments local service-based US businesses as high-value digital marketing leads.

### What Changed from v1 and Why

The v1 architecture had a single overloaded `scraper.py` that handled both API discovery and website contact scraping. Any change to one function risked breaking the other. There was no data contract between modules — a new field added in one place could silently fail or crash downstream.

v2 solves this by:

- Splitting `scraper.py` into `discovery.py` (find businesses) and `extractor.py` (extract contacts)
- Introducing `models.py` as a strict Pydantic data contract — no data reaches the database without passing validation
- Introducing `stealth.py` as a dedicated HTTP shield — all outgoing web requests route through it, never directly through `requests`
- Replacing CSV outputs with SQLite via `database.py` — supports nullable fields, UPSERT, and failure reason logging
- Replacing the static 120s batch cooldown with a human behavioral timing curve in `stealth.py`

---

## 2. Module Map

```text
first_agy_agent_lead_scraper/
│
├── config.py          # Global source of truth: API keys, DB path, cities, niches,
│                      # timeouts, User-Agent pool, SQLite schema constants
│
├── logger.py          # Dual-destination logging: colorized stdout + persistent file
│                      # (logs/app.log). No business logic lives here.
│
├── tracker.py         # Monthly API quota tracking for SerpApi, Brave, and Hunter.io/Apollo.
│                      # Raises QuotaExhaustedError before any out-of-quota network call.
│                      # Called by discovery.py and extractor.py before every API request.
│
├── stealth.py         # ⚠️ ALL outgoing HTTP requests must route through this module.
│                      # Wraps curl_cffi to mimic Chrome TLS fingerprint.
│                      # Manages persistent sessions (consistent headers + cookies per site).
│                      # Implements human behavioral timing curve — randomized variable
│                      # delays between requests; replaces all static sleep intervals.
│                      # Never rotates User-Agent mid-session (triggers bot detection).
│
├── discovery.py       # Single responsibility: find business names and website URLs.
│                      # Internal fallback chain (see Section 4).
│                      # Does NOT scrape websites. Does NOT validate URLs.
│                      # Pings tracker.py before every API call.
│                      # Routes all HTTP through stealth.py.
│
├── validator.py       # Single responsibility: HTTP probe only.
│                      # Sends GET request (via stealth.py) to discovered URL.
│                      # Returns live/dead status, resolved redirect URL, and HTTP status code.
│                      # Does NOT extract data. Does NOT call external APIs.
│
├── extractor.py       # Single responsibility: extract contact data from a live website URL.
│                      # Internal fallback chain for email (see Section 4).
│                      # Internal fallback chain for socials (see Section 4).
│                      # Routes all HTTP through stealth.py.
│                      # Pings tracker.py before Hunter.io/Apollo API calls.
│
├── models.py          # Pydantic v2 data contract. Single BusinessLead model.
│                      # All fields typed. Optional fields nullable with explicit status.
│                      # Every extraction attempt has a corresponding status field.
│                      # No data reaches database.py without passing this model.
│
├── database.py        # SQLite persistence layer. Replaces storage.py and CSV outputs.
│                      # Creates tables on first run. Handles UPSERT (insert or update).
│                      # Logs failure reasons per field (NOT_FOUND, BLOCKED, QUOTA_EXHAUSTED).
│                      # Deduplication via SQL query — replaces the in-memory set.
│
└── main.py            # CLI orchestrator only. Parses args, runs pipeline phases,
│                      # renders progress bars, prints execution summary.
│                      # No business logic. No HTTP calls. No data processing.
│
├── AGENTS.md          # Agent governance rules (hard stops, auto-proceed directives)
```text

├── ARCHITECTURE.md    # This file
├── README.md          # Setup, CLI usage, output schema
├── requirements.txt   # Python dependencies
├── .env.example       # API key template
├── .gitignore         # Excludes .env, *.db, logs/, __pycache__/
│
└── logs/
    └── app.log        # Rotating DEBUG/INFO execution logs

```

---

## 3. Module Responsibilities (Single Responsibility Contract)

> **Agent Rule:** If you are asked to modify a module, only touch the file whose responsibility matches the change. Use this table to decide which file to open.

| Module | Does | Does NOT |
| --- | --- | --- |
| `config.py` | Store all constants and credentials | Contain any logic or function calls |
| `logger.py` | Log messages | Process or transform data |
| `tracker.py` | Check and increment API quota counters | Make any network requests |
| `stealth.py` | Wrap HTTP requests with TLS mimicry and timing | Contain any business or parsing logic |
| `discovery.py` | Query APIs to find business name + URL | Validate URLs or extract contact data |
| `validator.py` | Probe a URL for live/dead HTTP status | Query APIs or extract contact fields |
| `extractor.py` | Extract email and social links from a URL | Discover businesses or validate URLs |
| `models.py` | Define and validate the BusinessLead data shape | Make network calls or write to disk |
| `database.py` | Persist validated leads to SQLite | Make network calls or validate data |
| `main.py` | Orchestrate the pipeline and render CLI output | Contain any business or network logic |

---

## 4. Pipeline & Data Flow

### Sequential Pipeline (per business)

```txt
main.py
  │
  └─► discovery.py ──► validator.py ──► extractor.py ──► models.py ──► database.py
         │                                    │                │
    [fallback chain]                   [fallback chain]  [validates all
                                                          fields + statuses]
```

Each business record travels this chain in order. A failure at any stage is captured as a status field in the model — it does not crash the pipeline.

### Discovery Fallback Chain (inside discovery.py)

```txt
Priority 1: SerpApi (Google Maps engine)
    │  quota OK & results found → continue
    │  quota exhausted / error / empty
    ▼
Priority 2: Brave Search API
    │  quota OK & results found → continue
    │  quota exhausted
    ▼
    Log QUOTA_EXHAUSTED, skip this query combination, continue pipeline
```

### Extractor Fallback Chain (inside extractor.py)

**Email extraction:**

```txt
Priority 1: Hunter.io / Apollo API (domain lookup)
    │  quota OK & email found → record email, status = FOUND_API
    │  quota exhausted / not found
    ▼
Priority 2: BeautifulSoup (scrape homepage, /contact, /about pages)
    │  mailto: link found → record email, status = FOUND_SCRAPE
    │  not found / blocked
    ▼
    Record email = None, status = NOT_FOUND
```

**Social media extraction:**

```txt
Priority 1: BeautifulSoup (scrape outbound links on business website)
    │  social profile links found → record, status = FOUND_ON_SITE
    │  not found / site blocked
    ▼
Priority 2: DuckDuckGo HTML search (public endpoint, no API key)
    │  results found → record, status = FOUND_DDG
    │  blocked / empty
    ▼
    Record socials = {}, status = NOT_FOUND
```

---

## 5. Stealth Layer — Routing Rules

> **Agent Rule:** This is the most critical constraint in the system. Every outgoing HTTP GET or POST in `validator.py` and `extractor.py` MUST go through `stealth.py`. Using Python `requests` directly bypasses Chrome TLS fingerprinting and will result in bot detection blocks.

### What stealth.py provides

| Feature | Implementation | Why |
| --- | --- | --- |
| TLS fingerprinting | `curl_cffi` mimicking Chrome's TLS handshake | Python `requests` has an identifiable TLS signature that servers detect before reading headers |
| Session cohesion | Persistent `curl_cffi` session per site visit | Rotating User-Agent mid-session triggers security flags — real browsers don't do this |
| Human timing curve | Randomized delays drawn from a non-uniform distribution | Static sleep intervals (e.g. exactly 120s every 10 batches) are a bot signature; human browsing is irregular |
| User-Agent pool | Rotated between site sessions, not within them | New session = new identity; same session = consistent identity |

### Timing behavior (replaces old static cooldown)

The old architecture used a fixed `BATCH_SLEEP_TIME = 120s` every 10 queries. This is replaced with:

- **Between individual requests:** randomized delay drawn from a behavioral curve (short bursts simulating reading, occasional longer pauses)
- **Between query combinations (city × niche batches):** variable cooldown, not fixed
- **No fixed interval of any kind** — predictable intervals are detectable

---

## 6. Data Contract — models.py

### BusinessLead model

Every field that can fail has a paired status field. This eliminates silent failures.

```python
class BusinessLead(BaseModel):
    # Core identity (required)
    business_name: str
    city: str
    industry: str
    timestamp: str

    # Web presence (from validator.py)
    website_found: bool
    website_url: Optional[str] = None
    http_status: Optional[str] = None          # "200", "404", "TIMEOUT", "CONN_ERROR", "NO_URL"

    # Email extraction (from extractor.py)
    email: Optional[str] = None
    email_status: str = "NOT_ATTEMPTED"        # FOUND_API | FOUND_SCRAPE | NOT_FOUND |
                                               # BLOCKED | QUOTA_EXHAUSTED | NOT_ATTEMPTED

    # Social media (from extractor.py)
    linkedin: Optional[str] = None
    instagram: Optional[str] = None
    facebook: Optional[str] = None
    twitter: Optional[str] = None
    social_status: str = "NOT_ATTEMPTED"       # FOUND_ON_SITE | FOUND_DDG | NOT_FOUND |
                                               # BLOCKED | NOT_ATTEMPTED
```

### Status values (used across email_status and social_status)

| Status | Meaning |
| --- | --- |
| `FOUND_API` | Email found via Hunter.io/Apollo |
| `FOUND_SCRAPE` | Email found via BeautifulSoup |
| `FOUND_ON_SITE` | Socials found directly on the business website |
| `FOUND_DDG` | Socials found via DuckDuckGo fallback |
| `NOT_FOUND` | Extraction ran but returned nothing |
| `BLOCKED` | Site or search returned 403/Cloudflare/captcha |
| `QUOTA_EXHAUSTED` | API quota hit before extraction could run |
| `NOT_ATTEMPTED` | Module was not reached (e.g. website was dead) |

---

## 7. Storage — database.py

Replaces `needs_digital_presence.csv` and `established_digital_presence.csv`.

### SQLite schema (single table)

```sql
CREATE TABLE IF NOT EXISTS leads (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    business_name     TEXT NOT NULL,
    city              TEXT NOT NULL,
    industry          TEXT NOT NULL,
    timestamp         TEXT NOT NULL,
    website_found     INTEGER NOT NULL,         -- 0 or 1
    website_url       TEXT,
    http_status       TEXT,
    email             TEXT,
    email_status      TEXT NOT NULL DEFAULT 'NOT_ATTEMPTED',
    linkedin          TEXT,
    instagram         TEXT,
    facebook          TEXT,
    twitter           TEXT,
    social_status     TEXT NOT NULL DEFAULT 'NOT_ATTEMPTED',
    UNIQUE(business_name, city)                 -- deduplication constraint
);
```

### Key behaviors

- **Deduplication:** SQL `INSERT OR IGNORE` on `(business_name, city)` unique constraint. No in-memory set required.
- **UPSERT:** On re-run, existing records can be updated with newly extracted data (e.g. email found on second pass).
- **Failure visibility:** `email_status` and `social_status` always have a value. An empty `email` field with `email_status = BLOCKED` tells you exactly what happened.
- **Querying leads:** `SELECT * FROM leads WHERE website_found = 0` returns all high-priority targets with no website.

---

## 8. External APIs & Quota Management

| Service | Module | Env Variable | Free Quota | Fallback |
| --- | --- | --- | --- | --- |
| SerpApi (Google Maps) | `discovery.py` | `SERPAPI_API_KEY` | 250 calls/month | Brave Search |
| Brave Search API | `discovery.py` | `BRAVE_API_KEY` | 1,000 calls/month | Halt discovery gracefully |
| Hunter.io / Apollo | `extractor.py` | `HUNTER_API_KEY` | Varies by tier | BeautifulSoup scrape |
| DuckDuckGo HTML | `extractor.py` | None (public) | Unmetered (rate-governed by stealth.py) | Log NOT_FOUND |
| Direct HTTP probing | `validator.py` + `extractor.py` | None | N/A | Log error status |

`tracker.py` maintains a `usage_tracker.json` file with monthly counters for SerpApi, Brave, and Hunter. It raises `QuotaExhaustedError` before any out-of-quota call is made — no surprise billing.

---

## 9. Fallback & Error Handling Rules

> **Agent Rule:** The system must never silently succeed while producing empty output. Every error must be captured as a status field, logged, and handled gracefully.

1. **No silent swallowing of exceptions.** Every `try/except` block must either log the exception with context or set the appropriate status field on the model.
2. **A blocked site is not a crash.** If extractor.py hits a 403 or Cloudflare wall, set `email_status = BLOCKED`, log it, and continue to the next business.
3. **A dead website is not a crash.** If validator.py gets a timeout or DNS error, set `website_found = False`, set `http_status = TIMEOUT` (or `CONN_ERROR`), and skip extractor.py for that record.
4. **Quota exhaustion is not a crash.** If tracker.py raises `QuotaExhaustedError`, log it, set the appropriate status, and either fall back to the next priority or skip gracefully.
5. **The end-of-run summary must always show:** total processed, total with email found, total with socials found, total blocked, total quota exhausted, total dead websites. Never "Success" with nothing beneath it.

---

## 10. CLI Reference

```bash
# Default offline run (mock data, for testing)
python main.py

# Live discovery mode
python main.py --live

# Targeted region
python main.py --live --cities "Houston, TX" "Miami, FL"

# Targeted vertical
python main.py --live --niches "Plumbing" "Roofing"

# Combined
python main.py --live --cities "Atlanta, GA" --niches "HVAC" "Landscaping"
```

---

## 11. Environment Configuration

Create a `.env` file in the project root:

```env
SERPAPI_API_KEY=your_serpapi_key_here
BRAVE_API_KEY=your_brave_key_here
HUNTER_API_KEY=your_hunter_key_here
```

---

## 12. Dependencies (requirements.txt)

```txt
curl_cffi          # Chrome TLS fingerprinting (replaces requests for all HTTP)
pydantic>=2.0      # Data contract and validation
beautifulsoup4     # HTML parsing for contact extraction
python-dotenv      # .env loading
```
