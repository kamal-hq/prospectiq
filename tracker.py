"""
tracker.py — API usage and monthly quota tracking module.

Persists call counts for third-party APIs (SerpApi, Brave, Hunter.io) into a JSON file
keyed by month (YYYY-MM). Prevents accidental overages by enforcing hard ceilings
before external network calls are executed.
"""

import json
import os
from datetime import datetime
from typing import Any, Dict

from config import BASE_DIR
from logger import setup_logger

# Initialize logger for tracking operations
log = setup_logger("tracker")

# Path to the JSON persistence file storing monthly usage counters
TRACKER_FILE = os.path.join(BASE_DIR, "usage_tracker.json")

# Map of accepted api_name aliases to canonical keys in usage_tracker.json
API_KEY_MAP = {
    "serpapi": "serpapi_calls",
    "serpapi_calls": "serpapi_calls",
    "brave": "brave_calls",
    "brave_calls": "brave_calls",
    "hunter": "hunter_calls",
    "hunter_calls": "hunter_calls",
    "apollo": "hunter_calls",
}

DEFAULT_MONTHLY_COUNTERS: Dict[str, int] = {
    "serpapi_calls": 0,
    "brave_calls": 0,
    "hunter_calls": 0,
}


class QuotaExhaustedError(Exception):
    """Raised when an API's configured monthly request ceiling has been reached."""

    def __init__(self, api_name: str, max_limit: int, month: str, current_count: int = 0):
        self.api_name = api_name
        self.max_limit = max_limit
        self.month = month
        self.current_count = current_count
        super().__init__(
            f"Monthly quota exhausted for API '{api_name}' (limit: {max_limit}, used: {current_count}) for month {month}."
        )


def _get_current_month() -> str:
    """
    Retrieve the current year and month as a string key.

    Returns:
        String formatted as 'YYYY-MM' (e.g., '2026-08').
    """
    return datetime.now().strftime("%Y-%m")


def _load_tracker() -> dict:
    """
    Load API usage statistics from the persistent JSON file.

    Returns:
        Dictionary mapping month keys ('YYYY-MM') to API call counts
        (e.g., {'2026-08': {'serpapi_calls': 12, 'brave_calls': 45, 'hunter_calls': 0}}),
        or empty dict on failure/missing file.
    """
    if not os.path.exists(TRACKER_FILE):
        return {}
    try:
        with open(TRACKER_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:
        log.error(f"Failed to load tracker file: {exc}")
        return {}


def _save_tracker(data: dict) -> None:
    """
    Write updated API usage statistics back to the JSON file.

    Args:
        data: Dictionary of monthly API counts to serialize.
    """
    try:
        with open(TRACKER_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
    except Exception as exc:
        log.error(f"Failed to save tracker file: {exc}")


def _normalize_month_record(record: dict) -> dict:
    """
    Ensure all tracked API keys exist in the monthly record, supporting migration from legacy keys.

    Args:
        record: Dictionary representing a single month's usage stats.

    Returns:
        Standardized dictionary containing all canonical keys initialized.
    """
    normalized = dict(DEFAULT_MONTHLY_COUNTERS)
    # Migrate legacy format keys if present
    if "serpapi" in record:
        normalized["serpapi_calls"] = record["serpapi"]
    if "brave" in record:
        normalized["brave_calls"] = record["brave"]
    if "hunter" in record:
        normalized["hunter_calls"] = record["hunter"]

    # Copy current canonical keys
    for k in DEFAULT_MONTHLY_COUNTERS:
        if k in record:
            normalized[k] = record[k]
    return normalized


def check_and_increment(api_name: str, max_limit: int) -> int:
    """
    Verify whether an API quota is available, and increment the counter if under limit.

    Performs a pre-flight check against the monthly hard limit before an API request
    is initiated. If the current count is at or above max_limit, raises QuotaExhaustedError
    to prevent billable overage or rate violations.
    Monthly counters auto-reset when the calendar month changes.

    Args:
        api_name:  Identifier of the API being checked ('serpapi', 'brave', or 'hunter').
        max_limit: Maximum allowed requests for the current calendar month.

    Returns:
        int: The newly updated request count for the API in the current month.

    Raises:
        QuotaExhaustedError: If current_count >= max_limit prior to incrementing.
        ValueError: If api_name is not recognized.
    """
    canonical_key = API_KEY_MAP.get(api_name.lower().strip())
    if not canonical_key:
        raise ValueError(
            f"Unknown API '{api_name}'. Expected one of: 'serpapi', 'brave', 'hunter'."
        )

    data = _load_tracker()
    month = _get_current_month()

    # Initialize / normalize monthly tracking record (auto-reset on new calendar month)
    if month not in data:
        data[month] = dict(DEFAULT_MONTHLY_COUNTERS)
    else:
        data[month] = _normalize_month_record(data[month])

    # Retrieve current count for specified API
    current_count = data[month].get(canonical_key, 0)

    # Enforce strict quota ceiling
    if current_count >= max_limit:
        raise QuotaExhaustedError(
            api_name=api_name,
            max_limit=max_limit,
            month=month,
            current_count=current_count,
        )

    # Increment and persist new count
    new_count = current_count + 1
    data[month][canonical_key] = new_count
    _save_tracker(data)

    log.debug(f"API quota counter incremented: {api_name} -> {new_count}/{max_limit} for {month}")
    return new_count
