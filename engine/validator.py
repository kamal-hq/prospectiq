"""
Validator & Digital Audit Layer — validator.py

Single responsibility: Probe a candidate business website URL via stealth.py,
classify reachability into 5 accurate states (LIVE, WAF_PROTECTED, PARKED,
BROKEN, NO_WEBSITE), strip tracking query parameters, and perform a zero-extra-request
Digital Health Audit on the fetched HTML body.

Returns a strict `SiteAudit` model including `html_body` (excluded from serialization)
so extractor.py can reuse the homepage DOM without double-fetching.
"""

import re
import time
import urllib.parse
from typing import Optional

from bs4 import BeautifulSoup

from engine.config import PARKED_DOMAIN_SIGNATURES, REQUEST_TIMEOUT, TRACKING_QUERY_PARAMS
from engine.logger import setup_logger
from engine.models import SiteAudit
from engine import stealth

log = setup_logger("validator")

# Bot-wall / WAF challenge signatures returned even on HTTP 200 or 403/503
_WAF_HTML_SIGNATURES = (
    "challenge-running",
    "cf-browser-verification",
    "just a moment...",
    "attention required! | cloudflare",
    "checking your browser before accessing",
    "ddos-guard",
    "sucuri website firewall",
    "access denied | cloudflare",
)

_WAF_SERVER_HEADERS = ("cloudflare", "sucuri", "akamai", "imperva", "incapsula", "ddos-guard")


def canonicalize_url(url: Optional[str]) -> Optional[str]:
    """
    Strip UTM/GMB tracking parameters and fragments, returning a clean canonical URL.
    """
    if not url or not str(url).strip():
        return None
    raw = str(url).strip()
    if not raw.startswith(("http://", "https://")):
        raw = "https://" + raw
    try:
        parsed = urllib.parse.urlsplit(raw)
        if not parsed.netloc:
            return None
        kept_params = [
            (k, v)
            for k, v in urllib.parse.parse_qsl(parsed.query, keep_blank_values=False)
            if k.lower() not in TRACKING_QUERY_PARAMS and not k.lower().startswith("utm_")
        ]
        clean_query = urllib.parse.urlencode(kept_params)
        clean_path = parsed.path or "/"
        return urllib.parse.urlunsplit(
            (parsed.scheme.lower(), parsed.netloc.lower(), clean_path, clean_query, "")
        ).rstrip("?")
    except Exception:
        return raw


def extract_domain(url: Optional[str]) -> str:
    """
    Extract and normalize the root domain from a URL (strips scheme, www., m., ports).
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


def _is_waf_challenge(html_lower: str, status_code: int, headers: dict) -> bool:
    """Detect Cloudflare / WAF / bot-protection challenges."""
    if status_code in (401, 403, 406, 429):
        return True
    server_hdr = str(headers.get("server", "") or headers.get("Server", "")).lower()
    if status_code == 503 and any(waf in server_hdr for waf in _WAF_SERVER_HEADERS):
        return True
    if any(sig in html_lower for sig in _WAF_HTML_SIGNATURES):
        return True
    return False


def _is_parked_page(html_lower: str, title_lower: str, final_url_lower: str) -> bool:
    """Detect domain-parking, expired-domain, or suspended-host placeholder pages."""
    combined = f"{title_lower} {final_url_lower} {html_lower[:12000]}"
    for sig in PARKED_DOMAIN_SIGNATURES:
        if sig in combined:
            return True
    return False


def _detect_cms(html_lower: str, soup: BeautifulSoup) -> Optional[str]:
    """Identify common SMB website builders / CMS platforms from HTML."""
    gen_meta = soup.find("meta", attrs={"name": re.compile(r"^generator$", re.I)})
    gen_content = str(gen_meta.get("content", "")).lower() if gen_meta else ""
    combined = f"{gen_content} {html_lower[:40000]}"

    if "wordpress" in combined or "wp-content/" in combined or "wp-includes/" in combined:
        return "WordPress"
    if "wix.com" in combined or "wixstatic.com" in combined or "_wix_browser_sess" in combined:
        return "Wix"
    if "squarespace.com" in combined or "static1.squarespace.com" in combined:
        return "Squarespace"
    if "webflow.com" in combined or "data-wf-site" in combined:
        return "Webflow"
    if "godaddysites.com" in combined or "wsimg.com" in combined or "secureserver.net" in combined:
        return "GoDaddy"
    if "cdn.shopify.com" in combined or "shopify.theme" in combined:
        return "Shopify"
    if "weebly.com" in combined or "editmysite.com" in combined:
        return "Weebly"
    if "multiscreensite.com" in combined or "irp.cdn-website.com" in combined:
        return "Duda"

    return "Custom" if len(html_lower) > 500 else "Unknown"


def audit_html(
    html: str,
    resolved_url: str,
    http_status: str,
    load_time_ms: Optional[int] = None,
) -> SiteAudit:
    """
    Perform a zero-extra-request Digital Health Audit on already-fetched HTML.
    Detects parked domains, WAF pages, SSL, mobile viewport, CMS, analytics, and Meta Pixel.
    """
    clean_resolved = canonicalize_url(resolved_url) or resolved_url
    root_domain = extract_domain(clean_resolved) or None
    has_ssl = clean_resolved.lower().startswith("https://")
    html_lower = (html or "").lower()

    soup = BeautifulSoup(html or "", "html.parser")
    title_tag = soup.find("title")
    title_lower = title_tag.get_text(" ", strip=True).lower() if title_tag else ""

    # Check parked/expired domains before marking LIVE
    if _is_parked_page(html_lower, title_lower, clean_resolved.lower()):
        log.info(f"Website PARKED/EXPIRED ({http_status}) -> {clean_resolved}")
        return SiteAudit(
            website_found=False,
            website_status="PARKED",
            website_url=clean_resolved,
            root_domain=root_domain,
            http_status=f"{http_status}_PARKED",
            has_ssl=has_ssl,
            load_time_ms=load_time_ms,
        )

    # Mobile viewport check
    viewport_meta = soup.find("meta", attrs={"name": re.compile(r"^viewport$", re.I)})
    is_mobile_friendly = bool(
        viewport_meta and "width" in str(viewport_meta.get("content", "")).lower()
    )

    # CMS detection
    cms_platform = _detect_cms(html_lower, soup)

    # Analytics & Meta Pixel detection
    has_analytics = any(
        sig in html_lower
        for sig in (
            "googletagmanager.com",
            "google-analytics.com",
            "gtag(",
            "plausible.io",
            "clarity.ms",
            "matomo.",
        )
    ) or bool(re.search(r"['\"]g-[a-z0-9]{6,}['\"]", html_lower))

    has_meta_pixel = any(
        sig in html_lower
        for sig in (
            "connect.facebook.net/en_us/fbevents.js",
            "fbevents.js",
            "fbq('init'",
            'fbq("init"',
        )
    )

    return SiteAudit(
        website_found=True,
        website_status="LIVE",
        website_url=clean_resolved,
        root_domain=root_domain,
        http_status=http_status,
        has_ssl=has_ssl,
        is_mobile_friendly=is_mobile_friendly,
        cms_platform=cms_platform,
        has_analytics=has_analytics,
        has_meta_pixel=has_meta_pixel,
        load_time_ms=load_time_ms,
        html_body=html,
    )


def validate_url(website_url: Optional[str]) -> SiteAudit:
    """
    Probe a business website URL via stealth.py and return a strict SiteAudit contract.
    """
    clean_url = canonicalize_url(website_url)
    if not clean_url:
        return SiteAudit(
            website_found=False,
            website_status="NO_WEBSITE",
            website_url=None,
            root_domain=None,
            http_status="NO_URL",
        )

    root_domain = extract_domain(clean_url) or None
    t0 = time.perf_counter()

    try:
        response = stealth.get(
            clean_url,
            timeout=REQUEST_TIMEOUT,
            allow_redirects=True,
            allow_http_fallback=True,
        )
        load_time_ms = int((time.perf_counter() - t0) * 1000)
        status_code = int(response.status_code)
        status_str = str(status_code)
        resolved_raw = getattr(response, "url", clean_url) or clean_url
        resolved_url = canonicalize_url(str(resolved_raw)) or clean_url
        resolved_domain = extract_domain(resolved_url) or root_domain
        headers = dict(getattr(response, "headers", {}) or {})
        html_text = getattr(response, "text", "") or ""
        html_lower = html_text.lower()

        # 1. WAF / Cloudflare / Bot-Protection Wall -> LIVE site behind firewall (NOT dead!)
        if _is_waf_challenge(html_lower, status_code, headers):
            log.info(
                f"Website WAF_PROTECTED ({status_str}) -> {resolved_url} ({load_time_ms}ms)"
            )
            return SiteAudit(
                website_found=True,
                website_status="WAF_PROTECTED",
                website_url=resolved_url,
                root_domain=resolved_domain,
                http_status=status_str,
                has_ssl=resolved_url.lower().startswith("https://"),
                load_time_ms=load_time_ms,
            )

        # 2. Healthy HTTP 2xx-3xx -> Run full zero-extra-request Digital Health Audit
        if 200 <= status_code < 400:
            audit = audit_html(
                html=html_text,
                resolved_url=resolved_url,
                http_status=status_str,
                load_time_ms=load_time_ms,
            )
            log.info(
                f"Website {audit.website_status} ({audit.http_status}) -> {audit.website_url} "
                f"[SSL={audit.has_ssl}, Mobile={audit.is_mobile_friendly}, "
                f"CMS={audit.cms_platform}, {load_time_ms}ms]"
            )
            return audit

        # 3. 404 / 410 / 5xx -> Broken site
        log.info(f"Website BROKEN ({status_str}) -> {resolved_url}")
        return SiteAudit(
            website_found=False,
            website_status="BROKEN",
            website_url=resolved_url,
            root_domain=resolved_domain,
            http_status=status_str,
            has_ssl=resolved_url.lower().startswith("https://"),
            load_time_ms=load_time_ms,
        )

    except Exception as exc:
        load_time_ms = int((time.perf_counter() - t0) * 1000)
        exc_str = str(exc).lower()
        exc_type = type(exc).__name__.lower()

        if "timeout" in exc_str or "timeout" in exc_type or "timed out" in exc_str:
            log.warning(f"Website TIMEOUT -> {clean_url}")
            return SiteAudit(
                website_found=False,
                website_status="BROKEN",
                website_url=clean_url,
                root_domain=root_domain,
                http_status="TIMEOUT",
                load_time_ms=load_time_ms,
            )

        log.warning(f"Website CONNECTION ERROR -> {clean_url} ({exc})")
        return SiteAudit(
            website_found=False,
            website_status="BROKEN",
            website_url=clean_url,
            root_domain=root_domain,
            http_status="CONN_ERROR",
            load_time_ms=load_time_ms,
        )
