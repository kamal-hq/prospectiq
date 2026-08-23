"""
stealth.py — Stealth HTTP Request & TLS Fingerprinting Shield.

All outgoing HTTP requests in this system must route through this module.
Do not use requests or curl_cffi directly in any other module.
"""

import logging
import random
import socket
import sys
import time
from typing import Any, Optional, Tuple, Union
import urllib.parse

try:
    from curl_cffi import requests
    from curl_cffi.requests import Response, Session
except ImportError:
    # Allows module to load even if curl_cffi is pending environment installation
    requests = None  # type: ignore
    Response = Any   # type: ignore
    Session = Any    # type: ignore

try:
    import pycurl
except ImportError:
    pycurl = None

try:
    import dns.resolver
except ImportError:
    dns = None  # type: ignore

try:
    from config import REQUEST_TIMEOUT, USER_AGENTS
except (ImportError, AttributeError):
    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/605.1.15 "
        "(KHTML, like Gecko) Version/17.5 Safari/605.1.15",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:127.0) "
        "Gecko/20100101 Firefox/127.0",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0",
    ]
    REQUEST_TIMEOUT = 30

try:
    from logger import setup_logger
    logger = setup_logger("stealth")
except Exception:
    logger = logging.getLogger("stealth")


def human_delay(mode: str = "request", min_bound: float = 1.0, max_bound: float = 12.0) -> float:
    """
    Draw a randomized delay from a non-uniform behavioral curve and sleep.

    Simulates realistic human browsing cadence using a right-skewed log-normal
    distribution (bursts of quick navigation mixed with natural reading pauses).
    No fixed intervals are used.

    Args:
        mode: Operational mode ("request" for inter-request delay, "batch" for longer pause).
        min_bound: Hard lower bound in seconds.
        max_bound: Hard upper bound in seconds.

    Returns:
        float: The actual sleep duration applied in seconds.
    """
    if mode == "batch":
        # Log-normal distribution centered around ~15-30s with long tail
        delay = random.lognormvariate(mu=2.8, sigma=0.4)
        delay = max(8.0, min(delay, 45.0))
    else:
        # Log-normal distribution centered around ~1.8s (median e^0.6 ~ 1.82s)
        delay = random.lognormvariate(mu=0.6, sigma=0.45)
        delay = max(min_bound, min(delay, max_bound))

    logger.debug(f"Applying behavioral stealth delay: {delay:.2f}s (mode={mode})")
    time.sleep(delay)
    return delay


def get_session(impersonate: str = "chrome124") -> Session:
    """
    Create and return a persistent curl_cffi Session configured with Chrome TLS
    fingerprinting, trust_env enabled for system DNS resolution,
    a single persistent User-Agent, and realistic browser headers.

    The User-Agent is selected randomly upon session creation and remains constant
    for the lifetime of the returned session to prevent bot detection triggers.

    Args:
        impersonate: Browser profile for TLS fingerprinting (default: "chrome124").

    Returns:
        curl_cffi.requests.Session: Configured persistent HTTP session.
    """
    if requests is None:
        raise RuntimeError(
            "curl_cffi is required by stealth.py but is not installed. "
            "Please install it via 'pip install curl_cffi'."
        )

    session = requests.Session(impersonate=impersonate, trust_env=True)

    if pycurl is not None and hasattr(pycurl, "DNS_SERVERS"):
        try:
            session.curl_options = {pycurl.DNS_SERVERS: "1.1.1.1,8.8.8.8"}
        except Exception as exc:
            logger.debug(f"Failed to set pycurl DNS_SERVERS: {exc}")

    selected_user_agent = random.choice(USER_AGENTS)

    session.headers.update({
        "User-Agent": selected_user_agent,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "Accept-Language": "en-US,en;q=0.9",
        "Sec-Ch-Ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"Windows"',
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-User": "?1",
        "Sec-Fetch-Dest": "document",
        "Upgrade-Insecure-Requests": "1",
    })

    logger.debug(f"Created persistent stealth session with User-Agent: {selected_user_agent}")
    return session


def _pre_resolve_host(url: str) -> None:
    """
    Attempt to pre-resolve the hostname using Python's socket.getaddrinfo()
    with a fallback to Cloudflare/Google DNS via dnspython if available.
    Logs a warning if dnspython is unavailable or resolution fails, but never raises.
    """
    try:
        parsed = urllib.parse.urlparse(url if "://" in url else f"https://{url}")
        hostname = parsed.netloc or parsed.path
        hostname = hostname.split(":")[0].strip()
        if not hostname:
            return

        try:
            socket.getaddrinfo(hostname, None)
            return
        except Exception:
            pass

        # Fallback to dnspython if installed
        if dns is not None and hasattr(dns, "resolver"):
            try:
                resolver = dns.resolver.Resolver()
                resolver.nameservers = ["1.1.1.1", "8.8.8.8"]
                resolver.timeout = 5.0
                resolver.lifetime = 5.0
                resolver.resolve(hostname, "A")
            except Exception as exc:
                logger.warning(f"DNS pre-resolution via dnspython failed for {hostname}: {exc}")
        else:
            logger.warning(f"Host '{hostname}' not resolved by system DNS and dnspython is not available.")
    except Exception as exc:
        logger.debug(f"Host pre-resolution error for {url}: {exc}")


def _is_dns_resolution_error(exc: Exception) -> bool:
    """
    Check whether an exception corresponds to a curl (6) host resolution error.
    """
    msg = str(exc).lower()
    return "could not resolve host" in msg or "curl: (6)" in msg or "resolve host" in msg


def _execute_get(
    target_session: Session,
    target_url: str,
    effective_timeout: Union[int, float, Tuple[Union[int, float], Union[int, float]]],
    impersonate: Optional[str] = None,
    **kwargs: Any,
) -> Response:
    """
    Execute GET request on session with DNS resolution fallback to http://.
    """
    try:
        if impersonate:
            return target_session.get(target_url, timeout=effective_timeout, impersonate=impersonate, **kwargs)
        return target_session.get(target_url, timeout=effective_timeout, **kwargs)
    except Exception as exc:
        if _is_dns_resolution_error(exc) and target_url.startswith("https://"):
            fallback_url = "http://" + target_url[8:]
            logger.warning(
                f"DNS resolution failure for {target_url}. Retrying once with plain HTTP: {fallback_url}"
            )
            if impersonate:
                return target_session.get(fallback_url, timeout=effective_timeout, impersonate=impersonate, **kwargs)
            return target_session.get(fallback_url, timeout=effective_timeout, **kwargs)
        raise


def get(
    url: str,
    session: Optional[Session] = None,
    timeout: Optional[Union[int, float, Tuple[Union[int, float], Union[int, float]]]] = None,
    impersonate: str = "chrome124",
    apply_delay: bool = True,
    **kwargs: Any,
) -> Response:
    """
    Execute a stealth HTTP GET request with Chrome TLS fingerprinting, DNS pre-resolution,
    and behavioral timing.

    All outgoing HTTP GET requests in the system (e.g. from validator.py and extractor.py)
    must route through this function.

    Args:
        url: Target HTTP/HTTPS URL.
        session: Optional persistent curl_cffi Session. If None, a temporary session
                 is automatically created and disposed for the request.
        timeout: Request timeout in seconds or (connect_timeout, read_timeout) tuple.
                 Defaults to (10, config.REQUEST_TIMEOUT).
        impersonate: Browser profile for TLS handshake mimicry (default: "chrome124").
        apply_delay: Whether to enforce human behavioral timing before the request.
        **kwargs: Additional keyword arguments forwarded to session.get().

    Returns:
        curl_cffi.requests.Response: Response received from the target server.
    """
    if requests is None:
        raise RuntimeError(
            "curl_cffi is required by stealth.py but is not installed. "
            "Please install it via 'pip install curl_cffi'."
        )

    if apply_delay:
        human_delay(mode="request")

    # Attempt host pre-resolution with Cloudflare/Google DNS fallback
    _pre_resolve_host(url)

    if isinstance(timeout, tuple):
        effective_timeout = timeout
    elif timeout is not None:
        effective_timeout = (10, timeout)
    else:
        effective_timeout = (10, REQUEST_TIMEOUT)

    if session is not None:
        logger.debug(f"Executing stealth GET via persistent session to {url}")
        return _execute_get(session, url, effective_timeout, impersonate=impersonate, **kwargs)

    logger.debug(f"Executing stealth GET via one-off session to {url}")
    temp_session = get_session(impersonate=impersonate)
    try:
        return _execute_get(temp_session, url, effective_timeout, **kwargs)
    finally:
        temp_session.close()
