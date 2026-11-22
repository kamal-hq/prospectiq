"""
Agency Intelligence Layer — scorer.py

Pure deterministic lead scoring and pitch classification engine.
Computes a transparent 0-100 Opportunity Score, Pitch Tier (HOT/WARM/COLD),
Pitch Angle, and bespoke agency Pitch Summary based on verified discovery,
Digital Health Audit, and contact enrichment signals.
Contains NO network I/O and NO database I/O.
"""

from typing import Optional

from engine.models import (
    ContactEnrichment,
    LeadScore,
    PitchAngle,
    PitchTier,
    RawCandidate,
    SiteAudit,
)

# Builders commonly associated with DIY / redesign-ready SMB sites
REDESIGN_CMS_PLATFORMS = {"Wix", "GoDaddy", "Weebly"}


def _has_any_social(contacts: ContactEnrichment) -> bool:
    return any(
        [
            contacts.facebook,
            contacts.instagram,
            contacts.linkedin,
            contacts.twitter,
        ]
    )


def _determine_pitch_angle(audit: SiteAudit, contacts: ContactEnrichment) -> PitchAngle:
    """
    Classify the single highest-ROI agency pitch angle for this business.
    """
    has_social = _has_any_social(contacts)

    # 1. No owned functioning website
    if audit.website_status in ("NO_WEBSITE", "BROKEN", "PARKED"):
        return "SOCIAL_ONLY" if has_social else "NO_WEBSITE"

    # 2. Live site with clear technical / design / SSL weaknesses
    if audit.website_status == "LIVE":
        needs_ssl = audit.has_ssl is False
        not_mobile = audit.is_mobile_friendly is False
        slow_site = audit.load_time_ms is not None and audit.load_time_ms >= 4000
        diy_cms = audit.cms_platform in REDESIGN_CMS_PLATFORMS
        if needs_ssl or not_mobile or slow_site or diy_cms:
            return "REDESIGN_SSL"

        if audit.has_analytics is False and audit.has_meta_pixel is False:
            return "SEO_ANALYTICS"

        return "ESTABLISHED"

    # 3. WAF_PROTECTED (live site behind Cloudflare/Akamai)
    return "SEO_ANALYTICS" if audit.has_ssl is False else "ESTABLISHED"


def _build_pitch_summary(
    candidate: RawCandidate,
    audit: SiteAudit,
    contacts: ContactEnrichment,
    pitch_angle: PitchAngle,
) -> str:
    """
    Generate a concise, factual agency outreach brief grounded in real signals.
    """
    rep_part = ""
    if candidate.rating is not None and candidate.reviews_count > 0:
        rep_part = f"Rated {candidate.rating:.1f} stars across {candidate.reviews_count} Google reviews"
    elif candidate.rating is not None:
        rep_part = f"Rated {candidate.rating:.1f} stars on Google"
    else:
        rep_part = f"Active {candidate.industry.lower()} business in {candidate.city}"

    if candidate.is_franchise:
        return (
            f"{rep_part}, flagged as a multi-location franchise/chain. "
            "Low local decision-maker accessibility; deprioritize for boutique agency outreach."
        )

    if pitch_angle == "NO_WEBSITE":
        reason = (
            "listed website is broken or parked"
            if audit.website_status in ("BROKEN", "PARKED")
            else "no owned website detected"
        )
        return (
            f"{rep_part} with {reason}. Prime pitch: launch a high-converting local "
            f"{candidate.industry.lower()} website + Google Business optimization to capture missed search demand."
        )

    if pitch_angle == "SOCIAL_ONLY":
        channels = [
            name
            for name, val in (
                ("Facebook", contacts.facebook),
                ("Instagram", contacts.instagram),
                ("LinkedIn", contacts.linkedin),
            )
            if val
        ]
        channel_str = "/".join(channels) if channels else "social media"
        return (
            f"{rep_part}, relying strictly on {channel_str} without an owned website. "
            "Prime pitch: convert existing social trust into a fast, SEO-ready booking website."
        )

    if pitch_angle == "REDESIGN_SSL":
        gaps = []
        if audit.has_ssl is False:
            gaps.append("no HTTPS/SSL")
        if audit.is_mobile_friendly is False:
            gaps.append("not mobile-optimized")
        if audit.cms_platform in REDESIGN_CMS_PLATFORMS:
            gaps.append(f"DIY {audit.cms_platform} build")
        if audit.load_time_ms is not None and audit.load_time_ms >= 4000:
            gaps.append(f"slow load ({audit.load_time_ms}ms)")
        gap_text = ", ".join(gaps) if gaps else "outdated site fundamentals"
        return (
            f"{rep_part} with clear website friction ({gap_text}). "
            "Pitch a modern speed/SSL redesign to lift quote conversions from existing local traffic."
        )

    if pitch_angle == "SEO_ANALYTICS":
        return (
            f"{rep_part} with a live site missing Google Analytics and Meta Pixel tracking. "
            "Pitch conversion tracking, local SEO, and retargeting campaigns to turn traffic into measurable leads."
        )

    return (
        f"{rep_part} with an established, SSL-secured website"
        f"{f' on {audit.cms_platform}' if audit.cms_platform else ''}. "
        "Best approached with specialized paid-ads, CRO, or reputation-growth retainers."
    )


def score_lead(
    candidate: RawCandidate,
    audit: SiteAudit,
    contacts: ContactEnrichment,
) -> LeadScore:
    """
    Calculate deterministic 0-100 Opportunity Score matching the transparent
    ProspectIQ Agency Formula:
      - No owned website (NO_WEBSITE / BROKEN / PARKED):      +35 pts
      - Redesign / Technical friction (LIVE no-SSL/DIY/slow): +20 pts
      - High Google reviews & rating:                         up to +20 pts
      - Phone / MX-verified email readiness:                  up to +20 pts
      - Missing SSL / Analytics / Tracking gap:               up to +15 pts
      - Social audience detected:                             +10 pts
      - Franchise / national chain penalty:                   -40 pts
    """
    score = 0
    pitch_angle = _determine_pitch_angle(audit, contacts)
    has_social = _has_any_social(contacts)

    # 1. Core Web Presence Opportunity (max +35)
    if audit.website_status in ("NO_WEBSITE", "BROKEN", "PARKED"):
        score += 35
    elif pitch_angle == "REDESIGN_SSL":
        score += 20
    elif audit.website_status == "LIVE":
        score += 10
    elif audit.website_status == "WAF_PROTECTED":
        score += 10

    # 2. Local Reputation & Demand Proof (max +20)
    rating = candidate.rating or 0.0
    reviews = candidate.reviews_count or 0
    if rating >= 4.5 and reviews >= 50:
        score += 20
    elif rating >= 4.2 and reviews >= 20:
        score += 15
    elif rating >= 4.0 and reviews >= 5:
        score += 10
    elif reviews > 0:
        score += 5

    # 3. Direct Contact Readiness (max +20)
    has_phone = bool(candidate.phone or contacts.extracted_phone)
    has_verified_email = bool(contacts.email and contacts.email_mx_valid is not False)
    if has_phone and has_verified_email:
        score += 20
    elif has_phone or has_verified_email:
        score += 15
    elif contacts.email:
        score += 8

    # 4. Missing SSL / Mobile / Analytics / Digital Gap (max +15)
    if audit.website_status in ("NO_WEBSITE", "BROKEN", "PARKED"):
        # No site implies zero SSL / zero analytics capture
        score += 15
    elif audit.website_status == "LIVE":
        tech_gap = 0
        if audit.has_ssl is False:
            tech_gap += 8
        if audit.is_mobile_friendly is False:
            tech_gap += 5
        if audit.has_analytics is False and audit.has_meta_pixel is False:
            tech_gap += 7
        elif audit.has_analytics is False or audit.has_meta_pixel is False:
            tech_gap += 3
        score += min(tech_gap, 15)

    # 5. Active Social Footprint Signal (+10)
    if has_social:
        score += 10

    # 6. Franchise / Enterprise Penalty (-40)
    if candidate.is_franchise:
        score -= 40

    # Clamp strictly to [0, 100]
    score = max(0, min(100, int(score)))

    pitch_tier: PitchTier
    if score >= 80:
        pitch_tier = "HOT"
    elif score >= 50:
        pitch_tier = "WARM"
    else:
        pitch_tier = "COLD"

    pitch_summary = _build_pitch_summary(candidate, audit, contacts, pitch_angle)

    return LeadScore(
        opportunity_score=score,
        pitch_tier=pitch_tier,
        pitch_angle=pitch_angle,
        pitch_summary=pitch_summary,
    )
