"""
Data Contract — models.py

Defines the Pydantic v2 BusinessLead model and status definitions for all lead data
flowing across discovery, validation, extraction, and database persistence layers.
"""

from typing import Literal, Optional
from pydantic import BaseModel, ConfigDict

# Allowed status values across extraction stages
ExtractionStatus = Literal[
    "FOUND_API",
    "FOUND_SCRAPE",
    "FOUND_ON_SITE",
    "FOUND_DDG",
    "NOT_FOUND",
    "BLOCKED",
    "QUOTA_EXHAUSTED",
    "NOT_ATTEMPTED",
]


class BusinessLead(BaseModel):
    """
    Data contract representing a single business prospect throughout the pipeline.
    Enforces strict typing and explicit status tracking for all extracted fields.
    """

    model_config = ConfigDict(strict=True)

    # Core identity (required, non-nullable)
    business_name: str
    city: str
    industry: str
    timestamp: str

    # Web presence (from validator.py)
    website_found: bool
    website_url: Optional[str] = None
    http_status: Optional[str] = None  # "200", "404", "TIMEOUT", "CONN_ERROR", "NO_URL"

    # Email extraction (from extractor.py)
    email: Optional[str] = None
    email_status: ExtractionStatus = "NOT_ATTEMPTED"

    # Social media (from extractor.py)
    linkedin: Optional[str] = None
    instagram: Optional[str] = None
    facebook: Optional[str] = None
    twitter: Optional[str] = None
    social_status: ExtractionStatus = "NOT_ATTEMPTED"
