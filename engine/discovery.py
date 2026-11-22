"""
Discovery Layer — discovery.py

Single responsibility: Discover local business entities using multi-tier search APIs
(Priority 1: SerpApi Google Maps -> Priority 2: Brave Search API) and emit clean,
strictly typed RawCandidate models.

v3.0 Upgrades:
- Captures full Google Maps metadata (place_id, phone, address, rating, reviews_count, status).
- Supports `start` pagination offset so repeated runs pull fresh leads instead of re-fetching page 1.
- Filters permanently closed listings and flags national franchises (`is_franchise=True`).
- Applies aggregator & social-only domain filtering to BOTH SerpApi and Brave results.
- Smart Social-as-Website splitting: Facebook/Instagram links listed as Google Maps websites
  are extracted into `prefilled_socials` while setting `website_url=None` (NO_WEBSITE!).
- Strips UTM/GMB tracking parameters into clean canonical URLs.
- Routes all outgoing HTTP strictly through stealth.py.
"""

import re
import urllib.parse
from typing import Dict, List, Optional, Tuple

from engine.config import (
    AGGREGATOR_DOMAINS,
    AGGREGATOR_PATH_PATTERNS,
    BRAVE_API_KEY,
    BRAVE_MONTHLY_QUOTA,
    FRANCHISE_BRANDS,
    REQUEST_TIMEOUT,
    SERPAPI_API_KEY,
    SERPAPI_MONTHLY_QUOTA,
    SOCIAL_ONLY_WEBSITE_DOMAINS,
    TRACKING_QUERY_PARAMS,
)
from engine.logger import setup_logger
from engine.models import RawCandidate
from engine import stealth
from engine.tracker import QuotaExhaustedError, check_and_increment

log = setup_logger("discovery")


def canonicalize_url(raw_url: Optional[str]) -> Optional[str]:
    """
    Normalize a candidate URL by ensuring scheme, stripping UTM/GMB tracking query
    parameters, and dropping fragments.
    """
    if not raw_url or not str(raw_url).strip():
        return None
    url = str(raw_url).strip()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    try:
        parsed = urllib.parse.urlsplit(url)
        if not parsed.netloc:
            return None
        kept_params = [
            (k, v)
            for k, v in urllib.parse.parse_qsl(parsed.query, keep_blank_values=False)
            if k.lower() not in TRACKING_QUERY_PARAMS and not k.lower().startswith("utm_")
        ]
        clean_query = urllib.parse.urlencode(kept_params)
        clean_path = parsed.path or "/"
        rebuilt = urllib.parse.urlunsplit(
            (parsed.scheme.lower(), parsed.netloc.lower(), clean_path, clean_query, "")
        )
        # Keep root URLs tidy without trailing '?'
        return rebuilt.rstrip("?")
    except Exception:
        return url


def extract_root_domain(url: Optional[str]) -> str:
    """
    Extract normalized root domain (stripping scheme, ports, www., m., mobile.).
    """
    if not url or not str(url).strip():
        return ""
    try:
        raw = str(url).strip()
        if "://" not in raw:
            raw = "https://" + raw
        parsed = urllib.parse.urlsplit(raw)
        host = (parsed.hostname or "").lower().strip()
        for prefix in ("www.", "m.", "mobile."):
            if host.startswith(prefix):
                host = host[len(prefix) :]
        return host
    except Exception:
        return ""


def _domain_matches_set(domain: str, domain_set: set) -> Optional[str]:
    """
    Check if `domain` equals or is a subdomain of any entry in `domain_set`.
    Returns the matched base domain string, or None.
    """
    if not domain:
        return None
    for entry in domain_set:
        if domain == entry or domain.endswith("." + entry):
            return entry
    return None


def _clean_social_profile(raw_url: str) -> str:
    """Strip www/mobile subdomains (m.facebook.com -> facebook.com) and tracking params."""
    try:
        parsed = urllib.parse.urlsplit(raw_url.strip())
        host = (parsed.hostname or "").lower()
        for prefix in ("www.", "m.", "mobile."):
            if host.startswith(prefix):
                host = host[len(prefix) :]
        clean = urllib.parse.urlunsplit(("https", host, parsed.path, "", ""))
        return clean.rstrip("/")
    except Exception:
        return raw_url.strip()


def classify_candidate_url(
    raw_url: Optional[str],
) -> Tuple[Optional[str], Dict[str, Optional[str]], bool]:
    """
    Classify a candidate URL discovered from Maps or Web Search.

    Returns:
        (clean_website_url, prefilled_socials, is_aggregator_only)
        - Social-only URL (e.g. m.facebook.com/plumb.masters/) ->
          (None, {'facebook': 'https://facebook.com/plumb.masters'}, False)
        - Link-in-bio / deprecated business.site ->
          (None, {}, False)
        - Aggregator directory URL (e.g. yelp.com/biz/...) ->
          (None, {}, True)
        - Genuine owned website URL ->
          (canonical_url, {}, False)
    """
    clean_url = canonicalize_url(raw_url)
    if not clean_url:
        return None, {}, False

    domain = extract_root_domain(clean_url)
    lowered_url = clean_url.lower()

    # 1. Social-only / link-in-bio / deprecated Google business.site
    matched_social_domain = _domain_matches_set(domain, set(SOCIAL_ONLY_WEBSITE_DOMAINS.keys()))
    if matched_social_domain is not None:
        platform = SOCIAL_ONLY_WEBSITE_DOMAINS[matched_social_domain]
        prefilled: Dict[str, Optional[str]] = {}
        if platform:
            cleaned_social = _clean_social_profile(clean_url)
            # Ensure URL points to an actual profile path, not bare homepage
            path_part = urllib.parse.urlsplit(cleaned_social).path.strip("/")
            if path_part:
                prefilled[platform] = cleaned_social
        log.info(
            f"Social-as-website detected ({domain}) -> routed to socials={list(prefilled.keys())}, website_url=None"
        )
        return None, prefilled, False

    # 2. Aggregator / directory domains or listicle paths
    if _domain_matches_set(domain, AGGREGATOR_DOMAINS) is not None:
        return None, {}, True

    if any(pattern in lowered_url for pattern in AGGREGATOR_PATH_PATTERNS):
        return None, {}, True

    return clean_url, {}, False


def _clean_business_name(raw_name: str) -> str:
    """
    Clean and normalize raw business names extracted from Maps or search titles.
    """
    patterns = [
        r"\s*[\|–—-]\s*(Home|Official Site|Welcome|About|Contact|Services).*$",
        r"\s*[\|–—-]\s*\w+,\s*\w{2}\s*$",
        r"\s*\.\.\.\s*$",
    ]
    name = raw_name or ""
    for pattern in patterns:
        name = re.sub(pattern, "", name, flags=re.IGNORECASE)
    return name.strip()


def _is_franchise(business_name: str, domain: str = "") -> bool:
    """Return True if business name or domain matches known multi-state franchises."""
    haystack = f"{business_name} {domain}".lower()
    return any(brand in haystack for brand in FRANCHISE_BRANDS)


def _extract_business_status(item: dict) -> str:
    """Inspect SerpApi Google Maps item for permanently or temporarily closed flags."""
    raw_fields = " ".join(
        str(item.get(k, ""))
        for k in ("open_state", "business_status", "operating_hours", "hours")
    ).lower()
    if "permanently closed" in raw_fields or "closed_permanently" in raw_fields:
        return "CLOSED_PERMANENTLY"
    if "temporarily closed" in raw_fields or "closed_temporarily" in raw_fields:
        return "CLOSED_TEMPORARILY"
    return "OPERATIONAL"


def _parse_float(value: object) -> Optional[float]:
    if value is None:
        return None
    try:
        return round(float(value), 1)
    except (ValueError, TypeError):
        return None


def _parse_int(value: object, default: int = 0) -> int:
    if value is None:
        return default
    try:
        return int(str(value).replace(",", "").strip())
    except (ValueError, TypeError):
        return default


def _search_serpapi(
    city: str,
    industry: str,
    max_results: int = 10,
    start: int = 0,
) -> List[RawCandidate]:
    """
    Priority 1: Query SerpApi Google Maps engine to discover rich local business leads.
    Supports `start` pagination offset. Filters out closed listings, strips aggregator
    URLs, splits social-only URLs into `prefilled_socials`, and flags franchises.
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
    if start > 0:
        params["start"] = str(start)

    log.info(
        f"Priority 1: Searching SerpApi (Google Maps) -> '{industry}' in '{city}' (start={start})"
    )
    candidates: List[RawCandidate] = []

    try:
        response = stealth.get(url, params=params, timeout=REQUEST_TIMEOUT)

        if response.status_code == 429:
            log.warning("SerpApi returned HTTP 429. Falling back to Priority 2 (Brave).")
            return []

        if response.status_code != 200:
            log.warning(f"SerpApi returned HTTP {response.status_code}")
            return []

        data = response.json()
        if "error" in data:
            log.warning(f"SerpApi JSON error: {data['error']}. Falling back to Priority 2.")
            return []

        local_results = data.get("local_results", [])
        for item in local_results:
            biz_status = _extract_business_status(item)
            if biz_status == "CLOSED_PERMANENTLY":
                log.info(f"Filtered permanently closed business: '{item.get('title', '')}'")
                continue

            raw_title = item.get("title", "")
            biz_name = _clean_business_name(raw_title)
            if not biz_name or len(biz_name) < 2:
                continue

            raw_website = item.get("website")
            clean_website, prefilled_socials, is_agg = classify_candidate_url(raw_website)
            if is_agg:
                log.info(
                    f"Stripped aggregator website ({raw_website}) for Maps business '{biz_name}' -> NO_WEBSITE"
                )
                clean_website = None

            domain = extract_root_domain(clean_website)
            place_id = item.get("place_id") or item.get("data_id")
            phone = str(item.get("phone")).strip() if item.get("phone") else None
            address = str(item.get("address")).strip() if item.get("address") else None

            candidates.append(
                RawCandidate(
                    place_id=str(place_id) if place_id else None,
                    business_name=biz_name,
                    city=city,
                    industry=industry,
                    phone=phone,
                    address=address,
                    rating=_parse_float(item.get("rating")),
                    reviews_count=_parse_int(item.get("reviews"), default=0),
                    business_status=biz_status,
                    is_franchise=_is_franchise(biz_name, domain),
                    website_url=clean_website,
                    prefilled_socials=prefilled_socials,
                )
            )

            if len(candidates) >= max_results:
                break

        log.info(f"SerpApi discovered {len(candidates)} clean candidates for '{industry}' in '{city}'")
    except Exception as exc:
        log.error(f"SerpApi search failed for '{industry}' in '{city}': {exc}")

    return candidates


def _search_brave(
    city: str,
    industry: str,
    max_results: int = 10,
    offset: int = 0,
) -> List[RawCandidate]:
    """
    Priority 2: Query Brave Search API as discovery fallback.
    Discards directory/listicle results entirely and emits typed RawCandidate objects.
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

    query = f"{industry} services in {city} -yelp -yellowpages -angi -thumbtack"
    url = "https://api.search.brave.com/res/v1/web/search"
    headers = {
        "Accept": "application/json",
        "Accept-Encoding": "gzip",
        "X-Subscription-Token": BRAVE_API_KEY,
    }
    params: Dict[str, object] = {
        "q": query,
        "count": min(max_results * 2, 20),
    }
    if offset > 0:
        params["offset"] = offset

    log.info(
        f"Priority 2: Searching Brave Search API -> '{industry}' in '{city}' (offset={offset})"
    )
    candidates: List[RawCandidate] = []

    try:
        response = stealth.get(url, headers=headers, params=params, timeout=REQUEST_TIMEOUT)

        if response.status_code == 429:
            log.warning("Brave API returned HTTP 429 (Rate limited/Quota exhausted).")
            return []

        if response.status_code != 200:
            log.warning(f"Brave API returned HTTP {response.status_code}")
            return []

        data = response.json()
        web_results = data.get("web", {}).get("results", [])

        for item in web_results:
            raw_title = item.get("title", "")
            href = item.get("url", "")
            biz_name = _clean_business_name(raw_title)

            if not biz_name or len(biz_name) < 2:
                continue

            clean_website, prefilled_socials, is_agg = classify_candidate_url(href)
            # For web search results, aggregator/listicle pages are NOT individual businesses
            if is_agg:
                continue

            domain = extract_root_domain(clean_website)
            candidates.append(
                RawCandidate(
                    business_name=biz_name,
                    city=city,
                    industry=industry,
                    is_franchise=_is_franchise(biz_name, domain),
                    website_url=clean_website,
                    prefilled_socials=prefilled_socials,
                )
            )

            if len(candidates) >= max_results:
                break

        log.info(f"Brave API discovered {len(candidates)} clean candidates for '{industry}' in '{city}'")
    except Exception as exc:
        log.error(f"Brave API search failed for '{industry}' in '{city}': {exc}")

    return candidates


def discover_leads(
    city: str,
    industry: str,
    max_results: int = 10,
    start: int = 0,
) -> List[RawCandidate]:
    """
    Orchestrate business discovery across the fallback chain:
    Priority 1 (SerpApi Google Maps) -> Priority 2 (Brave Search) -> graceful [].
    """
    candidates = _search_serpapi(
        city=city,
        industry=industry,
        max_results=max_results,
        start=start,
    )
    if candidates:
        return candidates

    brave_offset = start // 20 if start > 0 else 0
    candidates = _search_brave(
        city=city,
        industry=industry,
        max_results=max_results,
        offset=brave_offset,
    )
    if candidates:
        return candidates

    log.warning(f"No leads discovered or quotas exhausted for '{industry}' in '{city}'.")
    return []
