"""
logger.py -- Custom logging utility for the ProspectIQ Lead Generation Engine.

Provides dual-output logging (colored console + persistent file), safe cross-platform
encoding handling, and mandatory automatic secret redaction for URLs and headers.
"""

import logging
import os
import re
import sys
import urllib.parse
from typing import Iterable, Optional

from colorama import Fore, Style, init as colorama_init

from engine.config import LOG_DIR, LOG_FILE, SECRET_QUERY_PARAMS

# Initialize colorama for cross-platform colored terminal output
colorama_init(autoreset=True, strip=False, convert=True)

# Regex matching sensitive query string params (e.g. ?api_key=abc&...)
_SECRET_QS_REGEX = re.compile(
    r"([?&](?:" + "|".join(re.escape(p) for p in sorted(SECRET_QUERY_PARAMS)) + r")=)([^&\s\"']+)",
    flags=re.IGNORECASE,
)

# Regex matching sensitive header / bearer token patterns in log text
_SECRET_HEADER_REGEX = re.compile(
    r"((?:Bearer|X-Subscription-Token|Authorization)\s*[:=]?\s*)([A-Za-z0-9._\-]{8,})",
    flags=re.IGNORECASE,
)


def redact_secrets(text: str) -> str:
    """
    Redact API keys, tokens, and authorization secrets from arbitrary log strings.
    """
    if not text:
        return text
    cleaned = _SECRET_QS_REGEX.sub(r"\1[REDACTED]", text)
    cleaned = _SECRET_HEADER_REGEX.sub(r"\1[REDACTED]", cleaned)
    return cleaned


def redact_url(url: str) -> str:
    """
    Safely mask any sensitive query parameters in a URL before logging.
    """
    if not url:
        return url
    try:
        parsed = urllib.parse.urlsplit(url)
        if not parsed.query:
            return url
        pairs = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
        redacted_pairs = [
            (k, "[REDACTED]" if k.lower() in SECRET_QUERY_PARAMS else v)
            for k, v in pairs
        ]
        new_query = urllib.parse.urlencode(redacted_pairs, safe="[]")
        return urllib.parse.urlunsplit(
            (parsed.scheme, parsed.netloc, parsed.path, new_query, parsed.fragment)
        )
    except Exception:
        return redact_secrets(url)


class SecretRedactingFilter(logging.Filter):
    """
    Logging filter that scrubs sensitive query parameters and tokens from every
    log record before it reaches stdout or logs/app.log.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            rendered = record.getMessage()
            redacted = redact_secrets(rendered)
            if redacted != rendered:
                record.msg = redacted
                record.args = ()
        except Exception:
            pass
        return True


class ColoredConsoleHandler(logging.StreamHandler):
    """
    Custom StreamHandler that applies ANSI color codes to log output based on level
    while handling Windows terminal encoding gracefully.
    """

    LEVEL_COLORS = {
        logging.DEBUG: Fore.CYAN,
        logging.INFO: Fore.GREEN,
        logging.WARNING: Fore.YELLOW,
        logging.ERROR: Fore.RED,
        logging.CRITICAL: Fore.MAGENTA + Style.BRIGHT,
    }

    def emit(self, record: logging.LogRecord) -> None:
        try:
            color = self.LEVEL_COLORS.get(record.levelno, Fore.WHITE)
            original_levelname = record.levelname

            record.levelname = f"{color}{record.levelname}{Style.RESET_ALL}"
            msg = self.format(record)

            encoding = sys.stdout.encoding or "utf-8"
            safe_msg = msg.encode(encoding, errors="replace").decode(encoding, errors="replace")

            self.stream.write(safe_msg + self.terminator)
            self.flush()

            record.levelname = original_levelname
        except Exception:
            self.handleError(record)


def setup_logger(name: str = "lead_engine") -> logging.Logger:
    """
    Configure and return a dual-destination logger with secret redaction,
    persistent DEBUG file output (logs/app.log), and colored INFO stdout.
    """
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)
    redactor = SecretRedactingFilter()

    file_formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(module)-12s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
        file_handler = logging.FileHandler(LOG_FILE, mode="a", encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(file_formatter)
        file_handler.addFilter(redactor)
        logger.addHandler(file_handler)
    except OSError:
        # Gracefully fall back to console-only logging in read-only environments
        pass

    console_formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(message)s",
        datefmt="%H:%M:%S",
    )
    console_handler = ColoredConsoleHandler(stream=sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(console_formatter)
    console_handler.addFilter(redactor)

    logger.addHandler(console_handler)

    return logger


def log_milestone(logger: logging.Logger, message: str) -> None:
    border = "=" * 60
    logger.info(border)
    logger.info(f"  *  {message}")
    logger.info(border)


def log_skip(logger: logging.Logger, business_name: str, city: str) -> None:
    logger.info(f"SKIP (duplicate) -> {business_name} in {city}")


def log_validation_result(
    logger: logging.Logger,
    business_name: str,
    has_website: bool,
    social_handles: Iterable[str],
    status_code: int | str,
) -> None:
    socials = ", ".join(social_handles) if social_handles else "None"
    logger.info(
        f"VALIDATED -> {business_name} | "
        f"Website: {'YES' if has_website else 'NO'} | "
        f"Socials: {socials} | "
        f"Status: {status_code}"
    )
