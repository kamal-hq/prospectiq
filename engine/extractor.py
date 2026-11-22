"""
Contact & Social Extraction Layer — extractor.py

Single responsibility: Extract verified business contact information (ranked emails
with MX validation, optional fallback phone) and official social media profiles from
a validated SiteAudit.

v3.0 Upgrades:
- Reuses `audit.html_body` from validator.py (eliminates homepage double-fetching).
- FREE-FIRST Email Waterfall:
    Tier 1 (FREE): JSON-LD (`application/ld+json` LocalBusiness) on homepage
    Tier 2 (FREE): Homepage DOM (`mailto:` + regex) + dynamic nav-discovered
                   Contact/About links (max 2 requests)
    Tier 3 (METERED FALLBACK): Hunter.io API ONLY if Tiers 1-2 found nothing
                               (never called on social/aggregator domains)
- Email Quality Ranking & Agency/Junk Filtering + cached `dnspython` MX verification.
- Social Link Verification: merges Maps prefilled socials + JSON-LD `sameAs` +
  on-site links (excluding agency credit footers & post/share URLs) -> DDG fallback.
- Routes all outgoing HTTP strictly through stealth.py.
"""

import json
import re
import urllib.parse
from typing import Any, Dict, List, Optional, Set, Tuple

from bs4 import BeautifulSoup

try:
    import dns.resolver
except ImportError:
    dns = None  # type: ignore

from engine.config import (
    AGGREGATOR_DOMAINS,
    EMAIL_DOMAIN_BLACKLIST,
    EMAIL_LOCAL_BLACKLIST_PREFIXES,
    FREE_EMAIL_PROVIDERS,
    HUNTER_API_KEY,
    HUNTER_MONTHLY_QUOTA,
    SOCIAL_ONLY_WEBSITE_DOMAINS,
)
from engine.logger import setup_logger
from engine.models import ContactEnrichment, EmailStatus, SiteAudit, SocialStatus
from engine import stealth
from engine import tracker

log = setup_logger("extractor")

# Strict RFC-practical email regex
EMAIL_REGEX = re.compile(r"\b[a-zA-Z0-9._%+\-]{1,64}@[a-zA-Z0-9.\-]{1,253}\.[a-zA-Z]{2,12}\b")

# File extensions that falsely trigger email regexes in HTML/CSS/JS (e.g. icon@2x.png)
_ASSET_EXTENSIONS = (
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".ico",
    ".css", ".js", ".woff", ".woff2", ".ttf", ".eot", ".pdf", ".mp4",
)

# High-value business inbox local-parts
_PREFERRED_LOCAL_PARTS = {
    "info", "contact", "hello", "office", "service", "services",
    "sales", "estimates", "estimate", "quotes", "quote", "owner",
    "admin", "dispatch", "team", "booking", "appointments", "support",
}

# Social platform patterns
SOCIAL_DOMAINS = {
    "linkedin": ["linkedin.com/company/", "linkedin.com/in/"],
    "instagram": ["instagram.com/"],
    "facebook": ["facebook.com/"],
    "twitter": ["twitter.com/", "x.com/"],
}

# Share buttons, posts, reels, login modals, and non-profile URLs
SOCIAL_EXCLUDE_PATTERNS = {
    "sharer", "share", "intent", "login", "dialog", "signup", "plugins",
    "tr?id=", "sharer.php", "home.php", "search", "policies", "privacy",
    "/p/", "/reel/", "/reels/", "/stories/", "/explore/", "/hashtag/",
    "/watch", "/events/", "/groups/", "/i/", "/status/", "sharearticle",
    "developers.facebook.com", "business.facebook.com", "l.facebook.com",
}

# Footer phrases indicating a web-design agency's own link rather than the client's
_AGENCY_CREDIT_PHRASES = (
    "designed by", "website by", "powered by", "built by",
    "developed by", "web design by", "marketing by", "seo by",
)

# In-memory cache of domain -> MX valid bool
_MX_CACHE: Dict[str, Optional[bool]] = {}


def _extract_domain(url: str) -> str:
    try:
        raw = url if "://" in url else f"https://{url}"
        parsed = urllib.parse.urlsplit(raw)
        host = (parsed.hostname or "").lower().strip()
        for prefix in ("www.", "m.", "mobile."):
            if host.startswith(prefix):
                host = host[len(prefix) :]
        return host
    except Exception:
        return ""


def _domain_matches(domain: str, domain_set: Set[str]) -> bool:
    return any(domain == d or domain.endswith("." + d) for d in domain_set)


def _brand_tokens(business_name: str, site_domain: str) -> Set[str]:
    """Extract meaningful alphanumeric brand tokens (len >= 3) for relevance checks."""
    stop_words = {
        "the", "and", "llc", "inc", "corp", "company", "services", "service",
        "pro", "pros", "group", "solutions", "tx", "fl", "ga", "nc", "az", "co",
        "com", "net", "org", "www",
    }
    raw = f"{business_name} {site_domain.split('.')[0] if site_domain else ''}".lower()
    tokens = set(re.findall(r"[a-z0-9]{3,}", raw))
    return tokens - stop_words


def _clean_email_candidate(raw: str) -> str:
    """Decode URL encoding and strip leading/trailing punctuation/unicode artifacts."""
    decoded = urllib.parse.unquote(raw or "").strip()
    # Remove common JSON/HTML escape prefixes like u003einfo@...
    decoded = re.sub(r"^(?:u003[ce]|20|%20|mailto:)+", "", decoded, flags=re.IGNORECASE)
    return decoded.strip(" .,:;<>\"'()[]{}").lower()


def _is_valid_email(email: str) -> bool:
    cleaned = _clean_email_candidate(email)
    if len(cleaned) < 6 or len(cleaned) > 120 or "@" not in cleaned:
        return False
    if cleaned.count("@") != 1:
        return False

    local, domain = cleaned.split("@", 1)
    if not local or "." not in domain:
        return False
    if any(cleaned.endswith(ext) for ext in _ASSET_EXTENSIONS):
        return False
    if _domain_matches(domain, EMAIL_DOMAIN_BLACKLIST):
        return False
    if any(local == pref or local.startswith(pref + ".") or local.startswith(pref + "-") or local.startswith(pref + "_") for pref in EMAIL_LOCAL_BLACKLIST_PREFIXES):
        return False
    # Reject 24+ char hex-hash machine IDs (Sentry/UUID artifacts)
    if re.fullmatch(r"[0-9a-f]{20,}", local):
        return False
    return True


def _rank_emails(
    candidates: List[str],
    site_domain: str,
    business_name: str,
) -> List[str]:
    """
    Deduplicate, filter out unrelated third-party/agency emails, and rank candidates
    so the best business outreach email comes first.
    """
    tokens = _brand_tokens(business_name, site_domain)
    scored: List[Tuple[int, str]] = []
    seen: Set[str] = set()

    for raw in candidates:
        email = _clean_email_candidate(raw)
        if email in seen or not _is_valid_email(email):
            continue
        seen.add(email)

        local, email_domain = email.split("@", 1)
        score = 0

        # 1. Exact or subdomain match with the business website domain
        if site_domain and (email_domain == site_domain or email_domain.endswith("." + site_domain)):
            score += 50
            if local in _PREFERRED_LOCAL_PARTS:
                score += 20
            else:
                score += 15  # Named individual at the company domain
        # 2. Free webmail provider (common for small trades)
        elif email_domain in FREE_EMAIL_PROVIDERS:
            if any(tok in local for tok in tokens):
                score += 30
            else:
                score += 12
        # 3. Third-party custom domain (frequently a web-design agency's footer email!)
        else:
            domain_stem = email_domain.split(".")[0]
            if any(tok in domain_stem or tok in local for tok in tokens):
                score += 25
            else:
                # Drop unrelated third-party agency/vendor domains
                log.debug(f"Filtered likely third-party/agency email: {email} (site={site_domain})")
                continue

        scored.append((score, email))

    scored.sort(key=lambda item: (-item[0], item[1]))
    return [email for _, email in scored]


def verify_email_mx(email: Optional[str]) -> Optional[bool]:
    """
    Verify that an email's domain has active DNS MX (or RFC 5321 fallback A) records.
    Cached per domain in memory. Returns None if dnspython is unavailable.
    """
    if not email or "@" not in email:
        return None
    domain = email.split("@", 1)[1].strip().lower()
    if domain in _MX_CACHE:
        return _MX_CACHE[domain]

    if dns is None or not hasattr(dns, "resolver"):
        return None

    try:
        resolver = dns.resolver.Resolver(configure=False)
        resolver.nameservers = ["1.1.1.1", "8.8.8.8", "9.9.9.9"]
        resolver.timeout = 4.0
        resolver.lifetime = 5.0

        try:
            mx_answers = resolver.resolve(domain, "MX")
            # Reject null MX ("0 .") per RFC 7505
            valid_mx = any(str(r.exchange).strip(".") != "" for r in mx_answers)
            _MX_CACHE[domain] = valid_mx
            return valid_mx
        except (dns.resolver.NoAnswer, dns.resolver.NoNameservers):
            # RFC 5321 fallback: domain with A record can still receive mail
            try:
                a_answers = resolver.resolve(domain, "A")
                valid_a = len(list(a_answers)) > 0
                _MX_CACHE[domain] = valid_a
                return valid_a
            except Exception:
                _MX_CACHE[domain] = False
                return False
        except dns.resolver.NXDOMAIN:
            _MX_CACHE[domain] = False
            return False
    except Exception as exc:
        log.debug(f"MX verification error for {domain}: {exc}")
        return None


def _clean_social_url(url: str) -> str:
    parsed = urllib.parse.urlsplit(url.strip())
    host = (parsed.hostname or "").lower()
    for prefix in ("www.", "m.", "mobile."):
        if host.startswith(prefix):
            host = host[len(prefix) :]
    clean = urllib.parse.urlunsplit(("https", host or parsed.netloc, parsed.path, "", ""))
    return clean.rstrip("/")


def _is_valid_social_link(platform: str, href: str) -> bool:
    if not href:
        return False
    lowered = href.lower().strip()
    if any(pat in lowered for pat in SOCIAL_EXCLUDE_PATTERNS):
        return False

    for pat in SOCIAL_DOMAINS.get(platform, []):
        if pat in lowered:
            after = lowered.split(pat, 1)[1].strip("/?#")
            if after and len(after) >= 2:
                return True
    return False


def _is_inside_agency_credit(a_tag: Any) -> bool:
    """Return True if an anchor sits inside a 'Website designed by ...' footer credit."""
    parent = a_tag.parent
    for _ in range(2):
        if parent is None:
            break
        txt = parent.get_text(" ", strip=True).lower()[:200]
        if any(phrase in txt for phrase in _AGENCY_CREDIT_PHRASES):
            return True
        parent = parent.parent
    return False


def _extract_jsonld(soup: BeautifulSoup) -> Tuple[List[str], Dict[str, Optional[str]], Optional[str]]:
    """
    Parse all `<script type="application/ld+json">` blocks for LocalBusiness
    `email`, `sameAs` social profiles, and fallback `telephone`.
    """
    emails: List[str] = []
    socials: Dict[str, Optional[str]] = {
        "linkedin": None,
        "instagram": None,
        "facebook": None,
        "twitter": None,
    }
    phone: Optional[str] = None

    def _walk(node: Any) -> None:
        nonlocal phone
        if isinstance(node, list):
            for item in node:
                _walk(item)
            return
        if not isinstance(node, dict):
            return

        if "email" in node and isinstance(node["email"], str):
            emails.append(node["email"])

        if not phone and "telephone" in node and isinstance(node["telephone"], str):
            cand_phone = node["telephone"].strip()
            if len(cand_phone) >= 7:
                phone = cand_phone

        same_as = node.get("sameAs")
        if isinstance(same_as, str):
            same_as = [same_as]
        if isinstance(same_as, list):
            for link in same_as:
                if not isinstance(link, str):
                    continue
                for platform in socials:
                    if socials[platform] is None and _is_valid_social_link(platform, link):
                        socials[platform] = _clean_social_url(link)

        for key in ("@graph", "contactPoint", "publisher", "author", "department"):
            if key in node:
                _walk(node[key])

    for script in soup.find_all("script", attrs={"type": re.compile(r"ld\+json", re.I)}):
        raw_json = script.string or script.get_text() or ""
        if not raw_json.strip():
            continue
        try:
            parsed = json.loads(raw_json)
            _walk(parsed)
        except Exception:
            continue

    return emails, socials, phone


def _extract_emails_from_dom(soup: BeautifulSoup) -> Tuple[List[str], Optional[str]]:
    """Extract candidate emails (`mailto:` first, then visible text) and fallback `tel:` phone."""
    found: List[str] = []
    tel_phone: Optional[str] = None

    for a_tag in soup.find_all("a", href=True):
        href = str(a_tag["href"]).strip()
        lower_href = href.lower()
        if lower_href.startswith("mailto:"):
            if _is_inside_agency_credit(a_tag):
                continue
            raw_email = href[7:].split("?")[0].strip()
            if raw_email:
                found.append(raw_email)
        elif not tel_phone and lower_href.startswith("tel:"):
            raw_tel = urllib.parse.unquote(href[4:]).strip()
            if len(re.sub(r"\D", "", raw_tel)) >= 10:
                tel_phone = raw_tel

    # Strip script/style noise before text regex scan
    visible_text = soup.get_text(separator=" ")
    for match in EMAIL_REGEX.findall(visible_text):
        found.append(match)

    return found, tel_phone


def _extract_socials_from_dom(soup: BeautifulSoup) -> Dict[str, Optional[str]]:
    """Extract outbound social profile links while ignoring agency footer credits."""
    socials: Dict[str, Optional[str]] = {
        "linkedin": None,
        "instagram": None,
        "facebook": None,
        "twitter": None,
    }
    for a_tag in soup.find_all("a", href=True):
        href = str(a_tag["href"]).strip()
        if _is_inside_agency_credit(a_tag):
            continue
        for platform in socials:
            if socials[platform] is None and _is_valid_social_link(platform, href):
                socials[platform] = _clean_social_url(href)
    return socials


def _discover_contact_urls(
    homepage_soup: BeautifulSoup,
    base_url: str,
    site_domain: str,
    max_pages: int = 2,
) -> List[str]:
    """
    Inspect the homepage's actual `<a href>` navigation links to locate real Contact / About
    pages on the same domain instead of blindly probing 4 hardcoded paths.
    """
    scored_urls: List[Tuple[int, str]] = []
    seen: Set[str] = {base_url.rstrip("/")}

    for a_tag in homepage_soup.find_all("a", href=True):
        href = str(a_tag["href"]).strip()
        if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
            continue
        full_url = urllib.parse.urljoin(base_url, href).split("#")[0].rstrip("/")
        if full_url in seen:
            continue
        if _extract_domain(full_url) != site_domain:
            continue

        path_and_text = f"{urllib.parse.urlsplit(full_url).path} {a_tag.get_text(' ', strip=True)}".lower()
        priority = 0
        if "contact" in path_and_text:
            priority = 10
        elif any(k in path_and_text for k in ("quote", "estimate", "reach", "schedule")):
            priority = 7
        elif "about" in path_and_text or "team" in path_and_text:
            priority = 5

        if priority > 0:
            seen.add(full_url)
            scored_urls.append((priority, full_url))

    scored_urls.sort(key=lambda item: (-item[0], len(item[1])))
    discovered = [u for _, u in scored_urls[:max_pages]]

    # Gentle single fallback if homepage had zero contact links (e.g. JS menu)
    if not discovered:
        parsed = urllib.parse.urlsplit(base_url)
        origin = f"{parsed.scheme}://{parsed.netloc}"
        discovered.append(urllib.parse.urljoin(origin, "/contact"))

    return discovered


def _fetch_page_dom(url: str, session: Any) -> Tuple[Optional[BeautifulSoup], bool]:
    """Fetch a subpage through stealth.py and return (soup, is_blocked)."""
    try:
        response = stealth.get(url, session=session, apply_delay=True)
        status = response.status_code
        if status in (403, 429, 503):
            return None, True
        if status != 200 or not response.text:
            return None, False
        if "challenge-running" in response.text or "cf-browser-verification" in response.text:
            return None, True
        return BeautifulSoup(response.text, "html.parser"), False
    except Exception as exc:
        log.debug(f"Failed to fetch subpage {url}: {exc}")
        return None, False


def _query_hunter_api(
    domain: str,
    business_name: str,
    session: Any,
) -> Tuple[List[str], Optional[str]]:
    """
    Tier 3 Fallback: Query Hunter.io Domain Search API ONLY when free extraction fails.
    Never called on social or aggregator domains.
    Returns (ranked_emails, failure_status_override).
    """
    if not HUNTER_API_KEY:
        log.debug("Hunter.io API key not configured. Skipping Hunter fallback.")
        return [], None

    if (
        not domain
        or _domain_matches(domain, AGGREGATOR_DOMAINS)
        or _domain_matches(domain, set(SOCIAL_ONLY_WEBSITE_DOMAINS.keys()))
        or _domain_matches(domain, EMAIL_DOMAIN_BLACKLIST)
    ):
        log.debug(f"Blocked Hunter.io lookup on blacklisted/non-owned domain: {domain}")
        return [], None

    try:
        tracker.check_and_increment("hunter", HUNTER_MONTHLY_QUOTA)
    except tracker.QuotaExhaustedError as exc:
        log.warning(f"Hunter.io quota exhausted: {exc}")
        return [], "QUOTA_EXHAUSTED"
    except Exception as exc:
        log.error(f"Tracker check failed for Hunter.io: {exc}")
        return [], None

    try:
        api_url = f"https://api.hunter.io/v2/domain-search?domain={domain}&api_key={HUNTER_API_KEY}"
        response = stealth.get(api_url, session=session, apply_delay=False)

        if response.status_code == 429:
            log.warning("Hunter.io returned HTTP 429 (Quota/Rate limit).")
            return [], "QUOTA_EXHAUSTED"
        if response.status_code != 200:
            log.debug(f"Hunter.io returned HTTP {response.status_code} for {domain}")
            return [], None

        payload = response.json()
        emails_data = payload.get("data", {}).get("emails", [])
        raw_emails = [e.get("value", "") for e in emails_data if e.get("value")]
        ranked = _rank_emails(raw_emails, domain, business_name)
        if ranked:
            log.info(f"Hunter.io fallback found email for {domain}: {ranked[0]}")
        return ranked, None
    except Exception as exc:
        log.error(f"Hunter.io fallback failed for {domain}: {exc}")
        return [], None


def _search_ddg_socials(
    business_name: str,
    city: str,
    site_domain: str,
    session: Any,
) -> Tuple[Dict[str, Optional[str]], SocialStatus]:
    """
    Tier 2 Social Fallback: Query DuckDuckGo HTML search and verify URLs share at
    least one brand token so unrelated profiles are not attached.
    """
    socials: Dict[str, Optional[str]] = {
        "linkedin": None,
        "instagram": None,
        "facebook": None,
        "twitter": None,
    }
    if not business_name:
        return socials, "NOT_FOUND"

    tokens = _brand_tokens(business_name, site_domain)
    query = (
        f'"{business_name}" {city} '
        "(site:facebook.com OR site:instagram.com OR site:linkedin.com OR site:x.com)"
    )
    ddg_url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"

    try:
        response = stealth.get(ddg_url, session=session, apply_delay=True)
        if response.status_code in (403, 429):
            log.warning(f"DuckDuckGo blocked request (HTTP {response.status_code})")
            return socials, "BLOCKED"
        if response.status_code != 200:
            return socials, "NOT_FOUND"

        soup = BeautifulSoup(response.text, "html.parser")
        for link in soup.find_all("a", href=True):
            raw_href = str(link["href"])
            target_url = raw_href
            if "/l/?uddg=" in raw_href:
                try:
                    qs = urllib.parse.parse_qs(urllib.parse.urlparse(raw_href).query)
                    if "uddg" in qs:
                        target_url = qs["uddg"][0]
                except Exception:
                    pass

            for platform in socials:
                if socials[platform] is None and _is_valid_social_link(platform, target_url):
                    clean = _clean_social_url(target_url)
                    # Sanity check: require at least one brand token in URL or link text
                    haystack = f"{clean} {link.get_text(' ', strip=True)}".lower()
                    if not tokens or any(tok in haystack for tok in tokens):
                        socials[platform] = clean

        if any(socials.values()):
            return socials, "FOUND_DDG"
        return socials, "NOT_FOUND"
    except Exception as exc:
        log.error(f"DuckDuckGo social fallback failed for '{business_name}': {exc}")
        return socials, "NOT_FOUND"


def extract_contacts(
    audit: SiteAudit,
    business_name: str = "",
    city: str = "",
    prefilled_socials: Optional[Dict[str, Optional[str]]] = None,
) -> ContactEnrichment:
    """
    Extract verified email & social profiles using a Free-First waterfall.
    Reuses `audit.html_body` from validator.py to eliminate homepage double-fetching.
    """
    socials: Dict[str, Optional[str]] = {
        "linkedin": None,
        "instagram": None,
        "facebook": None,
        "twitter": None,
    }
    social_status: SocialStatus = "NOT_ATTEMPTED"

    # Merge any social profile already discovered on Google Maps (Social-as-Website)
    if prefilled_socials:
        for k in socials:
            if prefilled_socials.get(k):
                socials[k] = prefilled_socials[k]
        if any(socials.values()):
            social_status = "FOUND_MAPS"

    # If business has no live website, never burn Hunter.io credits or scrape dead URLs
    if not audit.website_found or not audit.website_url:
        return ContactEnrichment(
            email=None,
            email_status="NOT_ATTEMPTED",
            email_mx_valid=None,
            secondary_emails=[],
            linkedin=socials["linkedin"],
            instagram=socials["instagram"],
            facebook=socials["facebook"],
            twitter=socials["twitter"],
            social_status=social_status,
        )

    site_url = audit.website_url
    site_domain = audit.root_domain or _extract_domain(site_url)
    email_status: EmailStatus = "NOT_FOUND"
    best_email: Optional[str] = None
    secondary_emails: List[str] = []
    extracted_phone: Optional[str] = None
    any_blocked = audit.website_status == "WAF_PROTECTED"

    # ── TIER 1 & 2 (FREE): Reuse Homepage HTML from validator.py ─────────
    homepage_soup: Optional[BeautifulSoup] = None
    if audit.html_body:
        homepage_soup = BeautifulSoup(audit.html_body, "html.parser")

        # 1a. JSON-LD structured data (highest quality!)
        jsonld_emails, jsonld_socials, jsonld_phone = _extract_jsonld(homepage_soup)
        if jsonld_phone:
            extracted_phone = jsonld_phone
        for k, v in jsonld_socials.items():
            if v and not socials[k]:
                socials[k] = v
                social_status = "FOUND_ON_SITE"

        ranked_jsonld = _rank_emails(jsonld_emails, site_domain, business_name)
        if ranked_jsonld:
            best_email = ranked_jsonld[0]
            secondary_emails = ranked_jsonld[1:4]
            email_status = "FOUND_JSONLD"

        # 1b. Homepage DOM `mailto:` + visible text + outbound social anchors
        dom_emails, dom_phone = _extract_emails_from_dom(homepage_soup)
        if not extracted_phone and dom_phone:
            extracted_phone = dom_phone

        dom_socials = _extract_socials_from_dom(homepage_soup)
        for k, v in dom_socials.items():
            if v and not socials[k]:
                socials[k] = v
                social_status = "FOUND_ON_SITE"

        if not best_email:
            ranked_home = _rank_emails(dom_emails, site_domain, business_name)
            if ranked_home:
                best_email = ranked_home[0]
                secondary_emails = ranked_home[1:4]
                email_status = "FOUND_SCRAPE"

    # Only open a stealth session if we still need Contact subpages, Hunter, or DDG
    need_subpages = best_email is None and homepage_soup is not None and not any_blocked
    need_hunter = best_email is None
    need_ddg = not any(socials.values()) and not any_blocked

    if need_subpages or need_hunter or need_ddg:
        session = stealth.get_session()
        try:
            # 2. Smart Nav-Discovered Contact/About Subpages (max 2 requests)
            if need_subpages and homepage_soup is not None:
                subpage_urls = _discover_contact_urls(homepage_soup, site_url, site_domain, max_pages=2)
                sub_emails: List[str] = []
                for sub_url in subpage_urls:
                    sub_soup, blocked = _fetch_page_dom(sub_url, session)
                    if blocked:
                        any_blocked = True
                        continue
                    if sub_soup is None:
                        continue

                    j_emails, j_socials, j_phone = _extract_jsonld(sub_soup)
                    sub_emails.extend(j_emails)
                    if not extracted_phone and j_phone:
                        extracted_phone = j_phone
                    for k, v in j_socials.items():
                        if v and not socials[k]:
                            socials[k] = v
                            social_status = "FOUND_ON_SITE"

                    d_emails, d_phone = _extract_emails_from_dom(sub_soup)
                    sub_emails.extend(d_emails)
                    if not extracted_phone and d_phone:
                        extracted_phone = d_phone
                    for k, v in _extract_socials_from_dom(sub_soup).items():
                        if v and not socials[k]:
                            socials[k] = v
                            social_status = "FOUND_ON_SITE"

                    ranked_sub = _rank_emails(sub_emails, site_domain, business_name)
                    if ranked_sub:
                        best_email = ranked_sub[0]
                        secondary_emails = ranked_sub[1:4]
                        email_status = "FOUND_SCRAPE"
                        break  # Stop fetching further subpages once we have a clean email!

            # 3. TIER 3 (METERED FALLBACK): Hunter.io ONLY if free extraction found nothing
            if best_email is None:
                hunter_emails, hunter_override = _query_hunter_api(site_domain, business_name, session)
                if hunter_emails:
                    best_email = hunter_emails[0]
                    secondary_emails = hunter_emails[1:4]
                    email_status = "FOUND_API"
                elif hunter_override == "QUOTA_EXHAUSTED":
                    email_status = "QUOTA_EXHAUSTED"
                elif any_blocked:
                    email_status = "BLOCKED"
                else:
                    email_status = "NOT_FOUND"

            # 4. Socials Tier 2: DuckDuckGo HTML fallback if still zero socials
            if not any(socials.values()):
                if any_blocked and homepage_soup is None:
                    social_status = "BLOCKED"
                else:
                    ddg_socials, ddg_status = _search_ddg_socials(
                        business_name, city, site_domain, session
                    )
                    for k, v in ddg_socials.items():
                        if v:
                            socials[k] = v
                    social_status = ddg_status
        finally:
            try:
                session.close()
            except Exception:
                pass
    else:
        if not any(socials.values()):
            social_status = "BLOCKED" if any_blocked else "NOT_FOUND"

    # 5. DNS MX Verification on chosen primary email
    mx_valid = verify_email_mx(best_email) if best_email else None

    return ContactEnrichment(
        email=best_email,
        email_status=email_status,
        email_mx_valid=mx_valid,
        secondary_emails=secondary_emails,
        linkedin=socials["linkedin"],
        instagram=socials["instagram"],
        facebook=socials["facebook"],
        twitter=socials["twitter"],
        social_status=social_status,
        extracted_phone=extracted_phone,
    )
