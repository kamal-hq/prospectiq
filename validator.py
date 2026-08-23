"""
Validator Layer — validator.py

Single responsibility: Direct HTTP probing of candidate business website URLs.
Routes all HTTP probing requests through stealth.py.
Does NOT perform business discovery, API querying, or contact extraction.
"""

import re
from typing import Any, Dict, Optional
from urllib.parse import urlparse

from config import REQUEST_TIMEOUT
from logger import setup_logger
import stealth

log = setup_logger("validator")


def extract_domain(url: Optional[str]) -> str:
    """
    Extract and normalize the root domain from a given URL string.
    Strips schemes, paths, port numbers, query strings, and leading 'www.' prefixes.

    Args:
        url: Full or partial URL string.

    Returns:
        str: Clean domain string in lowercase (e.g., 'example.com'), or empty string on failure.
    """
    if not url:
        return ""
    try:
        parsed = urlparse(url if "://" in url else f"https://{url}")
        domain = parsed.netloc or parsed.path
        domain = re.sub(r"^www\.", "", domain)
        return domain.lower().strip()
    except Exception:
        return ""


def validate_url(website_url: Optional[str]) -> Dict[str, Any]:
    """
    Probe a business website URL to determine if it is actively responding and live.

    Args:
        website_url: Target URL string to probe.

    Returns:
        dict:
            - website_found (bool): True if HTTP response status is between 200 and 399.
            - website_url (str): Destination URL after redirect resolution.
            - http_status (str): "200", "404", "TIMEOUT", "CONN_ERROR", or "NO_URL".
    """
    if not website_url or not website_url.strip():
        return {
            "website_found": False,
            "website_url": "",
            "http_status": "NO_URL",
        }

    clean_url = website_url.strip()
    if not clean_url.startswith(("http://", "https://")):
        clean_url = "https://" + clean_url

    try:
        # Route probe GET request strictly through stealth layer with redirect resolution
        response = stealth.get(
            clean_url,
            timeout=REQUEST_TIMEOUT,
            allow_redirects=True,
        )

        status_code = response.status_code
        status_str = str(status_code)
        resolved_url = getattr(response, "url", clean_url) or clean_url

        if 200 <= status_code < 400:
            log.info(f"Website LIVE ({status_str}) -> {clean_url} (Resolved: {resolved_url})")
            return {
                "website_found": True,
                "website_url": resolved_url,
                "http_status": status_str,
            }
        else:
            log.info(f"Website DEAD ({status_str}) -> {clean_url}")
            return {
                "website_found": False,
                "website_url": clean_url,
                "http_status": status_str,
            }

    except Exception as exc:
        exc_str = str(exc).lower()
        exc_type = type(exc).__name__.lower()

        if "timeout" in exc_str or "timeout" in exc_type or "timed out" in exc_str:
            log.warning(f"Website TIMEOUT -> {clean_url}")
            return {
                "website_found": False,
                "website_url": clean_url,
                "http_status": "TIMEOUT",
            }

        # Connection, DNS, network, SSL errors
        log.warning(f"Website CONNECTION ERROR -> {clean_url} ({exc})")
        return {
            "website_found": False,
            "website_url": clean_url,
            "http_status": "CONN_ERROR",
        }
