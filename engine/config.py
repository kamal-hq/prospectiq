"""
config.py — Central configuration for the ProspectIQ v3.0 Lead Generation Engine.

Defines paths, API keys, monthly quotas, target markets, stealth parameters,
anti-garbage exclusion lists, URL hygiene rules, and legacy CSV schema constants.
Contains NO business logic or network I/O.
"""

import os
from dotenv import load_dotenv

# ──────────────────────────────────────────────
# Directory & File Paths (Anchored to Repository Root)
# ──────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Load environment variables from a local .env file at repo root (if present)
load_dotenv(os.path.join(BASE_DIR, ".env"))

DB_PATH = os.path.join(BASE_DIR, "leads.db")
LOG_DIR = os.path.join(BASE_DIR, "logs")
LOG_FILE = os.path.join(LOG_DIR, "app.log")

# ──────────────────────────────────────────────
# API Keys & Third-Party Monthly Quotas
# ──────────────────────────────────────────────
BRAVE_API_KEY = os.getenv("BRAVE_API_KEY")
BRAVE_MONTHLY_QUOTA = 1000

SERPAPI_API_KEY = os.getenv("SERPAPI_API_KEY")
SERPAPI_MONTHLY_QUOTA = 250

HUNTER_API_KEY = os.getenv("HUNTER_API_KEY", "")
HUNTER_MONTHLY_QUOTA = 50

# Supabase Shared Multi-Schema Hub Configuration (`shared-apps`, schema `prospectiq`).
# PUBLISHABLE KEY ONLY — NEVER store or use `service_role` on a shared multi-schema project
# (it would bypass RLS across sibling schemas like `cadence`).
# Headless Python/CI runs authenticate as the single Owner via Supabase Auth JWT.
SUPABASE_URL = os.getenv("SUPABASE_URL") or os.getenv("NEXT_PUBLIC_SUPABASE_URL", "")
SUPABASE_ANON_KEY = (
    os.getenv("SUPABASE_ANON_KEY") or os.getenv("NEXT_PUBLIC_SUPABASE_ANON_KEY", "")
)
SUPABASE_SCHEMA = (
    os.getenv("SUPABASE_SCHEMA") or os.getenv("NEXT_PUBLIC_SUPABASE_SCHEMA", "prospectiq")
)
SUPABASE_OWNER_EMAIL = os.getenv("SUPABASE_OWNER_EMAIL", "")
SUPABASE_OWNER_PASSWORD = os.getenv("SUPABASE_OWNER_PASSWORD", "")

# ──────────────────────────────────────────────
# Legacy Output CSV Destinations (Preserved for Compatibility)
# ──────────────────────────────────────────────
NEEDS_DIGITAL_CSV = os.path.join(BASE_DIR, "needs_digital_presence.csv")
ESTABLISHED_DIGITAL_CSV = os.path.join(BASE_DIR, "established_digital_presence.csv")

# ──────────────────────────────────────────────
# Target Cities & Service Niches
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
REQUEST_TIMEOUT = 25
MIN_DELAY = 1.0
MAX_DELAY = 3.0
MAX_RETRIES = 2

JITTER_MIN = 8.0
JITTER_MAX = 15.0
BATCH_CYCLE_SIZE = 10
BATCH_SLEEP_TIME = 120

# ──────────────────────────────────────────────
# Security: Sensitive Query Parameters to Redact in Logs
# ──────────────────────────────────────────────
SECRET_QUERY_PARAMS = {
    "api_key",
    "apikey",
    "key",
    "token",
    "access_token",
    "auth",
    "authorization",
    "secret",
    "password",
    "pwd",
}

# ──────────────────────────────────────────────
# URL Hygiene: Tracking Query Parameters to Strip
# ──────────────────────────────────────────────
TRACKING_QUERY_PARAMS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "utm_id",
    "utm_cid",
    "gclid",
    "fbclid",
    "msclkid",
    "mc_cid",
    "mc_eid",
    "_ga",
    "_gl",
    "_rdr",
    "y_source",
    "campaignid",
    "adgroupid",
    "gbp",
}

# ──────────────────────────────────────────────
# Anti-Garbage Filtering Lists
# ──────────────────────────────────────────────
# Directories & aggregators — NEVER valid owned business websites
AGGREGATOR_DOMAINS = {
    "yelp.com",
    "yellowpages.com",
    "bbb.org",
    "thumbtack.com",
    "angi.com",
    "angieslist.com",
    "homeadvisor.com",
    "nextdoor.com",
    "mapquest.com",
    "manta.com",
    "google.com",
    "goo.gl",
    "maps.google.com",
    "wikipedia.org",
    "chron.com",
    "houstonchronicle.com",
    "tripadvisor.com",
    "houzz.com",
    "porch.com",
    "bark.com",
    "expertise.com",
    "threebestrated.com",
    "superpages.com",
    "whitepages.com",
    "chamberofcommerce.com",
    "birdeye.com",
    "trustpilot.com",
    "foursquare.com",
    "alignable.com",
    "crunchbase.com",
    "dnb.com",
    "bizapedia.com",
    "opencorporates.com",
    "buildzoom.com",
    "networx.com",
    "modernize.com",
    "patch.com",
    "merchantcircle.com",
    "citysearch.com",
    "local.com",
    "hotfrog.com",
    "brownbook.net",
}

# Social / link-in-bio / deprecated GBP mini-sites pasted in Maps "website" field.
# Maps domain -> social platform key (or None if non-website bio page like linktr.ee / business.site).
SOCIAL_ONLY_WEBSITE_DOMAINS = {
    "facebook.com": "facebook",
    "fb.com": "facebook",
    "fb.me": "facebook",
    "instagram.com": "instagram",
    "linkedin.com": "linkedin",
    "twitter.com": "twitter",
    "x.com": "twitter",
    "tiktok.com": None,
    "linktr.ee": None,
    "linktree.com": None,
    "beacons.ai": None,
    "bio.link": None,
    "business.site": None,
    "youtube.com": None,
}

# URL path patterns indicating aggregator listicles or directory rankings
AGGREGATOR_PATH_PATTERNS = (
    "best-",
    "top-",
    "/directory/",
    "/listings/",
    "/yellow-pages/",
)

# Multi-state / national home-service franchises & chains to flag (is_franchise=True)
FRANCHISE_BRANDS = {
    "roto-rooter",
    "roto rooter",
    "service experts",
    "aire serv",
    "benjamin franklin plumbing",
    "one hour heating",
    "mr. rooter",
    "mr rooter",
    "mr. electric",
    "mr. handyman",
    "molly maid",
    "merry maids",
    "terminix",
    "orkin",
    "trugreen",
    "servpro",
    "puroclean",
    "goettl",
    "rooter-man",
    "rooterman",
    "rescue rooter",
    "ars/rescue",
    "horizon services",
    "len the plumber",
    "home depot",
    "lowe's",
    "sears home services",
    "stanley steemer",
    "1-800-got-junk",
    "college hunks",
    "mosquito joe",
    "lawn doctor",
    "brightview",
    "cintas",
    "jan-pro",
    "rentokil",
    "ehrlich",
}

# Parked, expired, or suspended domain page signatures (lowercased)
PARKED_DOMAIN_SIGNATURES = (
    "this domain is for sale",
    "buy this domain",
    "domain is parked",
    "parked free, courtesy of",
    "sedoparking",
    "hugedomains.com",
    "afternic.com",
    "godaddy.com/domainsearch",
    "this domain name has expired",
    "renew your domain",
    "cgi-sys/suspendedpage.cgi",
    "this account has been suspended",
    "future home of something quite cool",
    "domain parking",
)

# Junk / platform / tracker / placeholder email domains to discard
EMAIL_DOMAIN_BLACKLIST = {
    "example.com",
    "example.org",
    "example.net",
    "domain.com",
    "yourdomain.com",
    "email.com",
    "test.com",
    "localhost",
    "sentry.io",
    "sentry-next.wixpress.com",
    "wixpress.com",
    "wix.com",
    "wordpress.org",
    "wordpress.com",
    "schema.org",
    "googleapis.com",
    "google.com",
    "gstatic.com",
    "github.com",
    "cloudflare.com",
    "godaddy.com",
    "squarespace.com",
    "webflow.com",
    "shopify.com",
    "hubspot.com",
    "mailchimp.com",
    "constantcontact.com",
    "amazonaws.com",
    "facebook.com",
    "instagram.com",
    "twitter.com",
    "x.com",
    "linkedin.com",
    "youtube.com",
    "tiktok.com",
    "yelp.com",
    "bbb.org",
    "w3.org",
    "gravatar.com",
    "jquery.com",
    "bootstrapcdn.com",
    "fontawesome.com",
    "jsdelivr.net",
    "unpkg.com",
    "cdnjs.com",
    "typekit.net",
    "doubleclick.net",
    "googletagmanager.com",
    "google-analytics.com",
    "hotjar.com",
    "intercom.io",
    "zendesk.com",
    "freshdesk.com",
    "twilio.com",
    "stripe.com",
    "paypal.com",
    "duckduckgo.com",
}

# Local-part prefixes that are non-outreach / automated / system mailboxes
EMAIL_LOCAL_BLACKLIST_PREFIXES = (
    "noreply",
    "no-reply",
    "donotreply",
    "do-not-reply",
    "privacy",
    "legal",
    "dmca",
    "abuse",
    "postmaster",
    "hostmaster",
    "webmaster",
    "mailer-daemon",
    "bounce",
    "unsubscribe",
    "notifications",
    "automated",
    "careers",
    "jobs",
    "recruiting",
    "press",
    "copyright",
    "security",
    "compliance",
    "accessibility",
    "ada",
)

# Legitimate consumer webmail providers frequently used by small local trades
FREE_EMAIL_PROVIDERS = {
    "gmail.com",
    "yahoo.com",
    "outlook.com",
    "hotmail.com",
    "aol.com",
    "icloud.com",
    "me.com",
    "live.com",
    "msn.com",
    "proton.me",
    "protonmail.com",
    "comcast.net",
    "sbcglobal.net",
    "att.net",
    "verizon.net",
    "cox.net",
    "bellsouth.net",
    "earthlink.net",
}

# ──────────────────────────────────────────────
# Legacy CSV Schema Definition (Preserved per AGENTS.md)
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

SOCIAL_PLATFORMS = {
    "linkedin": "linkedin.com",
    "instagram": "instagram.com",
    "facebook": "facebook.com",
    "twitter": "x.com",
}
