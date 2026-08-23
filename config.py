"""
config.py — Central configuration for the Lead Generation Engine.

Defines target cities, niches, file paths, request headers, API keys,
traffic profiling (rate-limiting jitter, batch cooldowns), and CSV schemas.
"""

import os
from dotenv import load_dotenv

# Load environment variables from a local .env file (if present)
load_dotenv()

# ──────────────────────────────────────────────
# Directory & File Paths
# ──────────────────────────────────────────────
# Absolute path to the directory containing this config file (project root)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# SQLite database file path for lead storage and deduplication
DB_PATH = os.path.join(BASE_DIR, "leads.db")

# Directory and log file path for persistent application logging
LOG_DIR = os.path.join(BASE_DIR, "logs")
LOG_FILE = os.path.join(LOG_DIR, "app.log")

# ──────────────────────────────────────────────
# API Keys & Third-Party Services
# ──────────────────────────────────────────────
# Brave Search API subscription token (used for fallback web search, monthly quota: 1000)
# Env Var: BRAVE_API_KEY (obtainable from https://api.search.brave.com/)
BRAVE_API_KEY = os.getenv("BRAVE_API_KEY")
BRAVE_MONTHLY_QUOTA = 1000

# SerpApi API key (used for Google Maps local business searches, monthly quota: 250)
# Env Var: SERPAPI_API_KEY (obtainable from https://serpapi.com/)
SERPAPI_API_KEY = os.getenv("SERPAPI_API_KEY")
SERPAPI_MONTHLY_QUOTA = 250

# Hunter.io API key (used for domain email search and verification, monthly quota: 50)
# Env Var: HUNTER_API_KEY (obtainable from https://hunter.io/)
HUNTER_API_KEY = os.getenv("HUNTER_API_KEY", "")
HUNTER_MONTHLY_QUOTA = 50

# ──────────────────────────────────────────────
# Output CSV Destinations
# ──────────────────────────────────────────────
# Target CSV file for businesses found without a live website (prime outreach candidates)
NEEDS_DIGITAL_CSV = os.path.join(BASE_DIR, "needs_digital_presence.csv")

# Target CSV file for businesses with an existing, functional website
ESTABLISHED_DIGITAL_CSV = os.path.join(BASE_DIR, "established_digital_presence.csv")

# ──────────────────────────────────────────────
# Target Cities (US-based)
# Default geographic regions for lead discovery
# ──────────────────────────────────────────────
TARGET_CITIES = [
    "Houston, TX",
    "Dallas, TX",
    "Austin, TX",
    "San Antonio, TX",
    "Miami, FL",
    "Orlando, FL",
    "Atlanta, GA",
    "Charlotte, NC",
    "Phoenix, AZ",
    "Denver, CO",
]

# ──────────────────────────────────────────────
# Target Niches / Industries
# Default service-based business verticals to query
# ──────────────────────────────────────────────
TARGET_NICHES = [
    "Plumbing",
    "HVAC",
    "Roofing",
    "Landscaping",
    "Auto Detailing",
    "Pest Control",
    "Cleaning Services",
    "Personal Training",
    "Real Estate Photography",
    "Mobile Car Wash",
]

# ──────────────────────────────────────────────
# HTTP Request Headers (Rotated User-Agents)
# Standard Chrome browser User-Agent strings rotated across sessions to mimic human traffic
# ──────────────────────────────────────────────
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
]

# ──────────────────────────────────────────────
# Scraping Behavior & Rate Limiting Parameters
# ──────────────────────────────────────────────
REQUEST_TIMEOUT = 30          # Network timeout for individual HTTP requests in seconds
MIN_DELAY = 1.0               # Minimum polite sleep delay between consecutive HTTP requests (seconds)
MAX_DELAY = 3.0               # Maximum polite sleep delay between consecutive HTTP requests (seconds)
MAX_RETRIES = 2               # Maximum number of retry attempts for failed HTTP calls

# Safety Harness & Traffic Profiling (used during large batch search discovery)
JITTER_MIN = 8.0              # Minimum random jitter delay between consecutive city/niche search cycles (seconds)
JITTER_MAX = 15.0             # Maximum random jitter delay between consecutive city/niche search cycles (seconds)
BATCH_CYCLE_SIZE = 10         # Threshold count of search combinations before triggering a cooldown sleep
BATCH_SLEEP_TIME = 120        # Extended cooldown duration in seconds (2 minutes) to prevent rate limits/IP blocks

# ──────────────────────────────────────────────
# CSV Schema Definition
# Exact column headers enforced when creating or appending lead records
# ──────────────────────────────────────────────
CSV_COLUMNS = [
    "Business Name",
    "City",
    "Industry/Niche",
    "Website Found",
    "Website URL",
    "Social Media Handles Found",
    "Validation Status Code",
    "Timestamp",
]

# ──────────────────────────────────────────────
# Social Media Platforms to Check
# Mapping of platform identifier to target domain used for footprints and link scraping
# ──────────────────────────────────────────────
SOCIAL_PLATFORMS = {
    "linkedin": "linkedin.com",
    "instagram": "instagram.com",
    "facebook": "facebook.com",
    "twitter": "x.com",
}
