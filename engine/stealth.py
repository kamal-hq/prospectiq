"""
stealth.py — Sole Outgoing HTTP Gateway & TLS Fingerprinting Shield.

All outgoing HTTP requests across discovery.py, validator.py, and extractor.py
MUST route through this module. Never import `requests` or `curl_cffi` directly
outside stealth.py.

v3.0 Upgrades:
- Mandatory secret redaction in every log message (zero API keys in app.log).
- Fixed libcurl DNS resolution: passes dnspython-resolved IPv4 addresses directly
  into libcurl via CurlOpt.RESOLVE on curl (6) host resolution errors, plus
  www./bare-domain DNS fallback.
- Coherent Sec-Ch-Ua-Platform headers matching the chosen User-Agent OS.
"""

import logging
import random
import socket
import time
import urllib.parse
from typing import Any, Dict, List, Optional, Tuple, Union

try:
    from curl_cffi import requests
    from curl_cffi.requests import Response, Session
except ImportError:
    requests = None  # type: ignore
    Response = Any  # type: ignore
    Session = Any  # type: ignore

try:
    from curl_cffi.const import CurlOpt
except ImportError:
    try:
        from curl_cffi import CurlOpt  # type: ignore
    except ImportError:
        CurlOpt = None  # type: ignore

try:
    import dns.resolver
except ImportError:
    dns = None  # type: ignore

try:
    from engine.config import REQUEST_TIMEOUT, USER_AGENTS
except (ImportError, AttributeError):
    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    ]
    REQUEST_TIMEOUT = 25

try:
    from engine.logger import redact_url, setup_logger
    logger = setup_logger("stealth")
except Exception:
    logger = logging.getLogger("stealth")

    def redact_url(url: str) -> str:  # type: ignore
        return url


# In-memory DNS cache to avoid redundant lookups within a run
_DNS_IP_CACHE: Dict[str, Optional[str]] = {}


def human_delay(mode: str = "request", min_bound: float = 1.0, max_bound: float = 12.0) -> float:
    """
    Draw a randomized delay from a right-skewed log-normal behavioral curve and sleep.
    Replaces fixed sleep intervals with irregular human browsing cadence.
    """
    if mode == "batch":
        delay = random.lognormvariate(mu=2.8, sigma=0.4)
        delay = max(8.0, min(delay, 45.0))
    else:
        delay = random.lognormvariate(mu=0.55, sigma=0.45)
        delay = max(min_bound, min(delay, max_bound))

    logger.debug(f"Applying behavioral stealth delay: {delay:.2f}s (mode={mode})")
    time.sleep(delay)
    return delay


def _platform_from_ua(user_agent: str) -> str:
    ua_lower = user_agent.lower()
    if "macintosh" in ua_lower or "mac os x" in ua_lower:
        return '"macOS"'
    if "linux" in ua_lower:
        return '"Linux"'
    return '"Windows"'


def get_session(impersonate: str = "chrome124") -> Session:
    """
    Create and return a persistent curl_cffi Session configured with Chrome TLS
    fingerprinting, a single consistent User-Agent for session cohesion, and
    IPv4-preferred libcurl options to avoid Windows IPv6/DNS stalls.
    """
    if requests is None:
        raise RuntimeError(
            "curl_cffi is required by stealth.py but is not installed. "
            "Please install it via 'pip install curl_cffi'."
        )

    session = requests.Session(impersonate=impersonate, trust_env=True)

    # Prefer IPv4 when CurlOpt is available to avoid broken ISP IPv6 DNS timeouts
    if CurlOpt is not None and hasattr(CurlOpt, "IPRESOLVE"):
        try:
            session.curl_options = {CurlOpt.IPRESOLVE: 1}  # CURL_IPRESOLVE_V4 = 1
        except Exception as exc:
            logger.debug(f"Could not apply CurlOpt.IPRESOLVE: {exc}")

    selected_user_agent = random.choice(USER_AGENTS)
    platform_header = _platform_from_ua(selected_user_agent)

    session.headers.update(
        {
            "User-Agent": selected_user_agent,
            "Accept": (
                "text/html,application/xhtml+xml,application/xml;q=0.9,"
                "image/avif,image/webp,image/apng,*/*;q=0.8"
            ),
            "Accept-Language": "en-US,en;q=0.9",
            "Sec-Ch-Ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": platform_header,
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-User": "?1",
            "Sec-Fetch-Dest": "document",
            "Upgrade-Insecure-Requests": "1",
        }
    )

    logger.debug(f"Created persistent stealth session with User-Agent: {selected_user_agent}")
    return session


def resolve_host_ipv4(hostname: str) -> Optional[str]:
    """
    Resolve a hostname to an IPv4 address using system DNS first, then public DNS
    (Cloudflare 1.1.1.1 / Google 8.8.8.8 / Quad9 9.9.9.9) via dnspython.
    Returns the resolved IPv4 string (cached per run) or None if unresolvable.
    """
    host = hostname.strip().lower()
    if not host:
        return None
    if host in _DNS_IP_CACHE:
        return _DNS_IP_CACHE[host]

    # 1. Try OS resolver (IPv4)
    try:
        infos = socket.getaddrinfo(host, None, family=socket.AF_INET)
        if infos:
            ip = str(infos[0][4][0])
            _DNS_IP_CACHE[host] = ip
            return ip
    except Exception:
        pass

    # 2. Fallback to dnspython querying reliable public resolvers
    if dns is not None and hasattr(dns, "resolver"):
        try:
            resolver = dns.resolver.Resolver(configure=False)
            resolver.nameservers = ["1.1.1.1", "8.8.8.8", "9.9.9.9"]
            resolver.timeout = 4.0
            resolver.lifetime = 6.0
            answers = resolver.resolve(host, "A")
            for rdata in answers:
                ip = str(rdata.address)
                _DNS_IP_CACHE[host] = ip
                return ip
        except Exception as exc:
            logger.debug(f"dnspython A-record lookup failed for {host}: {exc}")

    _DNS_IP_CACHE[host] = None
    return None


def _is_dns_resolution_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    return (
        "could not resolve host" in msg
        or "curl: (6)" in msg
        or "resolve host" in msg
        or "name or service not known" in msg
    )


def _is_ssl_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    return (
        "ssl" in msg
        or "certificate" in msg
        or "curl: (60)" in msg
        or "curl: (51)" in msg
        or "curl: (35)" in msg
    )


def _toggle_www_url(url: str) -> Optional[str]:
    """Return the alternate www./bare-domain URL for DNS fallback retries."""
    try:
        parsed = urllib.parse.urlsplit(url)
        host = parsed.hostname or ""
        if not host:
            return None
        alt_host = host[4:] if host.startswith("www.") else f"www.{host}"
        netloc = f"{alt_host}:{parsed.port}" if parsed.port else alt_host
        return urllib.parse.urlunsplit(
            (parsed.scheme, netloc, parsed.path, parsed.query, parsed.fragment)
        )
    except Exception:
        return None


def _get_with_optional_resolve(
    target_session: Session,
    target_url: str,
    effective_timeout: Union[int, float, Tuple[Union[int, float], Union[int, float]]],
    impersonate: Optional[str] = None,
    resolved_ip: Optional[str] = None,
    **kwargs: Any,
) -> Response:
    """
    Issue the underlying curl_cffi GET, injecting CurlOpt.RESOLVE when an explicit
    IPv4 address was resolved via dnspython so libcurl bypasses broken local DNS.
    """
    call_kwargs = dict(kwargs)
    if resolved_ip and CurlOpt is not None and hasattr(CurlOpt, "RESOLVE"):
        parsed = urllib.parse.urlsplit(target_url)
        host = parsed.hostname
        if host:
            resolve_entries: List[str] = [
                f"{host}:443:{resolved_ip}",
                f"{host}:80:{resolved_ip}",
            ]
            existing_opts = dict(call_kwargs.get("curl_options") or {})
            existing_opts[CurlOpt.RESOLVE] = resolve_entries
            call_kwargs["curl_options"] = existing_opts

    if impersonate:
        return target_session.get(
            target_url,
            timeout=effective_timeout,
            impersonate=impersonate,
            **call_kwargs,
        )
    return target_session.get(target_url, timeout=effective_timeout, **call_kwargs)


def _execute_get(
    target_session: Session,
    target_url: str,
    effective_timeout: Union[int, float, Tuple[Union[int, float], Union[int, float]]],
    impersonate: Optional[str] = None,
    allow_http_fallback: bool = True,
    **kwargs: Any,
) -> Response:
    """
    Execute GET request with robust DNS resolution recovery (dnspython + CurlOpt.RESOLVE
    + www./bare hostname toggle) and optional HTTP fallback on HTTPS SSL failure.
    """
    safe_url = redact_url(target_url)
    try:
        return _get_with_optional_resolve(
            target_session,
            target_url,
            effective_timeout,
            impersonate=impersonate,
            **kwargs,
        )
    except Exception as exc:
        # 1. DNS error recovery: resolve via 1.1.1.1/8.8.8.8 and inject IP directly into libcurl
        if _is_dns_resolution_error(exc):
            parsed = urllib.parse.urlsplit(target_url)
            host = parsed.hostname or ""
            ip = resolve_host_ipv4(host)
            if ip:
                logger.info(
                    f"DNS recovery: retrying {safe_url} with public-DNS IPv4 ({ip})"
                )
                try:
                    return _get_with_optional_resolve(
                        target_session,
                        target_url,
                        effective_timeout,
                        impersonate=impersonate,
                        resolved_ip=ip,
                        **kwargs,
                    )
                except Exception:
                    pass

            # Try toggling www. <-> bare domain (many SMBs misconfigure one DNS record)
            alt_url = _toggle_www_url(target_url)
            if alt_url:
                alt_host = urllib.parse.urlsplit(alt_url).hostname or ""
                alt_ip = resolve_host_ipv4(alt_host)
                if alt_ip:
                    logger.info(
                        f"DNS recovery: retrying alternate host {redact_url(alt_url)} ({alt_ip})"
                    )
                    try:
                        return _get_with_optional_resolve(
                            target_session,
                            alt_url,
                            effective_timeout,
                            impersonate=impersonate,
                            resolved_ip=alt_ip,
                            **kwargs,
                        )
                    except Exception:
                        return _get_with_optional_resolve(
                            target_session,
                            alt_url,
                            effective_timeout,
                            impersonate=impersonate,
                            **kwargs,
                        )
            raise

        # 2. HTTPS SSL failure -> retry plain HTTP if allowed (helps detect No-SSL pitches!)
        if allow_http_fallback and _is_ssl_error(exc) and target_url.startswith("https://"):
            http_url = "http://" + target_url[8:]
            logger.warning(
                f"HTTPS SSL error for {safe_url}. Falling back once to HTTP: {redact_url(http_url)}"
            )
            return _get_with_optional_resolve(
                target_session,
                http_url,
                effective_timeout,
                impersonate=impersonate,
                **kwargs,
            )

        raise


def get(
    url: str,
    session: Optional[Session] = None,
    timeout: Optional[Union[int, float, Tuple[Union[int, float], Union[int, float]]]] = None,
    impersonate: str = "chrome124",
    apply_delay: bool = True,
    allow_http_fallback: bool = True,
    **kwargs: Any,
) -> Response:
    """
    Execute a stealth HTTP GET request with Chrome TLS fingerprinting, secret-safe
    logging, DNS resolution recovery, and behavioral timing.
    """
    if requests is None:
        raise RuntimeError(
            "curl_cffi is required by stealth.py but is not installed. "
            "Please install it via 'pip install curl_cffi'."
        )

    if apply_delay:
        human_delay(mode="request")

    if isinstance(timeout, tuple):
        effective_timeout = timeout
    elif timeout is not None:
        effective_timeout = (10, timeout)
    else:
        effective_timeout = (10, REQUEST_TIMEOUT)

    safe_url = redact_url(url)

    if session is not None:
        logger.debug(f"Executing stealth GET via persistent session to {safe_url}")
        return _execute_get(
            session,
            url,
            effective_timeout,
            impersonate=impersonate,
            allow_http_fallback=allow_http_fallback,
            **kwargs,
        )

    logger.debug(f"Executing stealth GET via one-off session to {safe_url}")
    temp_session = get_session(impersonate=impersonate)
    try:
        return _execute_get(
            temp_session,
            url,
            effective_timeout,
            impersonate=impersonate,
            allow_http_fallback=allow_http_fallback,
            **kwargs,
        )
    finally:
        temp_session.close()
