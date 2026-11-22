"""
Data Contract — models.py

Defines strict Pydantic v2 models and status enums for all lead data flowing across
discovery, validation, extraction, scoring, and database persistence layers.
"""

from typing import Dict, List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field

# ── Status & Classification Enums ───────────────────────────────────────────
WebsiteStatus = Literal[
    "LIVE",
    "WAF_PROTECTED",
    "PARKED",
    "BROKEN",
    "NO_WEBSITE",
]

EmailStatus = Literal[
    "FOUND_JSONLD",
    "FOUND_SCRAPE",
    "FOUND_API",
    "NOT_FOUND",
    "BLOCKED",
    "QUOTA_EXHAUSTED",
    "NOT_ATTEMPTED",
]

SocialStatus = Literal[
    "FOUND_MAPS",
    "FOUND_ON_SITE",
    "FOUND_DDG",
    "NOT_FOUND",
    "BLOCKED",
    "NOT_ATTEMPTED",
]

# Legacy combined alias preserved for backwards compatibility
ExtractionStatus = Literal[
    "FOUND_JSONLD",
    "FOUND_API",
    "FOUND_SCRAPE",
    "FOUND_MAPS",
    "FOUND_ON_SITE",
    "FOUND_DDG",
    "NOT_FOUND",
    "BLOCKED",
    "QUOTA_EXHAUSTED",
    "NOT_ATTEMPTED",
]

PitchTier = Literal["HOT", "WARM", "COLD"]

PitchAngle = Literal[
    "NO_WEBSITE",
    "SOCIAL_ONLY",
    "REDESIGN_SSL",
    "SEO_ANALYTICS",
    "ESTABLISHED",
]

OutreachStatus = Literal[
    "NEW",
    "CONTACTED",
    "FOLLOW_UP",
    "REPLIED",
    "QUALIFIED",
    "WON",
    "DISQUALIFIED",
]


class RawCandidate(BaseModel):
    """
    Structured output contract from discovery.py representing a single
    pre-validated business candidate discovered via SerpApi, Brave, or mock mode.
    """

    model_config = ConfigDict(strict=True)

    place_id: Optional[str] = None
    business_name: str
    city: str
    industry: str
    phone: Optional[str] = None
    address: Optional[str] = None
    rating: Optional[float] = None
    reviews_count: int = 0
    business_status: str = "OPERATIONAL"
    is_franchise: bool = False
    website_url: Optional[str] = None
    prefilled_socials: Dict[str, Optional[str]] = Field(default_factory=dict)


class SiteAudit(BaseModel):
    """
    Structured output contract from validator.py containing accurate 5-state
    reachability classification and lightweight Digital Health Audit signals.
    `html_body` is excluded from serialization so extractor.py reuses the already
    fetched homepage HTML without double-fetching or bloating persistence.
    """

    model_config = ConfigDict(strict=True)

    website_found: bool
    website_status: WebsiteStatus
    website_url: Optional[str] = None
    root_domain: Optional[str] = None
    http_status: Optional[str] = None
    has_ssl: Optional[bool] = None
    is_mobile_friendly: Optional[bool] = None
    cms_platform: Optional[str] = None
    has_analytics: Optional[bool] = None
    has_meta_pixel: Optional[bool] = None
    load_time_ms: Optional[int] = None
    html_body: Optional[str] = Field(default=None, exclude=True)


class ContactEnrichment(BaseModel):
    """
    Structured output contract from extractor.py containing verified contact data
    and explicit extraction status enums.
    """

    model_config = ConfigDict(strict=True)

    email: Optional[str] = None
    email_status: EmailStatus = "NOT_ATTEMPTED"
    email_mx_valid: Optional[bool] = None
    secondary_emails: List[str] = Field(default_factory=list)
    linkedin: Optional[str] = None
    instagram: Optional[str] = None
    facebook: Optional[str] = None
    twitter: Optional[str] = None
    social_status: SocialStatus = "NOT_ATTEMPTED"
    extracted_phone: Optional[str] = None


class LeadScore(BaseModel):
    """
    Structured output contract from scorer.py representing agency fit & pitch strategy.
    """

    model_config = ConfigDict(strict=True)

    opportunity_score: int = Field(ge=0, le=100)
    pitch_tier: PitchTier
    pitch_angle: PitchAngle
    pitch_summary: str


class BusinessLead(BaseModel):
    """
    Master Pydantic v2 data contract representing a fully validated, audited,
    enriched, and scored agency prospect ready for database persistence.
    Mirrors the `prospectiq.leads` PostgreSQL schema and frontend `BusinessLead` type.
    """

    model_config = ConfigDict(strict=True)

    # Core identity (from discovery.py)
    place_id: Optional[str] = None
    business_name: str
    city: str
    industry: str
    phone: Optional[str] = None
    address: Optional[str] = None
    rating: Optional[float] = None
    reviews_count: int = 0
    business_status: str = "OPERATIONAL"
    is_franchise: bool = False
    timestamp: str

    # Web presence & Digital Health Audit (from validator.py)
    website_found: bool
    website_status: WebsiteStatus = "NO_WEBSITE"
    website_url: Optional[str] = None
    root_domain: Optional[str] = None
    http_status: Optional[str] = None
    has_ssl: Optional[bool] = None
    is_mobile_friendly: Optional[bool] = None
    cms_platform: Optional[str] = None
    has_analytics: Optional[bool] = None
    has_meta_pixel: Optional[bool] = None
    load_time_ms: Optional[int] = None

    # Contact extraction (from extractor.py)
    email: Optional[str] = None
    email_status: EmailStatus = "NOT_ATTEMPTED"
    email_mx_valid: Optional[bool] = None
    secondary_emails: List[str] = Field(default_factory=list)
    linkedin: Optional[str] = None
    instagram: Optional[str] = None
    facebook: Optional[str] = None
    twitter: Optional[str] = None
    social_status: SocialStatus = "NOT_ATTEMPTED"

    # Agency intelligence & Mini-CRM (from scorer.py + user mutations)
    opportunity_score: int = Field(default=0, ge=0, le=100)
    pitch_tier: PitchTier = "COLD"
    pitch_angle: PitchAngle = "ESTABLISHED"
    pitch_summary: Optional[str] = None
    outreach_status: OutreachStatus = "NEW"
    outreach_notes: str = ""
