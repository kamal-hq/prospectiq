"""
Phase 2 Shared-Supabase Multi-Schema Test Suite — tests/test_phase2_cloud.py

Verifies all Phase 2 `shared-apps` multi-schema contract, publishable-key-only auth,
lazy profile provisioning, cloud persistence, quota guard, and CI automation rules
completely offline using mocked Supabase PostgREST clients:
1. Automatic SQLite / JSON fallback when Supabase publishable/owner env vars are absent
2. Publishable key (`sb_publishable_...`) client initialization + Owner JWT sign-in +
   lazy idempotent `prospectiq.profiles` upsert (ZERO `service_role`, ZERO `auth.users` triggers)
3. Strict `prospectiq` schema targeting on all Supabase table & RPC calls
4. Cloud deduplication (`place_id`, case-insensitive `(name, city)`, `root_domain`)
   and `prospectiq.upsert_lead` RPC payload formatting
5. Atomic cloud quota guard (`prospectiq.check_and_increment_quota` RPC)
   enforcing hard ceilings with QuotaExhaustedError
6. `scrape_jobs` lifecycle (`RUNNING -> COMPLETED/PARTIAL`) & `target_queue`
   cursor advancement (`+20`)
7. Safe parsing of JSON array & pipe-delimited cities without splitting `"Houston, TX"`
8. Static security audit of `supabase/prospectiq_schema.sql` & `.github/workflows/auto-scrape.yml`
   (zero `public.*` DDL, zero `cadence.*` edits, zero `auth.users` triggers, zero `service_role`
   in CI, explicit PostgREST grants, Owner-UUID RLS & RPC guards, idempotent Realtime)
"""

import os
import unittest
from unittest.mock import MagicMock, patch

from engine import config, database, tracker
from engine import main as app_main
from engine.models import BusinessLead, ContactEnrichment, LeadScore, RawCandidate, SiteAudit


class _FakeResponse:
    def __init__(self, data):
        self.data = data


class _FakeQueryBuilder:
    """Minimal fluent PostgREST query mock recording chained method calls."""

    def __init__(self, table_name: str, result_data=None):
        self.table_name = table_name
        self.calls = []
        self._result_data = result_data

    def select(self, *args, **kwargs):
        self.calls.append(("select", args, kwargs))
        return self

    def insert(self, payload):
        self.calls.append(("insert", payload))
        return self

    def upsert(self, payload, **kwargs):
        self.calls.append(("upsert", payload, kwargs))
        return self

    def update(self, payload):
        self.calls.append(("update", payload))
        return self

    def eq(self, col, val):
        self.calls.append(("eq", col, val))
        return self

    def ilike(self, col, val):
        self.calls.append(("ilike", col, val))
        return self

    def in_(self, col, vals):
        self.calls.append(("in_", col, vals))
        return self

    def order(self, col, **kwargs):
        self.calls.append(("order", col, kwargs))
        return self

    def limit(self, n):
        self.calls.append(("limit", n))
        return self

    def execute(self):
        return _FakeResponse(self._result_data)


def _patch_cloud_env():
    """Patch config with shared-apps publishable-key + Owner Auth credentials (NO service_role)."""
    return patch.multiple(
        config,
        SUPABASE_URL="https://hlxkgikqmljthjsbhzhq.supabase.co",
        SUPABASE_ANON_KEY="sb_publishable_test_key_12345",
        SUPABASE_SCHEMA="prospectiq",
        SUPABASE_OWNER_EMAIL="kamal@example.com",
        SUPABASE_OWNER_PASSWORD="test_owner_password",
    )


class TestPhase2CloudAdapter(unittest.TestCase):
    def tearDown(self):
        database.reset_supabase_client()

    def test_falls_back_to_local_when_supabase_env_absent(self):
        with patch.multiple(
            config,
            SUPABASE_URL="",
            SUPABASE_ANON_KEY="",
            SUPABASE_OWNER_EMAIL="",
            SUPABASE_OWNER_PASSWORD="",
        ):
            self.assertFalse(database.is_cloud_enabled())
            self.assertFalse(database._use_supabase())
            self.assertIsNone(
                database.create_scrape_job("CLI", ["Houston, TX"], ["Plumbing"])
            )
            self.assertEqual(database.fetch_next_targets(), [])

    def test_publishable_key_client_signs_in_and_lazily_provisions_profile(self):
        profiles_builder = _FakeQueryBuilder("profiles", [{"id": "owner-uuid-123"}])
        fake_schema = MagicMock()
        fake_schema.table.return_value = profiles_builder

        fake_session = MagicMock()
        fake_session.access_token = "jwt_owner_access_token"
        fake_user = MagicMock()
        fake_user.id = "owner-uuid-123"
        fake_user.email = "kamal@example.com"
        fake_auth_resp = MagicMock(session=fake_session, user=fake_user)

        fake_client = MagicMock()
        fake_client.auth.sign_in_with_password.return_value = fake_auth_resp
        fake_client.schema.return_value = fake_schema
        fake_create_client = MagicMock(return_value=fake_client)

        with _patch_cloud_env(), \
             patch.object(database, "_import_supabase_create_client", return_value=fake_create_client):
            schema_client = database.get_supabase_schema_client()

        self.assertIs(schema_client, fake_schema)
        fake_create_client.assert_called_once_with(
            "https://hlxkgikqmljthjsbhzhq.supabase.co",
            "sb_publishable_test_key_12345",
        )
        fake_client.auth.sign_in_with_password.assert_called_once_with(
            {"email": "kamal@example.com", "password": "test_owner_password"}
        )
        fake_client.postgrest.auth.assert_called_once_with("jwt_owner_access_token")
        fake_client.schema.assert_called_once_with("prospectiq")
        fake_schema.table.assert_called_once_with("profiles")
        # Verify lazy idempotent upsert on `id`
        self.assertEqual(profiles_builder.calls[0][0], "upsert")
        self.assertEqual(profiles_builder.calls[0][1]["id"], "owner-uuid-123")
        self.assertEqual(profiles_builder.calls[0][2], {"on_conflict": "id"})

    def test_cloud_upsert_targets_prospectiq_schema_rpc(self):
        fake_schema = MagicMock()
        fake_schema.rpc.return_value.execute.return_value = _FakeResponse("inserted")

        lead = BusinessLead(
            place_id="place_cloud_1",
            business_name="Lone Star Plumbing",
            city="Houston, TX",
            industry="Plumbing",
            phone="(713) 555-0111",
            rating=4.9,
            reviews_count=180,
            timestamp="2026-11-22T00:00:00+00:00",
            website_found=False,
            website_status="NO_WEBSITE",
            opportunity_score=90,
            pitch_tier="HOT",
            pitch_angle="NO_WEBSITE",
            pitch_summary="High-rated plumber without website.",
        )

        with _patch_cloud_env(), \
             patch.object(database, "get_supabase_schema_client", return_value=fake_schema):
            outcome = database.upsert_lead_with_status(lead, scrape_job_id="job-uuid-1")

        self.assertEqual(outcome, "inserted")
        fake_schema.rpc.assert_called_once()
        rpc_name, rpc_args = fake_schema.rpc.call_args[0]
        self.assertEqual(rpc_name, "upsert_lead")
        self.assertEqual(rpc_args["p_lead"]["business_name"], "Lone Star Plumbing")
        self.assertEqual(rpc_args["p_lead"]["scrape_job_id"], "job-uuid-1")
        self.assertEqual(rpc_args["p_lead"]["opportunity_score"], 90)

    def test_cloud_is_duplicate_checks_place_name_and_domain(self):
        builders = [
            _FakeQueryBuilder("leads", []),
            _FakeQueryBuilder("leads", []),
            _FakeQueryBuilder("leads", [{"id": "existing-uuid"}]),
        ]
        fake_schema = MagicMock()
        fake_schema.table.side_effect = builders

        with _patch_cloud_env(), \
             patch.object(database, "get_supabase_schema_client", return_value=fake_schema):
            dup = database.is_duplicate(
                business_name="Reliant Plumbing South",
                city="Austin, TX",
                place_id="place_new",
                website_url="https://www.reliantplumbing.com/south/?utm_source=gmb",
            )

        self.assertTrue(dup)
        self.assertEqual(fake_schema.table.call_count, 3)
        self.assertIn(("eq", "root_domain", "reliantplumbing.com"), builders[2].calls)

    def test_cloud_quota_guard_increments_and_blocks_at_ceiling(self):
        fake_schema = MagicMock()
        fake_schema.rpc.return_value.execute.side_effect = [
            _FakeResponse([{"allowed": True, "calls_used": 12, "monthly_limit": 250}]),
            _FakeResponse([{"allowed": False, "calls_used": 50, "monthly_limit": 50}]),
        ]

        with _patch_cloud_env(), \
             patch.object(database, "get_supabase_schema_client", return_value=fake_schema):
            new_count = tracker.check_and_increment("serpapi", 250)
            self.assertEqual(new_count, 12)

            with self.assertRaises(tracker.QuotaExhaustedError) as ctx:
                tracker.check_and_increment("hunter", 50)
            self.assertEqual(ctx.exception.current_count, 50)

    def test_cloud_scrape_job_and_target_cursor_helpers(self):
        insert_builder = _FakeQueryBuilder("scrape_jobs", [{"id": "job-123"}])
        update_builder = _FakeQueryBuilder("scrape_jobs", [{"id": "job-123"}])
        finish_builder = _FakeQueryBuilder("scrape_jobs", [{"id": "job-123"}])
        queue_builder = _FakeQueryBuilder(
            "target_queue",
            [{"id": "tq-1", "city": "Houston, TX", "industry": "Plumbing", "next_page_offset": 20, "max_results_per_run": 10}],
        )

        fake_schema = MagicMock()
        fake_schema.table.side_effect = [insert_builder, update_builder, finish_builder, queue_builder]
        fake_schema.rpc.return_value.execute.return_value = _FakeResponse(None)

        with _patch_cloud_env(), \
             patch.object(database, "get_supabase_schema_client", return_value=fake_schema):
            job_id = database.create_scrape_job("CRON", ["Houston, TX"], ["Plumbing"], github_run_url="https://github.com/run/1")
            self.assertEqual(job_id, "job-123")

            stats = {"leads_discovered": 5, "leads_inserted": 3, "leads_updated": 1, "skipped_duplicates": 1, "email_found": 2, "blocked": 0, "quota_exhausted": 0}
            database.update_scrape_job_progress(job_id, stats)
            database.finish_scrape_job(job_id, "COMPLETED", stats)

            targets = database.fetch_next_targets(limit=2)
            self.assertEqual(len(targets), 1)
            self.assertEqual(targets[0]["next_page_offset"], 20)
            order_calls = [c for c in queue_builder.calls if c[0] == "order"]
            self.assertEqual(order_calls[0][1], "last_scraped_at")
            self.assertEqual(order_calls[1][1], "priority")

            database.advance_target_cursor("tq-1", leads_found=10, page_step=20)
            fake_schema.rpc.assert_called_once_with(
                "advance_target_cursor",
                {"p_target_id": "tq-1", "p_leads_found": 10, "p_page_step": 20},
            )


class TestMainOrchestrationAndSchemaAudit(unittest.TestCase):
    def test_parse_multi_value_arg_preserves_city_commas(self):
        self.assertEqual(
            app_main._parse_multi_value_arg(['["Houston, TX", "Austin, TX"]']),
            ["Houston, TX", "Austin, TX"],
        )
        self.assertEqual(
            app_main._parse_multi_value_arg(["Houston, TX | Dallas, TX"]),
            ["Houston, TX", "Dallas, TX"],
        )
        self.assertEqual(
            app_main._parse_multi_value_arg(["Miami, FL; Orlando, FL"]),
            ["Miami, FL", "Orlando, FL"],
        )
        self.assertEqual(
            app_main._parse_multi_value_arg(["Houston, TX", "Austin, TX"]),
            ["Houston, TX", "Austin, TX"],
        )

    def test_main_queue_mode_advances_cursor_and_finishes_job(self):
        mock_candidate = RawCandidate(
            place_id="p_queue_1",
            business_name="Gulf Coast Plumbing",
            city="Houston, TX",
            industry="Plumbing",
            phone="(713) 555-0199",
            rating=4.9,
            reviews_count=150,
            website_url=None,
        )
        mock_audit = SiteAudit(website_found=False, website_status="NO_WEBSITE", http_status="NO_URL")
        mock_contacts = ContactEnrichment(email_status="NOT_ATTEMPTED", social_status="NOT_ATTEMPTED")
        mock_score = LeadScore(
            opportunity_score=90,
            pitch_tier="HOT",
            pitch_angle="NO_WEBSITE",
            pitch_summary="Hot lead",
        )

        with patch.object(database, "is_cloud_enabled", return_value=True), \
             patch.object(database, "init_db"), \
             patch.object(database, "fetch_next_targets", return_value=[
                 {"id": "tq-uuid-1", "city": "Houston, TX", "industry": "Plumbing", "next_page_offset": 20, "max_results_per_run": 10}
             ]), \
             patch.object(database, "create_scrape_job", return_value="job-uuid-99") as mock_create_job, \
             patch.object(database, "update_scrape_job_progress"), \
             patch.object(database, "finish_scrape_job") as mock_finish_job, \
             patch.object(database, "is_duplicate", return_value=False), \
             patch.object(database, "upsert_lead_with_status", return_value="inserted") as mock_upsert, \
             patch.object(database, "advance_target_cursor") as mock_advance, \
             patch("engine.discovery.discover_leads", return_value=[mock_candidate]) as mock_discover, \
             patch("engine.validator.validate_url", return_value=mock_audit), \
             patch("engine.extractor.extract_contacts", return_value=mock_contacts), \
             patch("engine.scorer.score_lead", return_value=mock_score):
            app_main.main(["--live", "--queue", "--queue-limit", "2", "--trigger-source", "CRON"])

        mock_discover.assert_called_once_with(
            city="Houston, TX", industry="Plumbing", max_results=10, start=20
        )
        mock_create_job.assert_called_once()
        mock_upsert.assert_called_once()
        mock_advance.assert_called_once_with("tq-uuid-1", leads_found=1, page_step=20)
        finish_kwargs = mock_finish_job.call_args.kwargs
        self.assertEqual(finish_kwargs["job_id"], "job-uuid-99")
        self.assertEqual(finish_kwargs["status"], "COMPLETED")
        self.assertEqual(finish_kwargs["stats"]["leads_inserted"], 1)

    def test_supabase_schema_sql_and_workflow_shared_apps_invariants(self):
        sql_path = os.path.join(config.BASE_DIR, "supabase", "prospectiq_schema.sql")
        with open(sql_path, "r", encoding="utf-8") as f:
            sql = f.read()

        sql_no_comments_upper = "\n".join(
            line for line in sql.splitlines() if not line.lstrip().startswith("--")
        ).upper()

        # 1. Strict schema isolation: zero `public.*` DDL, zero `cadence.*` edits, zero extensions
        self.assertNotIn("CREATE TABLE PUBLIC.", sql_no_comments_upper)
        self.assertNotIn("CREATE TABLE IF NOT EXISTS PUBLIC.", sql_no_comments_upper)
        self.assertNotIn("CREATE EXTENSION", sql_no_comments_upper)
        self.assertNotIn("DROP SCHEMA", sql_no_comments_upper)
        self.assertNotIn("CADENCE.", sql_no_comments_upper)

        # 2. ZERO triggers on shared `auth.users`!
        self.assertNotIn("CREATE TRIGGER", sql_no_comments_upper)
        self.assertIn("CREATE TABLE IF NOT EXISTS prospectiq.profiles", sql)

        # 3. Explicit PostgREST schema grants & zero anon table/sequence/function access
        self.assertIn("GRANT USAGE ON SCHEMA prospectiq TO anon, authenticated, service_role;", sql)
        self.assertIn("REVOKE ALL ON ALL TABLES IN SCHEMA prospectiq FROM PUBLIC, anon;", sql)
        self.assertIn("GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA prospectiq TO authenticated, service_role;", sql)
        self.assertIn("GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA prospectiq TO authenticated, service_role;", sql)
        self.assertIn("GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA prospectiq TO authenticated, service_role;", sql)

        # 4. Owner-UUID RLS (never generic USING (true)) on every table
        self.assertIn("CREATE OR REPLACE FUNCTION prospectiq.is_owner()", sql)
        self.assertIn("auth.uid() = cfg.value::uuid", sql)
        self.assertNotIn("USING (TRUE)", sql_no_comments_upper)
        for tbl in ("profiles", "leads", "scrape_jobs", "target_queue", "api_quotas", "exclusions", "app_config"):
            self.assertIn(f"ALTER TABLE prospectiq.{tbl}", sql)

        # 5. All 3 RPCs enforce owner authentication guard for publishable-key JWT calls
        self.assertEqual(sql.count("AND NOT prospectiq.is_owner() THEN"), 3)
        self.assertIn("ALTER PUBLICATION supabase_realtime ADD TABLE prospectiq.leads;", sql)
        self.assertIn("ALTER PUBLICATION supabase_realtime ADD TABLE prospectiq.scrape_jobs;", sql)

        # 6. GitHub Actions workflow uses publishable key + Owner Auth ONLY (ZERO service_role!)
        wf_path = os.path.join(config.BASE_DIR, ".github", "workflows", "auto-scrape.yml")
        with open(wf_path, "r", encoding="utf-8") as f:
            wf = f.read()
        self.assertNotIn("SUPABASE_SERVICE_ROLE_KEY", wf)
        self.assertIn("secrets.SUPABASE_URL || secrets.NEXT_PUBLIC_SUPABASE_URL", wf)
        self.assertIn("secrets.SUPABASE_ANON_KEY || secrets.NEXT_PUBLIC_SUPABASE_ANON_KEY", wf)
        self.assertIn("SUPABASE_OWNER_EMAIL", wf)
        self.assertIn("SUPABASE_OWNER_PASSWORD", wf)


if __name__ == "__main__":
    unittest.main(verbosity=2)
