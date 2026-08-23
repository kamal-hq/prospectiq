"""
Storage Layer — database.py

SQLite persistence layer for the Lead Generation & Web Presence Validation Engine.
This module is the single persistence layer and the ONLY place in the system
authorized to execute SQLite read and write operations. No other module should
connect directly to the database or execute SQL statements.
"""

import sqlite3
import urllib.parse
from typing import List, Optional

from logger import setup_logger
from models import BusinessLead

# Read DB_PATH from config.py with graceful fallback
try:
    from config import DB_PATH
except (ImportError, AttributeError):
    DB_PATH = "leads.db"

log = setup_logger("database")


def _extract_root_domain(url: Optional[str]) -> Optional[str]:
    """
    Extract normalized root domain (e.g. 'reliantplumbing.com') from a URL.

    Args:
        url: Raw website URL.

    Returns:
        Optional[str]: Cleaned domain string, or None if URL is invalid/empty.
    """
    if not url or not str(url).strip():
        return None
    try:
        raw_url = str(url).strip()
        if not raw_url.startswith("http://") and not raw_url.startswith("https://"):
            raw_url = "https://" + raw_url
        parsed = urllib.parse.urlparse(raw_url)
        netloc = parsed.netloc or parsed.path
        netloc = netloc.split(":")[0].strip().lower()
        if netloc.startswith("www."):
            netloc = netloc[4:]
        return netloc if netloc else None
    except Exception:
        return None


def get_connection(db_path: str = DB_PATH) -> sqlite3.Connection:
    """
    Creates and returns a SQLite connection configured with sqlite3.Row row_factory.
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: str = DB_PATH) -> None:
    """
    Initializes the SQLite database and creates the leads table if it does not exist,
    enforcing the schema and UNIQUE(business_name, city) constraint defined in Section 7
    of ARCHITECTURE.md.
    """
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS leads (
                id                INTEGER PRIMARY KEY AUTOINCREMENT,
                business_name     TEXT NOT NULL,
                city              TEXT NOT NULL,
                industry          TEXT NOT NULL,
                timestamp         TEXT NOT NULL,
                website_found     INTEGER NOT NULL,         -- 0 or 1
                website_url       TEXT,
                http_status       TEXT,
                email             TEXT,
                email_status      TEXT NOT NULL DEFAULT 'NOT_ATTEMPTED',
                linkedin          TEXT,
                instagram         TEXT,
                facebook          TEXT,
                twitter           TEXT,
                social_status     TEXT NOT NULL DEFAULT 'NOT_ATTEMPTED',
                UNIQUE(business_name, city)                 -- deduplication constraint
            );
            """
        )
        conn.commit()


def upsert_lead(lead: BusinessLead, db_path: str = DB_PATH) -> bool:
    """
    Inserts a validated BusinessLead into the database using INSERT OR IGNORE.
    Performs a domain-level duplicate check before inserting to skip leads
    with already-recorded root domains.
    Ensures all status fields (email_status, social_status, http_status) are written.
    Returns True if a new row was inserted, or False if ignored due to uniqueness constraint
    or domain duplication.
    """
    init_db(db_path)
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()

        # Domain-level duplicate check
        domain = _extract_root_domain(lead.website_url)
        if domain:
            cursor.execute(
                """
                SELECT 1 FROM leads WHERE 
                    website_url LIKE '%://' || ? || '/%'
                    OR website_url LIKE '%://' || ? || '?%'
                    OR website_url LIKE '%://' || ?
                    OR website_url LIKE '%://www.' || ? || '/%'
                    OR website_url LIKE '%://www.' || ? || '?%'
                    OR website_url LIKE '%://www.' || ?
                LIMIT 1
                """,
                (domain, domain, domain, domain, domain, domain),
            )
            if cursor.fetchone() is not None:
                log.info("Domain duplicate detected.")
                return False

        cursor.execute(
            """
            INSERT OR IGNORE INTO leads (
                business_name,
                city,
                industry,
                timestamp,
                website_found,
                website_url,
                http_status,
                email,
                email_status,
                linkedin,
                instagram,
                facebook,
                twitter,
                social_status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                lead.business_name,
                lead.city,
                lead.industry,
                lead.timestamp,
                1 if lead.website_found else 0,
                lead.website_url,
                lead.http_status,
                lead.email,
                lead.email_status,
                lead.linkedin,
                lead.instagram,
                lead.facebook,
                lead.twitter,
                lead.social_status,
            ),
        )
        conn.commit()
        return cursor.rowcount > 0


def is_duplicate(business_name: str, city: str, db_path: str = DB_PATH) -> bool:
    """
    Queries the database to check if a business lead with the exact business_name
    and city combination already exists. Replaces in-memory set deduplication.
    """
    init_db(db_path)
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT 1 FROM leads WHERE business_name = ? AND city = ? LIMIT 1",
            (business_name, city),
        )
        return cursor.fetchone() is not None


def get_all_leads(db_path: str = DB_PATH) -> List[BusinessLead]:
    """
    Retrieves all records from the leads table as validated BusinessLead model instances.
    """
    init_db(db_path)
    leads: List[BusinessLead] = []
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM leads ORDER BY id ASC")
        for row in cursor.fetchall():
            leads.append(
                BusinessLead(
                    business_name=row["business_name"],
                    city=row["city"],
                    industry=row["industry"],
                    timestamp=row["timestamp"],
                    website_found=bool(row["website_found"]),
                    website_url=row["website_url"],
                    http_status=row["http_status"],
                    email=row["email"],
                    email_status=row["email_status"],
                    linkedin=row["linkedin"],
                    instagram=row["instagram"],
                    facebook=row["facebook"],
                    twitter=row["twitter"],
                    social_status=row["social_status"],
                )
            )
    return leads


def get_leads_by_status(
    website_found: Optional[bool] = None,
    email_status: Optional[str] = None,
    social_status: Optional[str] = None,
    db_path: str = DB_PATH,
) -> List[BusinessLead]:
    """
    Retrieves leads filtered by website_found status, email_status, or social_status
    as validated BusinessLead model instances.
    """
    init_db(db_path)
    conditions = []
    params = []

    if website_found is not None:
        conditions.append("website_found = ?")
        params.append(1 if website_found else 0)

    if email_status is not None:
        conditions.append("email_status = ?")
        params.append(email_status)

    if social_status is not None:
        conditions.append("social_status = ?")
        params.append(social_status)

    query = "SELECT * FROM leads"
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY id ASC"

    leads: List[BusinessLead] = []
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(query, tuple(params))
        for row in cursor.fetchall():
            leads.append(
                BusinessLead(
                    business_name=row["business_name"],
                    city=row["city"],
                    industry=row["industry"],
                    timestamp=row["timestamp"],
                    website_found=bool(row["website_found"]),
                    website_url=row["website_url"],
                    http_status=row["http_status"],
                    email=row["email"],
                    email_status=row["email_status"],
                    linkedin=row["linkedin"],
                    instagram=row["instagram"],
                    facebook=row["facebook"],
                    twitter=row["twitter"],
                    social_status=row["social_status"],
                )
            )
    return leads


# Auto-initialize database table on module load
init_db()
