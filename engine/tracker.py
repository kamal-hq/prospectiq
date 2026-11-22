"""
tracker.py — API usage and monthly quota tracking module.

Dual-mode monthly quota guard for third-party APIs (SerpApi, Brave, Hunter.io):
  - Cloud Mode (Supabase): executes atomic row-locked `prospectiq.check_and_increment_quota`
    RPC against `prospectiq.api_quotas` (zero race conditions across CI runs).
  - Local Fallback Mode: persists monthly counters keyed by YYYY-MM into `usage_tracker.json`.

Prevents accidental overages by enforcing hard ceilings before external network calls.
"""

import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from engine.config import BASE_DIR
from engine import database
from engine.logger import setup_logger

# Initialize logger for tracking operations
log = setup_logger("tracker")

# Path to the JSON persistence file storing local monthly usage counters
TRACKER_FILE = os.path.join(BASE_DIR, "usage_tracker.json")

# Map of accepted api_name aliases to canonical keys in local usage_tracker.json
API_KEY_MAP = {
    "serpapi": "serpapi_calls",
    "serpapi_calls": "serpapi_calls",
    "brave": "brave_calls",
    "brave_calls": "brave_calls",
    "hunter": "hunter_calls",
    "hunter_calls": "hunter_calls",
    "apollo": "hunter_calls",
}

# Map of accepted api_name aliases to canonical provider names in prospectiq.api_quotas
PROVIDER_MAP = {
    "serpapi": "serpapi",
    "serpapi_calls": "serpapi",
    "brave": "brave",
    "brave_calls": "brave",
    "hunter": "hunter",
    "hunter_calls": "hunter",
    "apollo": "hunter",
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
    Retrieve the current UTC year and month as a string key ('YYYY-MM').
    """
    return datetime.now(timezone.utc).strftime("%Y-%m")


def _load_tracker() -> dict:
    """Load API usage statistics from the local persistent JSON file."""
    if not os.path.exists(TRACKER_FILE):
        return {}
    try:
        with open(TRACKER_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:
        log.error(f"Failed to load tracker file: {exc}")
        return {}


def _save_tracker(data: dict) -> None:
    """Write updated API usage statistics back to the local JSON file."""
    try:
        with open(TRACKER_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
    except Exception as exc:
        log.error(f"Failed to save tracker file: {exc}")


def _normalize_month_record(record: dict) -> dict:
    """Ensure all tracked API keys exist in the monthly record, supporting legacy keys."""
    normalized = dict(DEFAULT_MONTHLY_COUNTERS)
    if "serpapi" in record:
        normalized["serpapi_calls"] = record["serpapi"]
    if "brave" in record:
        normalized["brave_calls"] = record["brave"]
    if "hunter" in record:
        normalized["hunter_calls"] = record["hunter"]

    for k in DEFAULT_MONTHLY_COUNTERS:
        if k in record:
            normalized[k] = record[k]
    return normalized


def _check_and_increment_cloud(provider: str, api_name: str, max_limit: int, month: str) -> int:
    """Execute atomic PostgreSQL RPC `prospectiq.check_and_increment_quota` via Supabase."""
    schema = database.get_supabase_schema_client()
    resp = schema.rpc(
        "check_and_increment_quota",
        {
            "p_month_key": month,
            "p_provider": provider,
            "p_monthly_limit": int(max_limit),
        },
    ).execute()

    raw_data: Any = resp.data
    row: Optional[Dict[str, Any]] = None
    if isinstance(raw_data, list) and raw_data:
        row = raw_data[0]
    elif isinstance(raw_data, dict):
        row = raw_data

    if not row:
        raise RuntimeError(
            f"Unexpected empty response from prospectiq.check_and_increment_quota for '{provider}'."
        )

    allowed = bool(row.get("allowed", False))
    calls_used = int(row.get("calls_used", 0))
    effective_limit = int(row.get("monthly_limit", max_limit))

    if not allowed:
        raise QuotaExhaustedError(
            api_name=api_name,
            max_limit=effective_limit,
            month=month,
            current_count=calls_used,
        )

    log.debug(
        f"Cloud API quota incremented: {provider} -> {calls_used}/{effective_limit} for {month}"
    )
    return calls_used


def check_and_increment(api_name: str, max_limit: int) -> int:
    """
    Verify whether an API quota is available, and atomically increment the counter if under limit.

    Routes to Supabase `prospectiq.api_quotas` when cloud mode is enabled, and falls back
    to local `usage_tracker.json` during offline/local CLI runs.
    """
    normalized_name = api_name.lower().strip()
    canonical_key = API_KEY_MAP.get(normalized_name)
    provider = PROVIDER_MAP.get(normalized_name)
    if not canonical_key or not provider:
        raise ValueError(
            f"Unknown API '{api_name}'. Expected one of: 'serpapi', 'brave', 'hunter'."
        )

    month = _get_current_month()

    if database.is_cloud_enabled():
        return _check_and_increment_cloud(
            provider=provider,
            api_name=api_name,
            max_limit=max_limit,
            month=month,
        )

    data = _load_tracker()

    # Initialize / normalize monthly tracking record (auto-reset on new calendar month)
    if month not in data:
        data[month] = dict(DEFAULT_MONTHLY_COUNTERS)
    else:
        data[month] = _normalize_month_record(data[month])

    current_count = data[month].get(canonical_key, 0)

    if current_count >= max_limit:
        raise QuotaExhaustedError(
            api_name=api_name,
            max_limit=max_limit,
            month=month,
            current_count=current_count,
        )

    new_count = current_count + 1
    data[month][canonical_key] = new_count
    _save_tracker(data)

    log.debug(f"API quota counter incremented: {api_name} -> {new_count}/{max_limit} for {month}")
    return new_count


def get_monthly_usage(month: Optional[str] = None) -> Dict[str, int]:
    """Return current month API call counts keyed by provider (`serpapi`, `brave`, `hunter`)."""
    target_month = month or _get_current_month()
    usage: Dict[str, int] = {"serpapi": 0, "brave": 0, "hunter": 0}

    if database.is_cloud_enabled():
        schema = database.get_supabase_schema_client()
        resp = (
            schema.table("api_quotas")
            .select("provider, calls_used")
            .eq("month_key", target_month)
            .execute()
        )
        for row in resp.data or []:
            prov = str(row.get("provider") or "").lower()
            if prov in usage:
                usage[prov] = int(row.get("calls_used") or 0)
        return usage

    data = _load_tracker()
    record = _normalize_month_record(data.get(target_month, {}))
    usage["serpapi"] = int(record.get("serpapi_calls", 0))
    usage["brave"] = int(record.get("brave_calls", 0))
    usage["hunter"] = int(record.get("hunter_calls", 0))
    return usage
