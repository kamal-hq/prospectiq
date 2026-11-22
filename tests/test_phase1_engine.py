"""
Phase 1 Unit & Regression Test Suite — tests/test_phase1_engine.py

Verifies every single "Garbage In, Garbage Out" fix and security rule offline
with zero live API credits spent:
1. Secret redaction in logger.py (no plaintext api_key in logs)
2. Social-as-Website splitting (m.facebook.com -> facebook social + NO_WEBSITE)
3. Aggregator filtering, closed business rejection, franchise flagging, UTM stripping
4. 5-state validation (403 -> WAF_PROTECTED, parked page -> PARKED, live HTML audit)
5. Free-First email waterfall (JSON-LD & Homepage scraped BEFORE Hunter.io; agency email rejected)
6. Opportunity Scorer (0-100 Hot/Warm/Cold + Franchise -40 penalty)
7. Pre-scrape domain/place_id dedup + True SQLite UPSERT preserving CRM notes
"""

import os
import sqlite3
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from engine import database, discovery, extractor, scorer, validator
from engine import logger as app_logger
from engine.models import BusinessLead, ContactEnrichment, RawCandidate, SiteAudit


class TestSecretRedaction(unittest.TestCase):
    def test_redact_url_masks_api_keys(self):
        raw = "https://api.hunter.io/v2/domain-search?domain=acme.com&api_key=SUPER_SECRET_12345"
        redacted = app_logger.redact_url(raw)
        self.assertNotIn("SUPER_SECRET_12345", redacted)
        self.assertIn("api_key=[REDACTED]", redacted)
        self.assertIn("domain=acme.com", redacted)

    def test_redact_secrets_masks_bearer_and_query(self):
        msg = "GET https://serpapi.com/search.json?q=plumber&api_key=abc999xyz Authorization: Bearer tok_secret_987654"
        cleaned = app_logger.redact_secrets(msg)
        self.assertNotIn("abc999xyz", cleaned)
        self.assertNotIn("tok_secret_987654", cleaned)


class TestDiscoveryAntiGarbage(unittest.TestCase):
    def test_social_as_website_splits_facebook_to_socials(self):
        url, socials, is_agg = discovery.classify_candidate_url(
            "https://m.facebook.com/plumb.masters/?_rdr&utm_source=gmb"
        )
        self.assertIsNone(url)
        self.assertFalse(is_agg)
        self.assertEqual(socials.get("facebook"), "https://facebook.com/plumb.masters")

    def test_aggregator_url_detected(self):
        url, socials, is_agg = discovery.classify_candidate_url(
            "https://www.yelp.com/biz/bobs-plumbing-houston"
        )
        self.assertIsNone(url)
        self.assertEqual(socials, {})
        self.assertTrue(is_agg)

    def test_canonicalize_strips_utm_junk(self):
        cleaned = discovery.canonicalize_url(
            "https://www.abacusplumbing.net/?utm_source=google&utm_medium=gmb&utm_campaign=houston"
        )
        self.assertEqual(cleaned, "https://www.abacusplumbing.net/")

    def test_franchise_flagging(self):
        self.assertTrue(discovery._is_franchise("Service Experts Heating & Air", "serviceexperts.com"))
        self.assertFalse(discovery._is_franchise("Bayou City Rooter", "bayoucityrooter.com"))

    def test_closed_permanently_detected(self):
        self.assertEqual(
            discovery._extract_business_status({"open_state": "Permanently closed"}),
            "CLOSED_PERMANENTLY",
        )
        self.assertEqual(
            discovery._extract_business_status({"open_state": "Open 24 hours"}),
            "OPERATIONAL",
        )


class TestValidatorFiveStates(unittest.TestCase):
    def test_http_403_classified_as_waf_protected_not_dead(self):
        fake_resp = MagicMock()
        fake_resp.status_code = 403
        fake_resp.url = "https://www.serviceexperts.com/dallas-tx/"
        fake_resp.headers = {"server": "cloudflare"}
        fake_resp.text = "Attention Required! | Cloudflare"

        with patch("engine.validator.stealth.get", return_value=fake_resp):
            audit = validator.validate_url("https://www.serviceexperts.com/dallas-tx/?utm_source=gmb")

        self.assertTrue(audit.website_found)
        self.assertEqual(audit.website_status, "WAF_PROTECTED")
        self.assertEqual(audit.http_status, "403")
        self.assertEqual(audit.website_url, "https://www.serviceexperts.com/dallas-tx/")

    def test_parked_domain_classified_as_parked(self):
        html = "<html><head><title>Domain For Sale</title></head><body>This domain is for sale via SedoParking</body></html>"
        audit = validator.audit_html(html, "https://oldplumber.com/", "200", load_time_ms=220)
        self.assertFalse(audit.website_found)
        self.assertEqual(audit.website_status, "PARKED")

    def test_live_html_digital_audit(self):
        html = """
        <html>
          <head>
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <meta name="generator" content="WordPress 6.5">
            <script src="https://www.googletagmanager.com/gtag/js?id=G-ABC12345"></script>
          </head>
          <body><h1>Houston Plumbing Pros</h1></body>
        </html>
        """
        audit = validator.audit_html(html, "https://houstonplumbingpros.com/", "200", load_time_ms=410)
        self.assertTrue(audit.website_found)
        self.assertEqual(audit.website_status, "LIVE")
        self.assertTrue(audit.has_ssl)
        self.assertTrue(audit.is_mobile_friendly)
        self.assertEqual(audit.cms_platform, "WordPress")
        self.assertTrue(audit.has_analytics)
        self.assertFalse(audit.has_meta_pixel)
        self.assertEqual(audit.html_body, html)
        # Ensure html_body is excluded from serialized payload
        self.assertNotIn("html_body", audit.model_dump())


class TestExtractorFreeFirstAndHygiene(unittest.TestCase):
    def test_free_jsonld_runs_before_hunter_and_skips_hunter_credit(self):
        html = """
        <html>
          <head>
            <script type="application/ld+json">
            {
              "@type": "LocalBusiness",
              "name": "Apex Plumbing",
              "email": "mailto:info@apexplumbing.com",
              "telephone": "(713) 555-0100",
              "sameAs": ["https://www.instagram.com/apexplumbingtx"]
            }
            </script>
          </head>
          <body>
            <footer>Website designed by <a href="mailto:dev@randomwebagency.com">Cool Agency</a></footer>
          </body>
        </html>
        """
        audit = SiteAudit(
            website_found=True,
            website_status="LIVE",
            website_url="https://apexplumbing.com/",
            root_domain="apexplumbing.com",
            http_status="200",
            has_ssl=True,
            html_body=html,
        )

        with patch("engine.extractor._query_hunter_api") as mock_hunter, \
             patch("engine.extractor.verify_email_mx", return_value=True):
            result = extractor.extract_contacts(audit, business_name="Apex Plumbing", city="Houston, TX")

        mock_hunter.assert_not_called()
        self.assertEqual(result.email, "info@apexplumbing.com")
        self.assertEqual(result.email_status, "FOUND_JSONLD")
        self.assertTrue(result.email_mx_valid)
        self.assertEqual(result.instagram, "https://instagram.com/apexplumbingtx")
        self.assertEqual(result.social_status, "FOUND_ON_SITE")

    def test_rejects_noreply_and_unrelated_agency_emails(self):
        ranked = extractor._rank_emails(
            [
                "noreply@bobsroofing.com",
                "dev@someotherwebagency.io",
                "quotes@bobsroofing.com",
                "bobsroofingtx@gmail.com",
            ],
            site_domain="bobsroofing.com",
            business_name="Bob's Roofing LLC",
        )
        self.assertEqual(ranked, ["quotes@bobsroofing.com", "bobsroofingtx@gmail.com"])

    def test_social_only_lead_never_calls_hunter(self):
        audit = SiteAudit(website_found=False, website_status="NO_WEBSITE", http_status="NO_URL")
        with patch("engine.extractor._query_hunter_api") as mock_hunter:
            result = extractor.extract_contacts(
                audit,
                business_name="Plumb Masters",
                city="Austin, TX",
                prefilled_socials={"facebook": "https://facebook.com/plumb.masters"},
            )
        mock_hunter.assert_not_called()
        self.assertEqual(result.email_status, "NOT_ATTEMPTED")
        self.assertEqual(result.facebook, "https://facebook.com/plumb.masters")
        self.assertEqual(result.social_status, "FOUND_MAPS")

    def test_blacklisted_domain_never_calls_hunter_or_burns_quota(self):
        with patch("engine.extractor.HUNTER_API_KEY", "test_key_should_not_be_used"), \
             patch("engine.extractor.tracker.check_and_increment") as mock_quota, \
             patch("engine.extractor.stealth.get") as mock_get:
            emails, override = extractor._query_hunter_api("example.com", "Apex Plumbing", session=MagicMock())
        self.assertEqual(emails, [])
        self.assertIsNone(override)
        mock_quota.assert_not_called()
        mock_get.assert_not_called()


class TestScorerAndDatabaseUpsert(unittest.TestCase):
    def test_hot_social_only_lead_scores_high_and_franchise_penalized(self):
        hot_candidate = RawCandidate(
            business_name="Bayou City Rooter",
            city="Houston, TX",
            industry="Plumbing",
            phone="(713) 555-0184",
            rating=4.9,
            reviews_count=214,
            is_franchise=False,
        )
        no_site_audit = SiteAudit(website_found=False, website_status="NO_WEBSITE", http_status="NO_URL")
        social_contacts = ContactEnrichment(facebook="https://facebook.com/bayourooter", social_status="FOUND_MAPS")

        hot_score = scorer.score_lead(hot_candidate, no_site_audit, social_contacts)
        self.assertGreaterEqual(hot_score.opportunity_score, 85)
        self.assertEqual(hot_score.pitch_tier, "HOT")
        self.assertEqual(hot_score.pitch_angle, "SOCIAL_ONLY")

        franchise_candidate = hot_candidate.model_copy(
            update={"business_name": "Service Experts", "is_franchise": True}
        )
        franchise_score = scorer.score_lead(franchise_candidate, no_site_audit, social_contacts)
        self.assertLess(franchise_score.opportunity_score, 60)

    def test_pre_scrape_domain_dedup_and_true_upsert_preserves_notes(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test_leads.db")
            database.init_db(db_path)

            lead_v1 = BusinessLead(
                place_id="place_abc",
                business_name="Reliant Plumbing",
                city="Austin, TX",
                industry="Plumbing",
                phone="(512) 555-0100",
                rating=4.8,
                reviews_count=120,
                timestamp="2026-11-22T00:00:00+00:00",
                website_found=True,
                website_status="LIVE",
                website_url="https://reliantplumbing.com/",
                root_domain="reliantplumbing.com",
                http_status="200",
                email=None,
                email_status="NOT_FOUND",
                opportunity_score=72,
                pitch_tier="WARM",
                pitch_angle="SEO_ANALYTICS",
                outreach_status="CONTACTED",
                outreach_notes="Left voicemail with owner",
            )
            self.assertTrue(database.upsert_lead(lead_v1, db_path=db_path))

            # Pre-scrape domain dedup catches differently named GBP sharing same domain!
            self.assertTrue(
                database.is_duplicate(
                    business_name="Reliant Plumbing South Austin",
                    city="Austin, TX",
                    website_url="https://www.reliantplumbing.com/south-austin/?utm_source=gmb",
                    db_path=db_path,
                )
            )
            # Pre-scrape place_id dedup catches exact place_id
            self.assertTrue(
                database.is_duplicate(
                    business_name="Different Name",
                    city="Austin, TX",
                    place_id="place_abc",
                    db_path=db_path,
                )
            )

            # Re-enrichment UPSERT fills email while preserving outreach_status & outreach_notes
            lead_v2 = lead_v1.model_copy(
                update={
                    "email": "owner@reliantplumbing.com",
                    "email_status": "FOUND_SCRAPE",
                    "email_mx_valid": True,
                    "outreach_status": "NEW",
                    "outreach_notes": "",
                }
            )
            self.assertTrue(database.upsert_lead(lead_v2, db_path=db_path))

            stored = database.get_all_leads(db_path=db_path)
            self.assertEqual(len(stored), 1)
            self.assertEqual(stored[0].email, "owner@reliantplumbing.com")
            self.assertEqual(stored[0].email_status, "FOUND_SCRAPE")
            self.assertEqual(stored[0].outreach_status, "CONTACTED")
            self.assertEqual(stored[0].outreach_notes, "Left voicemail with owner")


if __name__ == "__main__":
    unittest.main(verbosity=2)
