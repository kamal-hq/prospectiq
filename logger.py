"""
logger.py -- Custom logging utility for the Lead Generation Engine.

Provides dual-output logging (console + file) with colored console output,
timestamped entries, safe encoding handling for cross-platform terminals,
and structured milestone/error tracking.
"""

import logging
import os
import sys
from datetime import datetime

from colorama import Fore, Style, init as colorama_init

from config import LOG_DIR, LOG_FILE

# Initialize colorama for cross-platform colored terminal output
colorama_init(autoreset=True, strip=False, convert=True)


class ColoredConsoleHandler(logging.StreamHandler):
    """
    Custom StreamHandler that applies ANSI color codes to log output based on level.

    Provides colored output in the terminal while preserving raw formatting
    and handling terminal character encoding gracefully across OS environments.
    """

    LEVEL_COLORS = {
        logging.DEBUG: Fore.CYAN,
        logging.INFO: Fore.GREEN,
        logging.WARNING: Fore.YELLOW,
        logging.ERROR: Fore.RED,
        logging.CRITICAL: Fore.MAGENTA + Style.BRIGHT,
    }

    def emit(self, record: logging.LogRecord) -> None:
        """
        Format and write the log record to the console stream with color coding.

        Args:
            record: The logging.LogRecord instance to be processed and displayed.
        """
        try:
            # Look up color corresponding to log level; fallback to white
            color = self.LEVEL_COLORS.get(record.levelno, Fore.WHITE)
            original_levelname = record.levelname
            
            # Wrap level name with color formatting and style reset
            record.levelname = f"{color}{record.levelname}{Style.RESET_ALL}"
            msg = self.format(record)
            
            # Encode with errors='replace' to safely handle characters not supported by the terminal encoding
            encoding = sys.stdout.encoding or "utf-8"
            safe_msg = msg.encode(encoding, errors="replace").decode(encoding, errors="replace")
            
            # Write out to console stream
            self.stream.write(safe_msg + self.terminator)
            self.flush()
            
            # Restore original levelname to prevent side effects in other handlers
            record.levelname = original_levelname
        except Exception:
            self.handleError(record)


def setup_logger(name: str = "lead_engine") -> logging.Logger:
    """
    Configure and return a dual-destination logger with file and colored console handlers.

    The logger writes detailed DEBUG-level records to a persistent file (app.log)
    and clean INFO-level colored notifications to stdout.

    Args:
        name: Unique string identifier for the logger instance.

    Returns:
        logging.Logger: Fully configured Logger instance with attached handlers.
    """
    # Ensure log destination directory exists
    os.makedirs(LOG_DIR, exist_ok=True)

    logger = logging.getLogger(name)

    # Prevent duplicate handler registration if setup_logger is called repeatedly
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)

    # ── File Handler (Full Detail, DEBUG level) ──────────────────────
    file_formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(module)-12s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler = logging.FileHandler(LOG_FILE, mode="a", encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(file_formatter)

    # ── Console Handler (Clean UI, INFO level) ───────────────────────
    console_formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(message)s",
        datefmt="%H:%M:%S",
    )
    console_handler = ColoredConsoleHandler(stream=sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(console_formatter)

    # Attach both handlers
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger


# ──────────────────────────────────────────────
# Convenience milestone & status loggers
# ──────────────────────────────────────────────

def log_milestone(logger: logging.Logger, message: str) -> None:
    """
    Log a high-visibility milestone banner event to mark pipeline stages.

    Args:
        logger:  Active Logger instance.
        message: Descriptive milestone text to display inside the border.
    """
    border = "=" * 60
    logger.info(border)
    logger.info(f"  *  {message}")
    logger.info(border)


def log_skip(logger: logging.Logger, business_name: str, city: str) -> None:
    """
    Log a duplicate skip event when a business is already indexed.

    Args:
        logger:        Active Logger instance.
        business_name: Name of the skipped business.
        city:          Location/city of the skipped business.
    """
    logger.info(f"SKIP (duplicate) -> {business_name} in {city}")


def log_validation_result(
    logger: logging.Logger,
    business_name: str,
    has_website: bool,
    social_handles: list,
    status_code: int | str,
) -> None:
    """
    Log the structured validation outcome for a single business entity.

    Args:
        logger:         Active Logger instance.
        business_name:  Name of the validated business.
        has_website:    Boolean indicating whether a live website was verified.
        social_handles: List of platform names where footprints were discovered.
        status_code:    HTTP status code or textual error descriptor.
    """
    socials = ", ".join(social_handles) if social_handles else "None"
    logger.info(
        f"VALIDATED -> {business_name} | "
        f"Website: {'YES' if has_website else 'NO'} | "
        f"Socials: {socials} | "
        f"Status: {status_code}"
    )
