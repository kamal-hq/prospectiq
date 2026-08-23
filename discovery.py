"""
Discovery Layer — discovery.py

Responsible solely for discovering local business entities (business names and candidate website URLs)
using multi-tier search APIs (SerpApi Google Maps -> Brave Search API).
Routes all outgoing HTTP requests through stealth.py.
Does NOT perform website validation or contact extraction.
"""

import re
from typing import Any, Dict, List, Optional

from config import (
    BRAVE_API_KEY,
    BRAVE_MONTHLY_QUOTA,
    REQUEST_TIMEOUT,
    SERPAPI_API_KEY,
    SERPAPI_MONTHLY_QUOTA,
)
from logger import setup_logger
import stealth
from tracker import QuotaExhaustedError, check_and_increment

log = setup_logger("discovery")

# Aggregator/directory domains to filter out from search results
AGGREGATOR_DOMAINS = [
    "yelp.com",
    "yellowpages.com",
    "bbb.org",
    "thumbtack.com",
    "angi.com",
    "homeadvisor.com",
    "nextdoor.com",
    "mapquest.com",
    "manta.com",
    "google.com",
    "facebook.com",
    "wikipedia.org",
    "linkedin.com",
    "instagram.com",
    "chron.com",
    "houstonchronicle.com",
    "tripadvisor.com",
]

# URL path patterns indicating aggregator listicles or directory rankings
AGGREGATOR_PATH_PATTERNS = [
    "best-",
    "top-",
]


def _clean_business_name(raw_name: str) -> str:
    """
    Clean and normalize raw business names extracted from search titles/snippets.
    Strips trailing geographic indicators, page titles, and boilerplate suffixes.
    """
    patterns = [
        r"\s*[\|–—-]\s*(Home|Official Site|Welcome|About|Contact|Services).*$",
        r"\s*[\|–—-]\s*\w+,\s*\w{2}\s*$",  # e.g., "- Dallas, TX" suffixes
        r"\s*\.\.\.\s*$",                  # Truncated title ellipsis
    ]
    name = raw_name
    for pattern in patterns:
        name = re.sub(pattern, "", name, flags=re.IGNORECASE)
    return name.strip()


def _search_serpapi(city: str, industry: str, max_results: int = 10) -> List[Dict[str, Optional[str]]]:
    """
    Priority 1: Query SerpApi Google Maps engine to discover local business leads.
    Pings tracker.py before making external request.
    Routes HTTP request through stealth.py.
    """
    if not SERPAPI_API_KEY:
        log.warning("SerpApi key missing. Skipping Priority 1 (SerpApi).")
        return []

    try:
        check_and_increment("serpapi", SERPAPI_MONTHLY_QUOTA)
    except QuotaExhaustedError as exc:
        log.warning(f"SerpApi quota exhausted: {exc}. Falling back to Priority 2 (Brave).")
        return []
    except Exception as exc:
        log.error(f"Tracker check failed for SerpApi: {exc}. Skipping Priority 1.")
        return []

    query = f"{industry} in {city}"
    url = "https://serpapi.com/search.json"
    params = {
        "engine": "google_maps",
        "q": query,
        "api_key": SERPAPI_API_KEY,
        "type": "search",
    }

    log.info(f"Priority 1: Searching SerpApi (Google Maps) -> '{industry}' in '{city}'")
    leads: List[Dict[str, Optional[str]]] = []

    try:
        response = stealth.get(url, params=params, timeout=REQUEST_TIMEOUT)

        if response.status_code == 429:
            log.warning("SerpApi returned HTTP 429 (Rate limited/Quota exhausted). Falling back to Priority 2.")
            return []

        if response.status_code != 200:
            log.warning(f"SerpApi returned HTTP {response.status_code}: {response.text}")
            return []

        data = response.json()
        if "error" in data:
            log.warning(f"SerpApi JSON error: {data['error']}. Falling back to Priority 2.")
            return []

        local_results = data.get("local_results", [])
        for item in local_results:
            raw_title = item.get("title", "")
            website = item.get("website")
            biz_name = _clean_business_name(raw_title)

            if not biz_name or len(biz_name) < 2:
                continue

            leads.append({
                "business_name": biz_name,
                "city": city,
                "industry": industry,
                "website_url": website if website and website.strip() else None,
            })

            if len(leads) >= max_results:
                break

        log.info(f"SerpApi found {len(leads)} leads for '{industry}' in '{city}'")
    except Exception as exc:
        log.error(f"SerpApi search failed for '{industry}' in '{city}': {exc}")

    return leads


def _search_brave(city: str, industry: str, max_results: int = 10) -> List[Dict[str, Optional[str]]]:
    """
    Priority 2: Query Brave Search API as discovery fallback.
    Pings tracker.py before making external request.
    Routes HTTP request through stealth.py.
    """
    if not BRAVE_API_KEY:
        log.warning("Brave API key missing. Skipping Priority 2 (Brave).")
        return []

    try:
        check_and_increment("brave", BRAVE_MONTHLY_QUOTA)
    except QuotaExhaustedError as exc:
        log.warning(f"Brave Search API quota exhausted: {exc}.")
        return []
    except Exception as exc:
        log.error(f"Tracker check failed for Brave: {exc}. Skipping Priority 2.")
        return []

    query = f"{industry} services in {city} -yelp -yellowpages"
    url = "https://api.search.brave.com/res/v1/web/search"
    headers = {
        "Accept": "application/json",
        "Accept-Encoding": "gzip",
        "X-Subscription-Token": BRAVE_API_KEY,
    }
    params = {
        "q": query,
        "count": min(max_results * 2, 20),
    }

    log.info(f"Priority 2: Searching Brave Search API -> '{industry}' in '{city}'")
    leads: List[Dict[str, Optional[str]]] = []

    try:
        response = stealth.get(url, headers=headers, params=params, timeout=REQUEST_TIMEOUT)

        if response.status_code == 429:
            log.warning("Brave API returned HTTP 429 (Rate limited/Quota exhausted).")
            return []

        if response.status_code != 200:
            log.warning(f"Brave API returned HTTP {response.status_code}: {response.text}")
            return []

        data = response.json()
        web_results = data.get("web", {}).get("results", [])

        for item in web_results:
            raw_title = item.get("title", "")
            href = item.get("url", "")
            biz_name = _clean_business_name(raw_title)

            if not biz_name or len(biz_name) < 2:
                continue

            href_lower = href.lower()

            # Filter aggregator domains
            if any(domain in href_lower for domain in AGGREGATOR_DOMAINS):
                continue

            # Filter aggregator/listicle path patterns (e.g. best-, top-)
            if any(pattern in href_lower for pattern in AGGREGATOR_PATH_PATTERNS):
                continue

            leads.append({
                "business_name": biz_name,
                "city": city,
                "industry": industry,
                "website_url": href if href and href.strip() else None,
            })

            if len(leads) >= max_results:
                break

        log.info(f"Brave API found {len(leads)} leads for '{industry}' in '{city}'")
    except Exception as exc:
        log.error(f"Brave API search failed for '{industry}' in '{city}': {exc}")

    return leads


def discover_leads(city: str, industry: str, max_results: int = 10) -> List[Dict[str, Optional[str]]]:
    """
    Orchestrates business discovery across the fallback chain:
    Priority 1 (SerpApi) -> Priority 2 (Brave Search) -> Log exhaustion & return [].

    Returns a list of dicts with keys: business_name, city, industry, website_url.
    Does not raise exceptions on exhaustion; returns [] gracefully.
    """
    # Priority 1: SerpApi Google Maps
    leads = _search_serpapi(city=city, industry=industry, max_results=max_results)
    if leads:
        return leads

    # Priority 2: Brave Search API
    leads = _search_brave(city=city, industry=industry, max_results=max_results)
    if leads:
        return leads

    log.warning(f"No leads discovered or quotas exhausted for '{industry}' in '{city}'.")
    return []
