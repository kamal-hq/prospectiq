# ProspectIQ: Lead Generation & Web Presence Validation Engine

> **Automated B2B Prospecting Pipeline**  
> An independent portfolio project developed and maintained by **Muhammad Kamal**.

---

## Overview

The **Lead Generation & Web Presence Validation Engine** (ProspectIQ v2.0) is a resilient, automated B2B prospecting pipeline engineered to discover local service businesses, validate their web presence, and extract verified contact points (direct emails and social profiles).

Built with modular single-responsibility components, the engine uses **Chrome TLS stealth mimicry**, **strict Pydantic data contracts**, **SQLite relational storage**, and **multi-tier fallback chains** to systematically classify high-value marketing and web-development leads without silent pipeline failures or bot detection blocks.

---

## Key Features & v2.0 Architecture Upgrades

- 🛡️ **`curl_cffi` TLS Stealth Routing (`stealth.py`)**:
  - All outbound network requests route through a dedicated TLS shield that impersonates Google Chrome browser handshakes.
  - Maintains persistent session cookies and headers per target domain—preventing Cloudflare and bot-protection triggers caused by standard Python `requests` TLS signatures.

- ⏳ **Human Behavioral Delays & Anti-Throttling**:
  - Replaces rigid static sleep timers with randomized, non-uniform delay curves simulating authentic human reading and browsing behavior.
  - Variable pacing between individual page requests and batch queries prevents IP throttling and rate-limit blocks.

- 📐 **Strict Pydantic v2 Data Contracts (`models.py`)**:
  - Every prospect is validated through the `BusinessLead` schema before touching persistence layers.
  - Every extracted field has an explicit status contract (`FOUND_API`, `FOUND_SCRAPE`, `FOUND_ON_SITE`, `FOUND_DDG`, `NOT_FOUND`, `BLOCKED`, `QUOTA_EXHAUSTED`, `NOT_ATTEMPTED`), eliminating silent pipeline failures.

- 🗄️ **SQLite Persistence Layer (`database.py` & `leads.db`)**:
  - Replaces legacy CSV flat files with an indexed, transactional SQLite database.
  - Native atomic deduplication on `(business_name, city)` via SQL unique constraints.
  - Supports intelligent UPSERTs, allowing repeat scans to enrich existing lead profiles with newly discovered contacts.

- 🔄 **Multi-Tier Fallback Chains**:
  - **Business Discovery**:
    - *Priority 1*: SerpApi (Google Maps Local Listings Engine)
    - *Priority 2*: Brave Search API (fallback web discovery)
    - *Offline*: Mock dataset for testing without consuming API credits.
  - **Email Extraction**:
    - *Priority 1*: Hunter.io API (domain-level verified email lookup)
    - *Priority 2*: BeautifulSoup scraper (deep scan of homepage, `/contact`, `/about`, and `mailto:` links)
  - **Social Media Extraction**:
    - *Priority 1*: BeautifulSoup direct on-site outbound anchor link extraction (LinkedIn, Instagram, Facebook, X/Twitter)
    - *Priority 2*: DuckDuckGo HTML public search fallback

- 📊 **Proactive Quota & Budget Protection (`tracker.py`)**:
  - Pre-flight quota counter (`usage_tracker.json`) monitors monthly consumption across SerpApi, Brave Search, and Hunter.io.
  - Halts or skips API calls before incurring billable overages.

---

## Pipeline Architecture

```text
[ CLI Orchestrator: main.py ]
          │
          ├──► Step 1: Initialize Database & Logging (database.py, logger.py)
          │
          ├──► Step 2: Business Discovery (discovery.py)
          │      ├── Offline Mock Mode (default)
          │      └── Live Multi-Tier Discovery:
          │            ├── Priority 1: SerpApi (Google Maps Engine)
          │            └── Priority 2: Brave Search API Fallback
          │            └── Guard: Quota Tracker (usage_tracker.json)
          │
          ├──► Step 3: Web Presence Validation (validator.py)
          │      └── HTTP Probe & Redirect Resolution (via stealth.py)
          │
          ├──► Step 4: Contact Extraction (extractor.py via stealth.py)
          │      ├── Email Fallback Chain: Hunter.io API ──► BeautifulSoup (/contact, mailto:)
          │      └── Socials Fallback Chain: On-Site Anchors ──► DuckDuckGo HTML Fallback
          │
          ├──► Step 5: Data Contract Enforcement (models.py: BusinessLead)
          │
          └──► Step 6: Relational Persistence & Deduplication (database.py ──► leads.db)
```

---

## Module Map (Single Responsibility Architecture)

| Module | Core Responsibility | HTTP / Logic Policy |
| :--- | :--- | :--- |
| `config.py` | Central configuration, API keys, database paths, target cities & niches | No business logic |
| `logger.py` | Dual-destination logging (colorized stdout + persistent `logs/app.log`) | Formatting & output only |
| `tracker.py` | Monthly API quota tracking and persistent counter management | No network calls |
| `stealth.py` | TLS fingerprinting, persistent sessions, human behavioral delay curves | Sole outbound HTTP gateway |
| `discovery.py` | Discovers business candidates via SerpApi and Brave Search | Routes HTTP via `stealth.py` |
| `validator.py` | Probes target URLs for live/dead HTTP status and redirect resolution | Routes HTTP via `stealth.py` |
| `extractor.py` | Extracts emails and social profiles via API and HTML fallback chains | Routes HTTP via `stealth.py` |
| `models.py` | Pydantic v2 `BusinessLead` model and `ExtractionStatus` validation | Schema validation only |
| `database.py` | SQLite connection, table migrations, SQL deduplication, and UPSERTs | Database access only |
| `main.py` | CLI argument parser, terminal progress display, execution summary | CLI orchestration only |

---

## Prerequisites

- **Python 3.10+** (Fully tested on Python 3.10, 3.11, and 3.12)
- **API Credentials** *(Required only for live discovery mode)*:
  - [SerpApi Account](https://serpapi.com/) — Free tier includes 250 monthly searches.
  - [Brave Search API Account](https://api.search.brave.com/) — Free tier includes 1,000 monthly requests.
  - [Hunter.io Account](https://hunter.io/) — Free tier includes 50 domain searches/month.

---

## Installation & Setup

### 1. Clone the Repository

```bash
git clone https://github.com/your-username/prospectiq.git
cd prospectiq
```

### 2. Create and Activate a Virtual Environment

**On Linux / macOS:**

```bash
python3 -m venv .venv
source .venv/bin/activate
```

**On Windows (PowerShell / Command Prompt):**

```powershell
python -m venv .venv
.venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables

Create your local `.env` configuration from the provided template:

```bash
# On Linux / macOS
cp .env.example .env

# On Windows (PowerShell)
Copy-Item .env.example .env
```

Open `.env` in your text editor and add your API credentials:

```env
# SerpApi API Key (Google Maps / local business discovery)
SERPAPI_API_KEY=your_serpapi_api_key_here

# Brave Search API Key (Fallback discovery)
BRAVE_API_KEY=your_brave_api_key_here

# Hunter.io API Key (Domain-level email verification)
HUNTER_API_KEY=your_hunter_api_key_here
```

---

## Usage

### 1. Offline Mock Mode (Default)

Run a complete pipeline verification (discovery, validation, extraction, model validation, and SQLite persistence) instantly without burning API credits:

```bash
python main.py
```

### 2. Live Discovery Mode

Discover real businesses across the default target cities and industry niches configured in `config.py`:

```bash
python main.py --live
```

### 3. Custom Targeted Search

Target specific metropolitan areas and business verticals directly from the CLI:

```bash
# Single city and niche
python main.py --live --cities "Houston, TX" --niches "Plumbing"

# Multiple cities and industry verticals
python main.py --live --cities "Houston, TX" "Miami, FL" "Atlanta, GA" --niches "Plumbing" "Roofing" "HVAC"
```

---

## SQLite Database & Lead Prospecting

All leads are stored in `leads.db` under the `leads` table.

### Table Schema

| Column | Type | Constraints / Description |
| :--- | :--- | :--- |
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT |
| `business_name` | TEXT | Non-nullable entity name |
| `city` | TEXT | Target city / state |
| `industry` | TEXT | Business niche / category |
| `timestamp` | TEXT | ISO-8601 UTC timestamp |
| `website_found` | INTEGER | `1` if live website exists, `0` if no site / broken |
| `website_url` | TEXT | Resolved landing page URL |
| `http_status` | TEXT | HTTP status (`200`, `404`, `TIMEOUT`, `CONN_ERROR`, `NO_URL`) |
| `email` | TEXT | Discovered email address |
| `email_status` | TEXT | `FOUND_API`, `FOUND_SCRAPE`, `NOT_FOUND`, `BLOCKED`, `QUOTA_EXHAUSTED`, `NOT_ATTEMPTED` |
| `linkedin` | TEXT | LinkedIn profile URL |
| `instagram` | TEXT | Instagram handle/profile URL |
| `facebook` | TEXT | Facebook page URL |
| `twitter` | TEXT | X / Twitter profile URL |
| `social_status` | TEXT | `FOUND_ON_SITE`, `FOUND_DDG`, `NOT_FOUND`, `BLOCKED`, `NOT_ATTEMPTED` |

### Sample Prospecting SQL Queries

```sql
-- 1. High-priority leads: Established businesses with NO active website (Web Design / SEO Pitch)
SELECT business_name, city, industry, http_status
FROM leads 
WHERE website_found = 0;

-- 2. Ready-to-email leads: Active websites with verified email addresses
SELECT business_name, city, industry, website_url, email, email_status
FROM leads 
WHERE email IS NOT NULL;

-- 3. Omni-channel outreach leads: Businesses with at least one verified social profile
SELECT business_name, city, website_url, linkedin, instagram, facebook
FROM leads 
WHERE linkedin IS NOT NULL OR instagram IS NOT NULL OR facebook IS NOT NULL;
```

---

## Author & Project Information

- **Developer**: **Muhammad Kamal**
- **Project Role**: Automated Prospecting Pipeline & Lead Intelligence Engine (Portfolio Project)
- **License**: Open-source under the [MIT License](LICENSE)
