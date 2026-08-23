"""
extractor.py — Contact Data & Social Media Extraction Engine.

Single responsibility: Extract contact information (email address) and social media
profiles (LinkedIn, Instagram, Facebook, Twitter/X) from a validated live business website URL.
Does not discover businesses. Does not validate URLs.
All outgoing HTTP requests route strictly through stealth.py using a persistent session.
"""

import re
import urllib.parse
from typing import Any, Dict, List, Optional, Set, Tuple

from bs4 import BeautifulSoup

try:
    from config import HUNTER_API_KEY, HUNTER_MONTHLY_QUOTA, REQUEST_TIMEOUT
except ImportError:
    HUNTER_API_KEY = ""
    HUNTER_MONTHLY_QUOTA = 25
    REQUEST_TIMEOUT = 30

from logger import setup_logger
import stealth
import tracker

log = setup_logger("extractor")

# Regex for detecting email addresses
EMAIL_REGEX = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")

# Domain substrings to discard during regex filtering
EMAIL_FILTER_BLACKLIST = {
    "example.com", "domain.com", "sentry.io", "wixpress.com", "wix.com",
    "wordpress.org", "wordpress.com", "schema.org", "googleapis.com",
    "github.com", "cloudflare.com", ".png", ".jpg", ".jpeg", ".svg", ".webp",
}

# Domains mapping to target social platforms
SOCIAL_DOMAINS = {
    "linkedin": ["linkedin.com/company/", "linkedin.com/in/"],
    "instagram": ["instagram.com/"],
    "facebook": ["facebook.com/"],
    "twitter": ["twitter.com/", "x.com/"],
}

# Substrings to discard when checking social links (generic share/intent/login buttons)
SOCIAL_SHARE_PATTERNS = {
    "sharer", "share", "intent", "login", "dialog", "signup", "plugins",
    "tr?id=", "sharer.php", "home.php", "search", "policies",
}


def _extract_domain(url: str) -> str:
    """
    Extract the root domain / netloc from a URL, stripping leading www.

    Args:
        url: Target web URL.

    Returns:
        str: Cleaned domain string (e.g., 'example.com').
    """
    try:
        parsed = urllib.parse.urlparse(url)
        netloc = parsed.netloc or parsed.path
        netloc = netloc.split(":")[0].strip()
        if netloc.lower().startswith("www."):
            netloc = netloc[4:]
        return netloc.lower()
    except Exception:
        return ""


def _is_valid_email(email: str) -> bool:
    """
    Check if an extracted email is valid and not a platform artifact.

    Args:
        email: Candidate email string.

    Returns:
        bool: True if email passes standard heuristics.
    """
    cleaned = email.strip().lower()
    if len(cleaned) < 6 or "@" not in cleaned:
        return False
    if any(blacklisted in cleaned for blacklisted in EMAIL_FILTER_BLACKLIST):
        return False
    return True


def _clean_social_url(url: str) -> str:
    """
    Normalize and clean a candidate social profile URL.

    Args:
        url: Raw link from DOM or search result.

    Returns:
        str: Cleaned full URL.
    """
    parsed = urllib.parse.urlsplit(url.strip())
    # Strip tracking query params and fragments
    clean = urllib.parse.urlunsplit((parsed.scheme or "https", parsed.netloc, parsed.path, "", ""))
    return clean.rstrip("/")


def _is_valid_social_link(platform: str, href: str) -> bool:
    """
    Validate that an href is an actual profile/page and not a share link or home page.

    Args:
        platform: Target platform ('linkedin', 'instagram', 'facebook', 'twitter').
        href: Extracted href link.

    Returns:
        bool: True if link represents a valid profile.
    """
    lowered = href.lower()
    if any(pat in lowered for pat in SOCIAL_SHARE_PATTERNS):
        return False

    patterns = SOCIAL_DOMAINS.get(platform, [])
    for pat in patterns:
        if pat in lowered:
            parts = lowered.split(pat, 1)
            if len(parts) > 1 and len(parts[1].strip("/?#")) > 0:
                return True
    return False


def _query_hunter_api(domain: str, session: Any) -> Optional[str]:
    """
    Query Hunter.io Domain Search API (Priority 1) for a verified domain email.

    Args:
        domain: Clean business website domain.
        session: Persistent stealth session.

    Returns:
        Optional[str]: Extracted primary email address if found, else None.
    """
    if not HUNTER_API_KEY:
        log.debug("Hunter.io API key not configured. Skipping Priority 1.")
        return None

    try:
        tracker.check_and_increment("hunter", HUNTER_MONTHLY_QUOTA)
    except tracker.QuotaExhaustedError as exc:
        log.warning(f"Hunter.io quota reached: {exc}. Falling back to Priority 2.")
        return None
    except Exception as exc:
        log.error(f"Unexpected tracker check failure for Hunter.io: {exc}")
        return None

    try:
        api_url = f"https://api.hunter.io/v2/domain-search?domain={domain}&api_key={HUNTER_API_KEY}"
        response = stealth.get(api_url, session=session, apply_delay=False)

        if response.status_code != 200:
            log.debug(f"Hunter.io API returned HTTP {response.status_code} for domain {domain}")
            return None

        payload = response.json()
        emails = payload.get("data", {}).get("emails", [])
        if emails and len(emails) > 0:
            candidate = emails[0].get("value")
            if candidate and _is_valid_email(candidate):
                log.info(f"Hunter.io found email for {domain}: {candidate}")
                return candidate
    except Exception as exc:
        log.error(f"Hunter.io API query failed for {domain}: {exc}")

    return None


def _fetch_page_dom(
    url: str, session: Any
) -> Tuple[Optional[BeautifulSoup], Optional[int], bool]:
    """
    Fetch a single URL using the shared stealth session and return its parsed DOM.

    Args:
        url: Absolute web URL to fetch.
        session: Persistent stealth session.

    Returns:
        Tuple[Optional[BeautifulSoup], Optional[int], bool]:
            (parsed BeautifulSoup instance, HTTP status code, is_blocked flag)
    """
    try:
        response = stealth.get(url, session=session, apply_delay=True)
        status = response.status_code

        if status in (403, 429, 503):
            # Check for Cloudflare / bot block indication
            return None, status, True

        if status != 200:
            return None, status, False

        text = response.text
        if not text:
            return None, status, False

        # Check for typical bot challenge pages returning HTTP 200
        if "challenge-running" in text or "cf-browser-verification" in text:
            return None, status, True

        soup = BeautifulSoup(text, "html.parser")
        return soup, status, False
    except Exception as exc:
        log.debug(f"Failed to fetch page {url}: {exc}")
        return None, None, False


def _fetch_site_pages(
    base_url: str, session: Any
) -> Tuple[List[BeautifulSoup], bool]:
    """
    Fetch and cache the DOM of the homepage, /contact, and /about pages once.

    Args:
        base_url: Live website URL.
        session: Persistent stealth session.

    Returns:
        Tuple[List[BeautifulSoup], bool]: (List of cached BeautifulSoup DOMs, any_blocked)
    """
    parsed = urllib.parse.urlparse(base_url)
    origin = f"{parsed.scheme}://{parsed.netloc}"

    candidate_urls = [base_url]
    # Common contact and about path variants
    subpaths = ["/contact", "/contact-us", "/about", "/about-us"]
    for path in subpaths:
        candidate_urls.append(urllib.parse.urljoin(origin, path))

    cached_doms: List[BeautifulSoup] = []
    any_blocked = False
    visited_urls: Set[str] = set()

    for url in candidate_urls:
        if url in visited_urls:
            continue
        visited_urls.add(url)

        soup, status, is_blocked = _fetch_page_dom(url, session)
        if is_blocked:
            any_blocked = True
        if soup is not None:
            cached_doms.append(soup)

    return cached_doms, any_blocked


def _extract_email_from_doms(doms: List[BeautifulSoup]) -> Optional[str]:
    """
    Extract email address from cached DOMs inspecting mailto: links first, then regex.

    Args:
        doms: List of parsed BeautifulSoup DOMs for the website.

    Returns:
        Optional[str]: Extracted email address if found, else None.
    """
    # 1. Inspect mailto: links across all cached pages
    for soup in doms:
        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"].strip()
            if href.lower().startswith("mailto:"):
                raw_email = href[7:].split("?")[0].strip()
                if _is_valid_email(raw_email):
                    return raw_email

    # 2. Inspect plain text regex matches across cached pages
    for soup in doms:
        text = soup.get_text(separator=" ")
        matches = EMAIL_REGEX.findall(text)
        for match in matches:
            if _is_valid_email(match):
                return match

    return None


def _extract_socials_from_doms(doms: List[BeautifulSoup]) -> Dict[str, Optional[str]]:
    """
    Extract outbound social media links from cached DOMs.

    Args:
        doms: List of parsed BeautifulSoup DOMs for the website.

    Returns:
        Dict[str, Optional[str]]: Dictionary with platform keys ('linkedin', 'instagram', 'facebook', 'twitter').
    """
    socials: Dict[str, Optional[str]] = {
        "linkedin": None,
        "instagram": None,
        "facebook": None,
        "twitter": None,
    }

    for soup in doms:
        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"].strip()
            for platform in socials:
                if socials[platform] is None and _is_valid_social_link(platform, href):
                    socials[platform] = _clean_social_url(href)

    return socials


def _search_ddg_socials(
    business_name: str, city: str, session: Any
) -> Tuple[Dict[str, Optional[str]], str]:
    """
    Fallback (Priority 2): Query DuckDuckGo HTML search for social media profiles.

    Args:
        business_name: Name of the business.
        city: City / region of the business.
        session: Persistent stealth session.

    Returns:
        Tuple[Dict[str, Optional[str]], str]: (Socials dict, status)
    """
    socials: Dict[str, Optional[str]] = {
        "linkedin": None,
        "instagram": None,
        "facebook": None,
        "twitter": None,
    }

    if not business_name:
        return socials, "NOT_FOUND"

    query = f'"{business_name}" {city} (site:facebook.com OR site:instagram.com OR site:linkedin.com OR site:twitter.com OR site:x.com)'
    ddg_url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"

    try:
        response = stealth.get(ddg_url, session=session, apply_delay=True)

        if response.status_code in (403, 429):
            log.warning(f"DuckDuckGo blocked request (HTTP {response.status_code})")
            return socials, "BLOCKED"

        if response.status_code != 200:
            log.debug(f"DuckDuckGo returned HTTP {response.status_code}")
            return socials, "NOT_FOUND"

        soup = BeautifulSoup(response.text, "html.parser")
        # DDG HTML search results links are in <a> with class 'result__url' or 'result__snippet' / 'result__a'
        for link in soup.find_all("a", href=True):
            raw_href = link["href"]
            # DuckDuckGo wraps URLs in /l/?uddg=<url>
            target_url = raw_href
            if "/l/?uddg=" in raw_href:
                try:
                    parsed_uddg = urllib.parse.parse_qs(urllib.parse.urlparse(raw_href).query)
                    if "uddg" in parsed_uddg:
                        target_url = parsed_uddg["uddg"][0]
                except Exception:
                    pass

            for platform in socials:
                if socials[platform] is None and _is_valid_social_link(platform, target_url):
                    socials[platform] = _clean_social_url(target_url)

        if any(socials.values()):
            return socials, "FOUND_DDG"

        return socials, "NOT_FOUND"

    except Exception as exc:
        log.error(f"DuckDuckGo social search failed for '{business_name}': {exc}")
        return socials, "NOT_FOUND"


def extract_contacts(
    website_url: Optional[str],
    business_name: str = "",
    city: str = "",
) -> Dict[str, Any]:
    """
    Extract contact email and social media profiles from a live business website URL.

    Execution Flow:
    1. If website_url is None/empty -> return immediately with all None & NOT_ATTEMPTED.
    2. Initialize a persistent stealth.get_session() for this business extraction.
    3. Email Priority 1: Hunter.io API.
    4. Fetch & cache site DOMs (homepage, /contact, /about) once.
    5. Email Priority 2: BeautifulSoup scrape on cached DOMs if Priority 1 yielded nothing.
    6. Socials Priority 1: BeautifulSoup scrape on cached DOMs.
    7. Socials Priority 2: DuckDuckGo HTML fallback if Priority 1 yielded nothing.
    8. Dispose session and return complete result dict.

    Args:
        website_url: Live website URL to extract from.
        business_name: Name of the business (used for DDG social fallback).
        city: City or region of the business (used for DDG social fallback).

    Returns:
        dict: Standardized extraction result with exact keys:
              - email: Optional[str]
              - email_status: str
              - linkedin: Optional[str]
              - instagram: Optional[str]
              - facebook: Optional[str]
              - twitter: Optional[str]
              - social_status: str
    """
    if not website_url or not website_url.strip():
        return {
            "email": None,
            "email_status": "NOT_ATTEMPTED",
            "linkedin": None,
            "instagram": None,
            "facebook": None,
            "twitter": None,
            "social_status": "NOT_ATTEMPTED",
        }

    url = website_url.strip()
    if not url.startswith("http://") and not url.startswith("https://"):
        url = "https://" + url

    domain = _extract_domain(url)
    session = stealth.get_session()

    result: Dict[str, Any] = {
        "email": None,
        "email_status": "NOT_FOUND",
        "linkedin": None,
        "instagram": None,
        "facebook": None,
        "twitter": None,
        "social_status": "NOT_FOUND",
    }

    try:
        # ── 1. Email Extraction — Priority 1: Hunter.io API ──────────────────
        hunter_email = _query_hunter_api(domain, session)
        if hunter_email:
            result["email"] = hunter_email
            result["email_status"] = "FOUND_API"

        # ── 2. Fetch and Cache DOMs (Homepage, /contact, /about) ─────────────
        cached_doms, any_blocked = _fetch_site_pages(url, session)

        # ── 3. Email Extraction — Priority 2: BeautifulSoup Scraping ─────────
        if result["email"] is None:
            if cached_doms:
                scraped_email = _extract_email_from_doms(cached_doms)
                if scraped_email:
                    result["email"] = scraped_email
                    result["email_status"] = "FOUND_SCRAPE"
                else:
                    result["email_status"] = "NOT_FOUND"
            elif any_blocked:
                result["email_status"] = "BLOCKED"
            else:
                result["email_status"] = "NOT_FOUND"

        # ── 4. Social Media Extraction — Priority 1: On-Site Outbound Links ──
        if cached_doms:
            on_site_socials = _extract_socials_from_doms(cached_doms)
            result.update(on_site_socials)
            if any(on_site_socials.values()):
                result["social_status"] = "FOUND_ON_SITE"

        # ── 5. Social Media Extraction — Priority 2: DuckDuckGo HTML ─────────
        if result["social_status"] != "FOUND_ON_SITE":
            if any_blocked and not cached_doms:
                result["social_status"] = "BLOCKED"
            else:
                ddg_socials, ddg_status = _search_ddg_socials(business_name, city, session)
                result.update(ddg_socials)
                result["social_status"] = ddg_status

    finally:
        try:
            session.close()
        except Exception:
            pass

    return result
