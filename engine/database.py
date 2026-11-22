"""
Storage Layer — database.py

Dual-mode persistence layer supporting:
  1. Cloud Mode (Supabase PostgreSQL via PostgREST, strictly scoped to `prospectiq.*`
     schema) when `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` are configured.
  2. Local Fallback Mode (SQLite `leads.db`) when Supabase credentials are absent
     or when an explicit local `db_path` is passed (e.g. offline unit tests).

This module is the ONLY place authorized to execute database read/write operations.
"""

from contextlib import closing
from datetime import datetime, timezone
import importlib
import json
import os
import sqlite3
import sys
import urllib.parse
from typing import Any, Dict, List, Optional

from engine import config
from engine.logger import setup_logger
from engine.models import BusinessLead

try:
    DB_PATH = config.DB_PATH
except AttributeError:
    DB_PATH = "leads.db"

log = setup_logger("database")

# Cached Supabase base client (lazy-initialized only when cloud mode is active)
_SUPABASE_CLIENT: Optional[Any] = None

# Columns added in v3.0 (auto-migrated safely onto existing v2.0 SQLite databases)
_V3_MIGRATION_COLUMNS: Dict[str, str] = {
    "place_id": "TEXT",
    "phone": "TEXT",
    "address": "TEXT",
    "rating": "REAL",
    "reviews_count": "INTEGER DEFAULT 0",
    "business_status": "TEXT DEFAULT 'OPERATIONAL'",
    "is_franchise": "INTEGER DEFAULT 0",
    "website_status": "TEXT DEFAULT 'NO_WEBSITE'",
    "root_domain": "TEXT",
    "has_ssl": "INTEGER",
    "is_mobile_friendly": "INTEGER",
    "cms_platform": "TEXT",
    "has_analytics": "INTEGER",
    "has_meta_pixel": "INTEGER",
    "load_time_ms": "INTEGER",
    "email_mx_valid": "INTEGER",
    "secondary_emails": "TEXT DEFAULT '[]'",
    "opportunity_score": "INTEGER DEFAULT 0",
    "pitch_tier": "TEXT DEFAULT 'COLD'",
    "pitch_angle": "TEXT DEFAULT 'ESTABLISHED'",
    "pitch_summary": "TEXT",
    "outreach_status": "TEXT DEFAULT 'NEW'",
    "outreach_notes": "TEXT DEFAULT ''",
}


# ──────────────────────────────────────────────
# Backend Detection & Supabase Client Lifecycle
# ──────────────────────────────────────────────

def get_supabase_schema() -> str:
    """Return the configured isolated PostgreSQL schema name (default: 'prospectiq')."""
    return (getattr(config, "SUPABASE_SCHEMA", "") or "prospectiq").strip() or "prospectiq"


def is_cloud_enabled() -> bool:
    """
    Return True when shared-apps Supabase publishable credentials AND Owner auth
    credentials are configured. Never uses `service_role` so sibling schemas
    (e.g. `cadence`) remain strictly protected by RLS.
    """
    url = (getattr(config, "SUPABASE_URL", "") or "").strip()
    anon_key = (getattr(config, "SUPABASE_ANON_KEY", "") or "").strip()
    owner_email = (getattr(config, "SUPABASE_OWNER_EMAIL", "") or "").strip()
    owner_password = (getattr(config, "SUPABASE_OWNER_PASSWORD", "") or "").strip()
    return bool(url and anon_key and owner_email and owner_password)


def _use_supabase(db_path: Optional[str] = None) -> bool:
    """
    Use Supabase when cloud credentials exist AND the caller has not explicitly
    overridden `db_path` to a custom local SQLite file (e.g. temp test DB).
    """
    if db_path is not None and db_path != DB_PATH:
        return False
    return is_cloud_enabled()


def reset_supabase_client() -> None:
    """Clear the cached Supabase client instance (used in tests and reconfiguration)."""
    global _SUPABASE_CLIENT
    _SUPABASE_CLIENT = None


def _import_supabase_create_client() -> Any:
    """
    Import `create_client` from the installed `supabase` PyPI package without being
    shadowed by the repository's local `supabase/` SQL migrations directory.
    """
    repo_root = os.path.abspath(getattr(config, "BASE_DIR", os.getcwd()))
    saved_path = list(sys.path)
    existing = sys.modules.get("supabase")
    try:
        if existing is not None and not hasattr(existing, "create_client"):
            del sys.modules["supabase"]
        sys.path = [p for p in sys.path if os.path.abspath(p or ".") != repo_root]
        mod = importlib.import_module("supabase")
        if not hasattr(mod, "create_client"):
            raise ImportError("Installed 'supabase' package does not expose create_client.")
        return mod.create_client
    except ImportError as exc:
        raise RuntimeError(
            "The 'supabase' package is required for cloud persistence. "
            "Install it via 'pip install supabase>=2.15.0'."
        ) from exc
    finally:
        sys.path = saved_path


def ensure_owner_profile(
    schema_client: Any,
    user_id: str,
    email: Optional[str] = None,
    full_name: Optional[str] = None,
) -> None:
    """
    Lazily and idempotently provision the Owner's `prospectiq.profiles` row on first
    authenticated visit (replaces any shared `auth.users` trigger so sibling apps
    like `cadence` are never impacted).
    """
    if not user_id:
        return
    try:
        payload: Dict[str, Any] = {
            "id": user_id,
            "email": email,
            "role": "owner",
            "updated_at": _utc_now_iso(),
        }
        if full_name:
            payload["full_name"] = full_name
        schema_client.table("profiles").upsert(payload, on_conflict="id").execute()
    except Exception as exc:
        log.warning(f"Non-fatal error lazily provisioning prospectiq.profiles row: {exc}")


def get_supabase_schema_client() -> Any:
    """
    Return an Owner-authenticated PostgREST client scoped strictly to
    `get_supabase_schema()` (`prospectiq`), initialized using ONLY the publishable
    `SUPABASE_ANON_KEY` (`sb_publishable_...`) and Owner Auth JWT (zero `service_role`).
    """
    global _SUPABASE_CLIENT
    schema_name = get_supabase_schema()

    if _SUPABASE_CLIENT is None:
        if os.getenv("SUPABASE_SERVICE_ROLE_KEY"):
            log.warning(
                "Ignoring SUPABASE_SERVICE_ROLE_KEY: shared-apps requires publishable key "
                "+ Owner JWT authentication so sibling schemas (e.g. 'cadence') remain RLS-safe."
            )

        url = (getattr(config, "SUPABASE_URL", "") or "").strip()
        anon_key = (getattr(config, "SUPABASE_ANON_KEY", "") or "").strip()
        owner_email = (getattr(config, "SUPABASE_OWNER_EMAIL", "") or "").strip()
        owner_password = (getattr(config, "SUPABASE_OWNER_PASSWORD", "") or "").strip()

        if not (url and anon_key and owner_email and owner_password):
            raise RuntimeError(
                "Supabase cloud mode requires SUPABASE_URL, SUPABASE_ANON_KEY "
                "(publishable key), SUPABASE_OWNER_EMAIL, and SUPABASE_OWNER_PASSWORD."
            )

        create_client = _import_supabase_create_client()
        client = create_client(url, anon_key)

        auth_resp = client.auth.sign_in_with_password(
            {"email": owner_email, "password": owner_password}
        )
        session = getattr(auth_resp, "session", None)
        user = getattr(auth_resp, "user", None)
        access_token = getattr(session, "access_token", None)
        if not access_token:
            raise RuntimeError(
                "Supabase Owner authentication succeeded without returning an access token."
            )
        if hasattr(client, "postgrest") and hasattr(client.postgrest, "auth"):
            client.postgrest.auth(access_token)

        _SUPABASE_CLIENT = client
        schema_client = _SUPABASE_CLIENT.schema(schema_name)

        user_id = str(getattr(user, "id", "") or "")
        user_email = str(getattr(user, "email", "") or owner_email)
        ensure_owner_profile(schema_client, user_id=user_id, email=user_email)

        log.info(
            f"Initialized publishable-key Supabase client (schema='{schema_name}', "
            f"owner_authenticated=True)."
        )
        return schema_client

    return _SUPABASE_CLIENT.schema(schema_name)


# ──────────────────────────────────────────────
# Shared Serialization & Normalization Helpers
# ──────────────────────────────────────────────

def _extract_root_domain(url: Optional[str]) -> Optional[str]:
    """Extract normalized root domain (e.g. 'reliantplumbing.com') from a URL."""
    if not url or not str(url).strip():
        return None
    try:
        raw_url = str(url).strip()
        if "://" not in raw_url:
            raw_url = "https://" + raw_url
        parsed = urllib.parse.urlsplit(raw_url)
        host = (parsed.hostname or "").lower().strip()
        for prefix in ("www.", "m.", "mobile."):
            if host.startswith(prefix):
                host = host[len(prefix) :]
        return host if host else None
    except Exception:
        return None


def _escape_ilike(value: str) -> str:
    """Escape SQL LIKE wildcards so PostgREST ilike behaves as exact case-insensitive match."""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _bool_to_int(val: Optional[bool]) -> Optional[int]:
    if val is None:
        return None
    return 1 if val else 0


def _int_to_bool(val: Optional[int]) -> Optional[bool]:
    if val is None:
        return None
    return bool(val)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _lead_to_supabase_payload(
    lead: BusinessLead,
    scrape_job_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Serialize a strict BusinessLead contract into the JSONB payload expected by prospectiq.upsert_lead."""
    root_domain = lead.root_domain or _extract_root_domain(lead.website_url)
    payload: Dict[str, Any] = {
        "place_id": lead.place_id,
        "business_name": lead.business_name.strip(),
        "city": lead.city.strip(),
        "industry": lead.industry.strip(),
        "phone": lead.phone,
        "address": lead.address,
        "rating": lead.rating,
        "reviews_count": lead.reviews_count,
        "business_status": lead.business_status,
        "is_franchise": lead.is_franchise,
        "website_status": lead.website_status,
        "website_url": lead.website_url,
        "root_domain": root_domain,
        "http_status": lead.http_status,
        "has_ssl": lead.has_ssl,
        "is_mobile_friendly": lead.is_mobile_friendly,
        "cms_platform": lead.cms_platform,
        "has_analytics": lead.has_analytics,
        "has_meta_pixel": lead.has_meta_pixel,
        "load_time_ms": lead.load_time_ms,
        "email": lead.email,
        "email_status": lead.email_status,
        "email_mx_valid": lead.email_mx_valid,
        "secondary_emails": list(lead.secondary_emails),
        "linkedin": lead.linkedin,
        "instagram": lead.instagram,
        "facebook": lead.facebook,
        "twitter": lead.twitter,
        "social_status": lead.social_status,
        "opportunity_score": lead.opportunity_score,
        "pitch_tier": lead.pitch_tier,
        "pitch_angle": lead.pitch_angle,
        "pitch_summary": lead.pitch_summary,
        "outreach_status": lead.outreach_status,
        "outreach_notes": lead.outreach_notes,
        "scrape_job_id": scrape_job_id,
    }
    return payload


def _dict_to_lead(row: Dict[str, Any]) -> BusinessLead:
    """Hydrate a strict BusinessLead model from a Supabase PostgreSQL row dictionary."""
    website_status = str(row.get("website_status") or "NO_WEBSITE")
    raw_secondary = row.get("secondary_emails")
    if isinstance(raw_secondary, str):
        try:
            secondary_list = json.loads(raw_secondary)
        except Exception:
            secondary_list = []
    elif isinstance(raw_secondary, list):
        secondary_list = [str(item) for item in raw_secondary]
    else:
        secondary_list = []

    raw_rating = row.get("rating")
    rating_val = float(raw_rating) if raw_rating is not None else None
    raw_load = row.get("load_time_ms")
    load_val = int(raw_load) if raw_load is not None else None

    return BusinessLead(
        place_id=row.get("place_id"),
        business_name=str(row["business_name"]),
        city=str(row["city"]),
        industry=str(row["industry"]),
        phone=row.get("phone"),
        address=row.get("address"),
        rating=rating_val,
        reviews_count=int(row.get("reviews_count") or 0),
        business_status=str(row.get("business_status") or "OPERATIONAL"),
        is_franchise=bool(row.get("is_franchise", False)),
        timestamp=str(row.get("last_enriched_at") or row.get("discovered_at") or _utc_now_iso()),
        website_found=website_status in ("LIVE", "WAF_PROTECTED"),
        website_status=website_status,  # type: ignore[arg-type]
        website_url=row.get("website_url"),
        root_domain=row.get("root_domain") or _extract_root_domain(row.get("website_url")),
        http_status=row.get("http_status"),
        has_ssl=row.get("has_ssl"),
        is_mobile_friendly=row.get("is_mobile_friendly"),
        cms_platform=row.get("cms_platform"),
        has_analytics=row.get("has_analytics"),
        has_meta_pixel=row.get("has_meta_pixel"),
        load_time_ms=load_val,
        email=row.get("email"),
        email_status=str(row.get("email_status") or "NOT_ATTEMPTED"),  # type: ignore[arg-type]
        email_mx_valid=row.get("email_mx_valid"),
        secondary_emails=secondary_list,
        linkedin=row.get("linkedin"),
        instagram=row.get("instagram"),
        facebook=row.get("facebook"),
        twitter=row.get("twitter"),
        social_status=str(row.get("social_status") or "NOT_ATTEMPTED"),  # type: ignore[arg-type]
        opportunity_score=int(row.get("opportunity_score") or 0),
        pitch_tier=str(row.get("pitch_tier") or "COLD"),  # type: ignore[arg-type]
        pitch_angle=str(row.get("pitch_angle") or "ESTABLISHED"),  # type: ignore[arg-type]
        pitch_summary=row.get("pitch_summary"),
        outreach_status=str(row.get("outreach_status") or "NEW"),  # type: ignore[arg-type]
        outreach_notes=str(row.get("outreach_notes") or ""),
    )


# ──────────────────────────────────────────────
# SQLite Local Connection & Initialization
# ──────────────────────────────────────────────

def get_connection(db_path: str = DB_PATH) -> sqlite3.Connection:
    """Create and return a SQLite connection configured with sqlite3.Row."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: str = DB_PATH) -> None:
    """
    Initialize the active storage backend:
      - Cloud Mode: verifies Supabase client initialization targeting `prospectiq`.
      - Local Mode: initializes SQLite `leads` table and safely migrates v2.0 schemas.
    """
    if _use_supabase(db_path):
        get_supabase_schema_client()
        return

    with closing(sqlite3.connect(db_path)) as conn:
        with conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS leads (
                    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                    place_id            TEXT,
                    business_name       TEXT NOT NULL,
                    city                TEXT NOT NULL,
                    industry            TEXT NOT NULL,
                    phone               TEXT,
                    address             TEXT,
                    rating              REAL,
                    reviews_count       INTEGER NOT NULL DEFAULT 0,
                    business_status     TEXT NOT NULL DEFAULT 'OPERATIONAL',
                    is_franchise        INTEGER NOT NULL DEFAULT 0,
                    timestamp           TEXT NOT NULL,
                    website_found       INTEGER NOT NULL,
                    website_status      TEXT NOT NULL DEFAULT 'NO_WEBSITE',
                    website_url         TEXT,
                    root_domain         TEXT,
                    http_status         TEXT,
                    has_ssl             INTEGER,
                    is_mobile_friendly  INTEGER,
                    cms_platform        TEXT,
                    has_analytics       INTEGER,
                    has_meta_pixel      INTEGER,
                    load_time_ms        INTEGER,
                    email               TEXT,
                    email_status        TEXT NOT NULL DEFAULT 'NOT_ATTEMPTED',
                    email_mx_valid      INTEGER,
                    secondary_emails    TEXT NOT NULL DEFAULT '[]',
                    linkedin            TEXT,
                    instagram           TEXT,
                    facebook            TEXT,
                    twitter             TEXT,
                    social_status       TEXT NOT NULL DEFAULT 'NOT_ATTEMPTED',
                    opportunity_score   INTEGER NOT NULL DEFAULT 0,
                    pitch_tier          TEXT NOT NULL DEFAULT 'COLD',
                    pitch_angle         TEXT NOT NULL DEFAULT 'ESTABLISHED',
                    pitch_summary       TEXT,
                    outreach_status     TEXT NOT NULL DEFAULT 'NEW',
                    outreach_notes      TEXT NOT NULL DEFAULT '',
                    UNIQUE(business_name, city)
                );
                """
            )

            # Safe additive migration for pre-existing v2.0 SQLite tables
            existing_cols = {
                row[1] for row in cursor.execute("PRAGMA table_info(leads)").fetchall()
            }
            for col_name, col_def in _V3_MIGRATION_COLUMNS.items():
                if col_name not in existing_cols:
                    cursor.execute(f"ALTER TABLE leads ADD COLUMN {col_name} {col_def}")
                    log.info(f"Migrated SQLite leads table: added column '{col_name}'")

            # Backfill website_status for pre-existing v2.0 rows where website_found=1
            cursor.execute(
                """
                UPDATE leads
                SET website_status = 'LIVE'
                WHERE website_found = 1 AND (website_status IS NULL OR website_status = 'NO_WEBSITE')
                """
            )

            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_leads_root_domain ON leads(root_domain)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_leads_place_id ON leads(place_id)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_leads_score ON leads(opportunity_score DESC)"
            )


# ──────────────────────────────────────────────
# Lead Deduplication, UPSERT, and Queries
# ──────────────────────────────────────────────

def is_duplicate(
    business_name: str,
    city: str,
    place_id: Optional[str] = None,
    website_url: Optional[str] = None,
    db_path: str = DB_PATH,
) -> bool:
    """
    Pre-scrape deduplication check across `place_id`, `(business_name, city)`,
    AND normalized `root_domain` so duplicate businesses never waste Hunter.io
    credits or web requests.
    """
    domain = _extract_root_domain(website_url)

    if _use_supabase(db_path):
        schema = get_supabase_schema_client()
        if place_id:
            resp = (
                schema.table("leads")
                .select("id")
                .eq("place_id", place_id)
                .limit(1)
                .execute()
            )
            if resp.data:
                return True

        resp = (
            schema.table("leads")
            .select("id")
            .ilike("business_name", _escape_ilike(business_name.strip()))
            .ilike("city", _escape_ilike(city.strip()))
            .limit(1)
            .execute()
        )
        if resp.data:
            return True

        if domain:
            resp = (
                schema.table("leads")
                .select("id")
                .eq("root_domain", domain.lower())
                .limit(1)
                .execute()
            )
            if resp.data:
                return True

        return False

    init_db(db_path)
    with closing(sqlite3.connect(db_path)) as conn:
        cursor = conn.cursor()

        # 1. Google Place ID check (strongest identity match)
        if place_id:
            cursor.execute("SELECT 1 FROM leads WHERE place_id = ? LIMIT 1", (place_id,))
            if cursor.fetchone() is not None:
                return True

        # 2. Exact (business_name, city) check (case-insensitive)
        cursor.execute(
            "SELECT 1 FROM leads WHERE lower(business_name) = lower(?) AND lower(city) = lower(?) LIMIT 1",
            (business_name.strip(), city.strip()),
        )
        if cursor.fetchone() is not None:
            return True

        # 3. Root domain check (prevents multi-location / renamed GBP duplicate scrapes)
        if domain:
            cursor.execute(
                """
                SELECT 1 FROM leads
                WHERE lower(root_domain) = ?
                   OR website_url LIKE '%://' || ? || '/%'
                   OR website_url LIKE '%://' || ? || '?%'
                   OR website_url LIKE '%://' || ?
                   OR website_url LIKE '%://www.' || ? || '/%'
                   OR website_url LIKE '%://www.' || ? || '?%'
                   OR website_url LIKE '%://www.' || ?
                LIMIT 1
                """,
                (domain, domain, domain, domain, domain, domain, domain),
            )
            if cursor.fetchone() is not None:
                return True

    return False


def upsert_lead_with_status(
    lead: BusinessLead,
    db_path: str = DB_PATH,
    scrape_job_id: Optional[str] = None,
) -> str:
    """
    True SQL UPSERT returning exact outcome: `'inserted'`, `'updated'`, or `'skipped_domain_dup'`.
    Preserves existing verified contacts and agency CRM notes on re-enrichment.
    """
    if _use_supabase(db_path):
        schema = get_supabase_schema_client()
        payload = _lead_to_supabase_payload(lead, scrape_job_id=scrape_job_id)
        resp = schema.rpc("upsert_lead", {"p_lead": payload}).execute()
        outcome = str(resp.data or "updated").strip()
        if outcome == "skipped_domain_dup":
            log.info(f"Domain duplicate skipped on cloud upsert: {payload.get('root_domain')}")
        return outcome

    init_db(db_path)
    root_domain = lead.root_domain or _extract_root_domain(lead.website_url)
    secondary_json = json.dumps(lead.secondary_emails)

    with closing(sqlite3.connect(db_path)) as conn:
        with conn:
            cursor = conn.cursor()

            # Prevent inserting a distinct business_name that duplicates another row's root_domain
            if root_domain:
                cursor.execute(
                    """
                    SELECT 1 FROM leads
                    WHERE lower(root_domain) = ?
                      AND NOT (lower(business_name) = lower(?) AND lower(city) = lower(?))
                    LIMIT 1
                    """,
                    (root_domain, lead.business_name.strip(), lead.city.strip()),
                )
                if cursor.fetchone() is not None:
                    log.info(f"Domain duplicate skipped on upsert: {root_domain}")
                    return "skipped_domain_dup"

            cursor.execute(
                "SELECT 1 FROM leads WHERE business_name = ? AND city = ? LIMIT 1",
                (lead.business_name, lead.city),
            )
            existed_before = cursor.fetchone() is not None

            cursor.execute(
                """
                INSERT INTO leads (
                    place_id, business_name, city, industry, phone, address,
                    rating, reviews_count, business_status, is_franchise, timestamp,
                    website_found, website_status, website_url, root_domain, http_status,
                    has_ssl, is_mobile_friendly, cms_platform, has_analytics, has_meta_pixel, load_time_ms,
                    email, email_status, email_mx_valid, secondary_emails,
                    linkedin, instagram, facebook, twitter, social_status,
                    opportunity_score, pitch_tier, pitch_angle, pitch_summary,
                    outreach_status, outreach_notes
                ) VALUES (
                    ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?,
                    ?, ?, ?, ?, ?,
                    ?, ?, ?, ?,
                    ?, ?
                )
                ON CONFLICT(business_name, city) DO UPDATE SET
                    place_id           = COALESCE(excluded.place_id, leads.place_id),
                    phone              = COALESCE(excluded.phone, leads.phone),
                    address            = COALESCE(excluded.address, leads.address),
                    rating             = COALESCE(excluded.rating, leads.rating),
                    reviews_count      = MAX(excluded.reviews_count, COALESCE(leads.reviews_count, 0)),
                    business_status    = excluded.business_status,
                    is_franchise       = excluded.is_franchise,
                    timestamp          = excluded.timestamp,
                    website_found      = excluded.website_found,
                    website_status     = excluded.website_status,
                    website_url        = COALESCE(excluded.website_url, leads.website_url),
                    root_domain        = COALESCE(excluded.root_domain, leads.root_domain),
                    http_status        = excluded.http_status,
                    has_ssl            = COALESCE(excluded.has_ssl, leads.has_ssl),
                    is_mobile_friendly = COALESCE(excluded.is_mobile_friendly, leads.is_mobile_friendly),
                    cms_platform       = COALESCE(excluded.cms_platform, leads.cms_platform),
                    has_analytics      = COALESCE(excluded.has_analytics, leads.has_analytics),
                    has_meta_pixel     = COALESCE(excluded.has_meta_pixel, leads.has_meta_pixel),
                    load_time_ms       = COALESCE(excluded.load_time_ms, leads.load_time_ms),
                    email              = COALESCE(excluded.email, leads.email),
                    email_status       = CASE WHEN excluded.email IS NOT NULL THEN excluded.email_status ELSE leads.email_status END,
                    email_mx_valid     = COALESCE(excluded.email_mx_valid, leads.email_mx_valid),
                    secondary_emails   = CASE WHEN excluded.secondary_emails != '[]' THEN excluded.secondary_emails ELSE leads.secondary_emails END,
                    linkedin           = COALESCE(excluded.linkedin, leads.linkedin),
                    instagram          = COALESCE(excluded.instagram, leads.instagram),
                    facebook           = COALESCE(excluded.facebook, leads.facebook),
                    twitter            = COALESCE(excluded.twitter, leads.twitter),
                    social_status      = CASE
                                             WHEN excluded.linkedin IS NOT NULL OR excluded.instagram IS NOT NULL
                                                  OR excluded.facebook IS NOT NULL OR excluded.twitter IS NOT NULL
                                             THEN excluded.social_status
                                             ELSE leads.social_status
                                         END,
                    opportunity_score  = excluded.opportunity_score,
                    pitch_tier         = excluded.pitch_tier,
                    pitch_angle        = excluded.pitch_angle,
                    pitch_summary      = excluded.pitch_summary
                    -- outreach_status and outreach_notes intentionally preserved on re-enrichment!
                """,
                (
                    lead.place_id,
                    lead.business_name,
                    lead.city,
                    lead.industry,
                    lead.phone,
                    lead.address,
                    lead.rating,
                    lead.reviews_count,
                    lead.business_status,
                    1 if lead.is_franchise else 0,
                    lead.timestamp,
                    1 if lead.website_found else 0,
                    lead.website_status,
                    lead.website_url,
                    root_domain,
                    lead.http_status,
                    _bool_to_int(lead.has_ssl),
                    _bool_to_int(lead.is_mobile_friendly),
                    lead.cms_platform,
                    _bool_to_int(lead.has_analytics),
                    _bool_to_int(lead.has_meta_pixel),
                    lead.load_time_ms,
                    lead.email,
                    lead.email_status,
                    _bool_to_int(lead.email_mx_valid),
                    secondary_json,
                    lead.linkedin,
                    lead.instagram,
                    lead.facebook,
                    lead.twitter,
                    lead.social_status,
                    lead.opportunity_score,
                    lead.pitch_tier,
                    lead.pitch_angle,
                    lead.pitch_summary,
                    lead.outreach_status,
                    lead.outreach_notes,
                ),
            )
            return "updated" if existed_before else "inserted"


def upsert_lead(
    lead: BusinessLead,
    db_path: str = DB_PATH,
    scrape_job_id: Optional[str] = None,
) -> bool:
    """
    Backwards-compatible UPSERT wrapper returning True if the lead was inserted or updated.
    """
    outcome = upsert_lead_with_status(lead, db_path=db_path, scrape_job_id=scrape_job_id)
    return outcome in ("inserted", "updated")


def _row_to_lead(row: sqlite3.Row) -> BusinessLead:
    keys = row.keys()
    raw_secondary = row["secondary_emails"] if "secondary_emails" in keys else "[]"
    try:
        secondary_list = json.loads(raw_secondary) if raw_secondary else []
    except Exception:
        secondary_list = []

    return BusinessLead(
        place_id=row["place_id"] if "place_id" in keys else None,
        business_name=row["business_name"],
        city=row["city"],
        industry=row["industry"],
        phone=row["phone"] if "phone" in keys else None,
        address=row["address"] if "address" in keys else None,
        rating=float(row["rating"]) if ("rating" in keys and row["rating"] is not None) else None,
        reviews_count=int(row["reviews_count"] or 0) if "reviews_count" in keys else 0,
        business_status=(row["business_status"] or "OPERATIONAL") if "business_status" in keys else "OPERATIONAL",
        is_franchise=bool(row["is_franchise"]) if "is_franchise" in keys else False,
        timestamp=row["timestamp"],
        website_found=bool(row["website_found"]),
        website_status=(row["website_status"] or ("LIVE" if row["website_found"] else "NO_WEBSITE")) if "website_status" in keys else ("LIVE" if row["website_found"] else "NO_WEBSITE"),
        website_url=row["website_url"],
        root_domain=row["root_domain"] if "root_domain" in keys else _extract_root_domain(row["website_url"]),
        http_status=row["http_status"],
        has_ssl=_int_to_bool(row["has_ssl"]) if "has_ssl" in keys else None,
        is_mobile_friendly=_int_to_bool(row["is_mobile_friendly"]) if "is_mobile_friendly" in keys else None,
        cms_platform=row["cms_platform"] if "cms_platform" in keys else None,
        has_analytics=_int_to_bool(row["has_analytics"]) if "has_analytics" in keys else None,
        has_meta_pixel=_int_to_bool(row["has_meta_pixel"]) if "has_meta_pixel" in keys else None,
        load_time_ms=int(row["load_time_ms"]) if ("load_time_ms" in keys and row["load_time_ms"] is not None) else None,
        email=row["email"],
        email_status=row["email_status"],
        email_mx_valid=_int_to_bool(row["email_mx_valid"]) if "email_mx_valid" in keys else None,
        secondary_emails=secondary_list,
        linkedin=row["linkedin"],
        instagram=row["instagram"],
        facebook=row["facebook"],
        twitter=row["twitter"],
        social_status=row["social_status"],
        opportunity_score=int(row["opportunity_score"] or 0) if "opportunity_score" in keys else 0,
        pitch_tier=(row["pitch_tier"] or "COLD") if "pitch_tier" in keys else "COLD",
        pitch_angle=(row["pitch_angle"] or "ESTABLISHED") if "pitch_angle" in keys else "ESTABLISHED",
        pitch_summary=row["pitch_summary"] if "pitch_summary" in keys else None,
        outreach_status=(row["outreach_status"] or "NEW") if "outreach_status" in keys else "NEW",
        outreach_notes=(row["outreach_notes"] or "") if "outreach_notes" in keys else "",
    )


def get_all_leads(db_path: str = DB_PATH, limit: int = 1000) -> List[BusinessLead]:
    """Retrieve all records ordered by opportunity_score DESC."""
    if _use_supabase(db_path):
        schema = get_supabase_schema_client()
        resp = (
            schema.table("leads")
            .select("*")
            .order("opportunity_score", desc=True)
            .order("discovered_at", desc=True)
            .limit(limit)
            .execute()
        )
        return [_dict_to_lead(row) for row in (resp.data or [])]

    init_db(db_path)
    with closing(get_connection(db_path)) as conn:
        rows = conn.execute(
            "SELECT * FROM leads ORDER BY opportunity_score DESC, id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [_row_to_lead(row) for row in rows]


def get_leads_by_status(
    website_found: Optional[bool] = None,
    website_status: Optional[str] = None,
    email_status: Optional[str] = None,
    social_status: Optional[str] = None,
    pitch_tier: Optional[str] = None,
    db_path: str = DB_PATH,
    limit: int = 1000,
) -> List[BusinessLead]:
    """Retrieve leads filtered by status or pitch tier as validated BusinessLead objects."""
    if _use_supabase(db_path):
        schema = get_supabase_schema_client()
        query = schema.table("leads").select("*")
        if website_status is not None:
            query = query.eq("website_status", website_status)
        elif website_found is True:
            query = query.in_("website_status", ["LIVE", "WAF_PROTECTED"])
        elif website_found is False:
            query = query.in_("website_status", ["NO_WEBSITE", "BROKEN", "PARKED"])
        if email_status is not None:
            query = query.eq("email_status", email_status)
        if social_status is not None:
            query = query.eq("social_status", social_status)
        if pitch_tier is not None:
            query = query.eq("pitch_tier", pitch_tier)
        resp = (
            query.order("opportunity_score", desc=True)
            .order("discovered_at", desc=True)
            .limit(limit)
            .execute()
        )
        return [_dict_to_lead(row) for row in (resp.data or [])]

    init_db(db_path)
    conditions: List[str] = []
    params: List[object] = []

    if website_found is not None:
        conditions.append("website_found = ?")
        params.append(1 if website_found else 0)
    if website_status is not None:
        conditions.append("website_status = ?")
        params.append(website_status)
    if email_status is not None:
        conditions.append("email_status = ?")
        params.append(email_status)
    if social_status is not None:
        conditions.append("social_status = ?")
        params.append(social_status)
    if pitch_tier is not None:
        conditions.append("pitch_tier = ?")
        params.append(pitch_tier)

    query_sql = "SELECT * FROM leads"
    if conditions:
        query_sql += " WHERE " + " AND ".join(conditions)
    query_sql += " ORDER BY opportunity_score DESC, id DESC LIMIT ?"
    params.append(limit)

    with closing(get_connection(db_path)) as conn:
        rows = conn.execute(query_sql, tuple(params)).fetchall()
        return [_row_to_lead(row) for row in rows]


# ──────────────────────────────────────────────
# Phase 2: Cloud Scrape Jobs, Target Queue & Exclusions
# ──────────────────────────────────────────────

def create_scrape_job(
    trigger_source: str,
    cities: List[str],
    niches: List[str],
    max_results_per_query: int = 10,
    github_run_url: Optional[str] = None,
    job_id: Optional[str] = None,
) -> Optional[str]:
    """
    Start or attach to a `prospectiq.scrape_jobs` execution row in Supabase.
    Returns the job UUID in cloud mode, or None when running locally on SQLite.
    """
    if not is_cloud_enabled():
        return None

    try:
        schema = get_supabase_schema_client()
        now_iso = _utc_now_iso()

        if job_id:
            update_payload: Dict[str, Any] = {
                "status": "RUNNING",
                "started_at": now_iso,
            }
            if github_run_url:
                update_payload["github_run_url"] = github_run_url
            if cities:
                update_payload["cities"] = cities
            if niches:
                update_payload["niches"] = niches
            schema.table("scrape_jobs").update(update_payload).eq("id", job_id).execute()
            log.info(f"Attached to queued scrape_job {job_id} (status -> RUNNING).")
            return job_id

        insert_payload: Dict[str, Any] = {
            "trigger_source": trigger_source,
            "status": "RUNNING",
            "cities": cities,
            "niches": niches,
            "max_results_per_query": max_results_per_query,
            "github_run_url": github_run_url,
            "started_at": now_iso,
        }
        resp = schema.table("scrape_jobs").insert(insert_payload).execute()
        created_id = str(resp.data[0]["id"]) if resp.data else None
        if created_id:
            log.info(f"Created scrape_job {created_id} (trigger={trigger_source}, status=RUNNING).")
        return created_id
    except Exception as exc:
        log.error(f"Failed to create/attach scrape_job in Supabase: {exc}")
        return job_id


def update_scrape_job_progress(
    job_id: Optional[str],
    stats: Dict[str, int],
) -> None:
    """Stream live job telemetry counters to `prospectiq.scrape_jobs` for Realtime UI updates."""
    if not job_id or not is_cloud_enabled():
        return

    try:
        schema = get_supabase_schema_client()
        payload = {
            "leads_discovered": int(stats.get("leads_discovered", 0)),
            "leads_inserted": int(stats.get("leads_inserted", 0)),
            "leads_updated": int(stats.get("leads_updated", 0)),
            "leads_skipped_dup": int(stats.get("skipped_duplicates", 0)),
            "emails_found": int(stats.get("email_found", 0)),
            "blocked_count": int(stats.get("blocked", 0)),
            "quota_exhausted_count": int(stats.get("quota_exhausted", 0)),
        }
        schema.table("scrape_jobs").update(payload).eq("id", job_id).execute()
    except Exception as exc:
        log.warning(f"Non-fatal error updating scrape_job {job_id} progress: {exc}")


def finish_scrape_job(
    job_id: Optional[str],
    status: str,
    stats: Dict[str, int],
    error_summary: Optional[str] = None,
) -> None:
    """Finalize a `prospectiq.scrape_jobs` row (`COMPLETED`, `PARTIAL`, or `FAILED`)."""
    if not job_id or not is_cloud_enabled():
        return

    try:
        schema = get_supabase_schema_client()
        payload: Dict[str, Any] = {
            "status": status,
            "leads_discovered": int(stats.get("leads_discovered", 0)),
            "leads_inserted": int(stats.get("leads_inserted", 0)),
            "leads_updated": int(stats.get("leads_updated", 0)),
            "leads_skipped_dup": int(stats.get("skipped_duplicates", 0)),
            "emails_found": int(stats.get("email_found", 0)),
            "blocked_count": int(stats.get("blocked", 0)),
            "quota_exhausted_count": int(stats.get("quota_exhausted", 0)),
            "finished_at": _utc_now_iso(),
        }
        if error_summary:
            payload["error_summary"] = error_summary[:1000]
        schema.table("scrape_jobs").update(payload).eq("id", job_id).execute()
        log.info(f"Finalized scrape_job {job_id} with status={status}.")
    except Exception as exc:
        log.error(f"Failed to finalize scrape_job {job_id}: {exc}")


def fetch_next_targets(limit: int = 2) -> List[Dict[str, Any]]:
    """
    Fetch the next `limit` enabled rows from `prospectiq.target_queue` ordered by
    highest priority (`priority ASC`) and stalest `last_scraped_at` (`NULLS FIRST`).
    """
    if not is_cloud_enabled():
        return []

    schema = get_supabase_schema_client()
    resp = (
        schema.table("target_queue")
        .select("*")
        .eq("enabled", True)
        .order("priority", desc=False)
        .order("last_scraped_at", desc=False, nullsfirst=True)
        .limit(limit)
        .execute()
    )
    return list(resp.data or [])


def advance_target_cursor(
    target_id: str,
    leads_found: int = 0,
    page_step: int = 20,
) -> None:
    """Atomically advance `next_page_offset` and `total_leads_found` for a queue row."""
    if not target_id or not is_cloud_enabled():
        return

    schema = get_supabase_schema_client()
    schema.rpc(
        "advance_target_cursor",
        {
            "p_target_id": target_id,
            "p_leads_found": max(0, int(leads_found)),
            "p_page_step": max(0, int(page_step)),
        },
    ).execute()
    log.info(
        f"Advanced target_queue cursor {target_id}: +{page_step} offset, +{leads_found} leads."
    )


def get_dynamic_exclusions() -> Dict[str, List[str]]:
    """Load dynamic exclusion rules from `prospectiq.exclusions` when cloud mode is active."""
    grouped: Dict[str, List[str]] = {"DOMAIN": [], "FRANCHISE": [], "EMAIL_DOMAIN": []}
    if not is_cloud_enabled():
        return grouped

    try:
        schema = get_supabase_schema_client()
        resp = schema.table("exclusions").select("pattern_type, pattern_value").execute()
        for row in resp.data or []:
            p_type = str(row.get("pattern_type") or "").upper()
            p_val = str(row.get("pattern_value") or "").strip().lower()
            if p_type in grouped and p_val:
                grouped[p_type].append(p_val)
    except Exception as exc:
        log.warning(f"Could not fetch dynamic exclusions from Supabase: {exc}")
    return grouped


# Auto-initialize local SQLite schema on module load ONLY when running locally
if not is_cloud_enabled():
    try:
        init_db()
    except sqlite3.OperationalError:
        # Defer write failure until an actual DB call (e.g. read-only test sandbox)
        pass
