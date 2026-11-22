-- ============================================================================
-- ProspectIQ v3.0 — Isolated Multi-Schema Migration (`shared-apps` Hub)
-- Target Project: shared-apps (https://hlxkgikqmljthjsbhzhq.supabase.co)
-- Sibling Live App: Cadence (`cadence` schema — NEVER touched or altered)
-- File: supabase/prospectiq_schema.sql
-- ============================================================================
-- SHARED-APPS MULTI-SCHEMA SAFETY GUARANTEES:
--   1. Strictly scoped to `prospectiq.*` (ZERO `public.*` objects, ZERO `cadence.*` edits).
--   2. Uses built-in `gen_random_uuid()` (no `CREATE EXTENSION` in `public`).
--   3. ZERO triggers on shared `auth.users` — `prospectiq.profiles` is lazily
--      provisioned via idempotent `upsert(..., { onConflict: "id" })` on login.
--   4. Publishable key (`sb_publishable_...`) ONLY — NEVER uses `service_role`
--      in `.env`, Vercel, or GitHub Secrets. All access is authenticated via
--      Supabase Auth JWT and gated by Owner-UUID RLS + `is_owner()` guards.
--   5. ZERO table/sequence/function access for `anon` (logged-out visitors use
--      100% static client-side dummy data).
--   6. 100% idempotent (safe to re-run; NEVER run `supabase db reset` on Hub).
--
-- POST-RUN DASHBOARD CHECKLIST (shared-apps):
--   Step 1: Paste & run this entire script in shared-apps SQL Editor.
--   Step 2: Project Settings -> Data API -> Exposed schemas:
--           APPEND `prospectiq` -> `public, cadence, prospectiq` (do NOT remove `cadence`!).
--   Step 3: Authentication -> Users -> copy Muhammad Kamal's existing User UID
--           (if already registered on Cadence, reuse that exact account & UID!).
--   Step 4: Run this 1-line SQL snippet to unlock Owner-UUID RLS on `prospectiq.*`:
--           INSERT INTO prospectiq.app_config (key, value)
--           VALUES ('owner_user_id', '<PASTE-YOUR-USER-UID-HERE>')
--           ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = NOW();
--   Step 5: Authentication -> URL Configuration -> Redirect URLs:
--           APPEND (do NOT delete Cadence URLs!) your ProspectIQ localhost &
--           Vercel `/auth/callback` URLs.
-- ============================================================================

-- ── 0. Dedicated Schema & Explicit PostgREST Grants ─────────────────────────
CREATE SCHEMA IF NOT EXISTS prospectiq;

-- Schema USAGE allows PostgREST to resolve the `prospectiq` profile cleanly,
-- while `anon` receives ZERO table, sequence, or function privileges below.
GRANT USAGE ON SCHEMA prospectiq TO anon, authenticated, service_role;

ALTER DEFAULT PRIVILEGES IN SCHEMA prospectiq
    REVOKE ALL ON TABLES FROM PUBLIC, anon;
ALTER DEFAULT PRIVILEGES IN SCHEMA prospectiq
    REVOKE ALL ON SEQUENCES FROM PUBLIC, anon;
ALTER DEFAULT PRIVILEGES IN SCHEMA prospectiq
    REVOKE ALL ON FUNCTIONS FROM PUBLIC, anon;

ALTER DEFAULT PRIVILEGES IN SCHEMA prospectiq
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO authenticated, service_role;
ALTER DEFAULT PRIVILEGES IN SCHEMA prospectiq
    GRANT USAGE, SELECT ON SEQUENCES TO authenticated, service_role;
ALTER DEFAULT PRIVILEGES IN SCHEMA prospectiq
    GRANT EXECUTE ON FUNCTIONS TO authenticated, service_role;

-- ── 1. Internal Owner Config Table (SQL Editor / Superuser Only) ────────────
CREATE TABLE IF NOT EXISTS prospectiq.app_config (
    key         TEXT PRIMARY KEY,
    value       TEXT NOT NULL,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

REVOKE ALL ON TABLE prospectiq.app_config FROM PUBLIC, anon, authenticated;
GRANT ALL ON TABLE prospectiq.app_config TO service_role;
ALTER TABLE prospectiq.app_config ENABLE ROW LEVEL SECURITY;

-- Fail-closed Owner-UUID predicate.
-- Guarantees users registered on sibling apps (e.g., `cadence`) sharing
-- `auth.users` receive ZERO access to `prospectiq.*`.
CREATE OR REPLACE FUNCTION prospectiq.is_owner()
RETURNS BOOLEAN
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = prospectiq, auth
AS $$
    SELECT auth.uid() IS NOT NULL
       AND EXISTS (
           SELECT 1
           FROM prospectiq.app_config cfg
           WHERE cfg.key = 'owner_user_id'
             AND cfg.value ~* '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
             AND auth.uid() = cfg.value::uuid
       );
$$;

-- ── 2. Lazily Provisioned Profiles Table (ZERO triggers on auth.users!) ─────
CREATE TABLE IF NOT EXISTS prospectiq.profiles (
    id          UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    email       TEXT,
    full_name   TEXT,
    role        TEXT NOT NULL DEFAULT 'owner' CHECK (role IN ('owner')),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── 3. Scrape Job Execution History (Realtime Enabled) ──────────────────────
CREATE TABLE IF NOT EXISTS prospectiq.scrape_jobs (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    trigger_source        TEXT NOT NULL DEFAULT 'CLI'
                          CHECK (trigger_source IN ('CRON', 'MANUAL_UI', 'CLI')),
    status                TEXT NOT NULL DEFAULT 'QUEUED'
                          CHECK (status IN ('QUEUED', 'RUNNING', 'COMPLETED', 'PARTIAL', 'FAILED')),
    cities                JSONB NOT NULL DEFAULT '[]'::jsonb,
    niches                JSONB NOT NULL DEFAULT '[]'::jsonb,
    max_results_per_query INTEGER NOT NULL DEFAULT 10,
    leads_discovered      INTEGER NOT NULL DEFAULT 0,
    leads_inserted        INTEGER NOT NULL DEFAULT 0,
    leads_updated         INTEGER NOT NULL DEFAULT 0,
    leads_skipped_dup     INTEGER NOT NULL DEFAULT 0,
    emails_found          INTEGER NOT NULL DEFAULT 0,
    blocked_count         INTEGER NOT NULL DEFAULT 0,
    quota_exhausted_count INTEGER NOT NULL DEFAULT 0,
    github_run_url        TEXT,
    error_summary         TEXT,
    started_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at           TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_scrape_jobs_started_at
    ON prospectiq.scrape_jobs (started_at DESC);
CREATE INDEX IF NOT EXISTS idx_scrape_jobs_status
    ON prospectiq.scrape_jobs (status);

-- ── 4. Core Leads Table (Realtime Enabled) ──────────────────────────────────
CREATE TABLE IF NOT EXISTS prospectiq.leads (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    place_id            TEXT UNIQUE,
    business_name       TEXT NOT NULL,
    city                TEXT NOT NULL,
    industry            TEXT NOT NULL,
    phone               TEXT,
    address             TEXT,
    rating              NUMERIC(2,1),
    reviews_count       INTEGER NOT NULL DEFAULT 0,
    business_status     TEXT NOT NULL DEFAULT 'OPERATIONAL',
    is_franchise        BOOLEAN NOT NULL DEFAULT FALSE,

    -- Web Presence & Digital Health Audit
    website_status      TEXT NOT NULL DEFAULT 'NO_WEBSITE'
                        CHECK (website_status IN ('LIVE', 'WAF_PROTECTED', 'PARKED', 'BROKEN', 'NO_WEBSITE')),
    website_url         TEXT,
    root_domain         TEXT,
    http_status         TEXT,
    has_ssl             BOOLEAN,
    is_mobile_friendly  BOOLEAN,
    cms_platform        TEXT,
    has_analytics       BOOLEAN,
    has_meta_pixel      BOOLEAN,
    load_time_ms        INTEGER,

    -- Contact Enrichment
    email               TEXT,
    email_status        TEXT NOT NULL DEFAULT 'NOT_ATTEMPTED'
                        CHECK (email_status IN (
                            'FOUND_JSONLD', 'FOUND_SCRAPE', 'FOUND_API',
                            'NOT_FOUND', 'BLOCKED', 'QUOTA_EXHAUSTED', 'NOT_ATTEMPTED'
                        )),
    email_mx_valid      BOOLEAN,
    secondary_emails    JSONB NOT NULL DEFAULT '[]'::jsonb,
    linkedin            TEXT,
    instagram           TEXT,
    facebook            TEXT,
    twitter             TEXT,
    social_status       TEXT NOT NULL DEFAULT 'NOT_ATTEMPTED'
                        CHECK (social_status IN (
                            'FOUND_MAPS', 'FOUND_ON_SITE', 'FOUND_DDG',
                            'NOT_FOUND', 'BLOCKED', 'NOT_ATTEMPTED'
                        )),

    -- Agency Intelligence & Mini-CRM
    opportunity_score   INTEGER NOT NULL DEFAULT 0
                        CHECK (opportunity_score BETWEEN 0 AND 100),
    pitch_tier          TEXT NOT NULL DEFAULT 'COLD'
                        CHECK (pitch_tier IN ('HOT', 'WARM', 'COLD')),
    pitch_angle         TEXT NOT NULL DEFAULT 'ESTABLISHED'
                        CHECK (pitch_angle IN (
                            'NO_WEBSITE', 'SOCIAL_ONLY', 'REDESIGN_SSL',
                            'SEO_ANALYTICS', 'ESTABLISHED'
                        )),
    pitch_summary       TEXT,
    outreach_status     TEXT NOT NULL DEFAULT 'NEW'
                        CHECK (outreach_status IN (
                            'NEW', 'CONTACTED', 'FOLLOW_UP', 'REPLIED',
                            'QUALIFIED', 'WON', 'DISQUALIFIED'
                        )),
    outreach_notes      TEXT NOT NULL DEFAULT '',

    -- Audit & Lineage
    scrape_job_id       UUID REFERENCES prospectiq.scrape_jobs(id) ON DELETE SET NULL,
    discovered_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_enriched_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_leads_name_city UNIQUE (business_name, city)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_leads_root_domain_unique
    ON prospectiq.leads (lower(root_domain)) WHERE root_domain IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_leads_lower_name_city
    ON prospectiq.leads (lower(business_name), lower(city));
CREATE INDEX IF NOT EXISTS idx_leads_score_tier
    ON prospectiq.leads (opportunity_score DESC, pitch_tier);
CREATE INDEX IF NOT EXISTS idx_leads_city_industry
    ON prospectiq.leads (city, industry);
CREATE INDEX IF NOT EXISTS idx_leads_outreach_status
    ON prospectiq.leads (outreach_status);
CREATE INDEX IF NOT EXISTS idx_leads_discovered_at
    ON prospectiq.leads (discovered_at DESC);

-- ── 5. Automated Cron Target Queue (Tracks Pagination Depth) ────────────────
CREATE TABLE IF NOT EXISTS prospectiq.target_queue (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    city                TEXT NOT NULL,
    industry            TEXT NOT NULL,
    enabled             BOOLEAN NOT NULL DEFAULT TRUE,
    priority            INTEGER NOT NULL DEFAULT 5,
    next_page_offset    INTEGER NOT NULL DEFAULT 0,
    max_results_per_run INTEGER NOT NULL DEFAULT 10,
    last_scraped_at     TIMESTAMPTZ,
    total_leads_found   INTEGER NOT NULL DEFAULT 0,
    CONSTRAINT uq_target_queue_pair UNIQUE (city, industry)
);

CREATE INDEX IF NOT EXISTS idx_target_queue_schedule
    ON prospectiq.target_queue (enabled, priority ASC, last_scraped_at ASC NULLS FIRST);

-- ── 6. Monthly API Quota Counters (Replaces local usage_tracker.json) ───────
CREATE TABLE IF NOT EXISTS prospectiq.api_quotas (
    month_key      TEXT NOT NULL,
    provider       TEXT NOT NULL CHECK (provider IN ('serpapi', 'brave', 'hunter')),
    calls_used     INTEGER NOT NULL DEFAULT 0,
    monthly_limit  INTEGER NOT NULL,
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (month_key, provider)
);

-- ── 7. Domain / Franchise / Email Junk Exclusions ───────────────────────────
CREATE TABLE IF NOT EXISTS prospectiq.exclusions (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pattern_type   TEXT NOT NULL CHECK (pattern_type IN ('DOMAIN', 'FRANCHISE', 'EMAIL_DOMAIN')),
    pattern_value  TEXT NOT NULL,
    reason         TEXT,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_exclusions_pair UNIQUE (pattern_type, pattern_value)
);

-- ── 8. Owner-UUID Row-Level Security (RLS) on Every Table ───────────────────
ALTER TABLE prospectiq.profiles     ENABLE ROW LEVEL SECURITY;
ALTER TABLE prospectiq.leads        ENABLE ROW LEVEL SECURITY;
ALTER TABLE prospectiq.scrape_jobs  ENABLE ROW LEVEL SECURITY;
ALTER TABLE prospectiq.target_queue ENABLE ROW LEVEL SECURITY;
ALTER TABLE prospectiq.api_quotas   ENABLE ROW LEVEL SECURITY;
ALTER TABLE prospectiq.exclusions   ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS owner_all_profiles ON prospectiq.profiles;
CREATE POLICY owner_all_profiles ON prospectiq.profiles
    FOR ALL TO authenticated
    USING (auth.uid() = id AND prospectiq.is_owner())
    WITH CHECK (auth.uid() = id AND prospectiq.is_owner());

DROP POLICY IF EXISTS owner_all_leads ON prospectiq.leads;
CREATE POLICY owner_all_leads ON prospectiq.leads
    FOR ALL TO authenticated
    USING (prospectiq.is_owner())
    WITH CHECK (prospectiq.is_owner());

DROP POLICY IF EXISTS owner_all_scrape_jobs ON prospectiq.scrape_jobs;
CREATE POLICY owner_all_scrape_jobs ON prospectiq.scrape_jobs
    FOR ALL TO authenticated
    USING (prospectiq.is_owner())
    WITH CHECK (prospectiq.is_owner());

DROP POLICY IF EXISTS owner_all_target_queue ON prospectiq.target_queue;
CREATE POLICY owner_all_target_queue ON prospectiq.target_queue
    FOR ALL TO authenticated
    USING (prospectiq.is_owner())
    WITH CHECK (prospectiq.is_owner());

DROP POLICY IF EXISTS owner_all_api_quotas ON prospectiq.api_quotas;
CREATE POLICY owner_all_api_quotas ON prospectiq.api_quotas
    FOR ALL TO authenticated
    USING (prospectiq.is_owner())
    WITH CHECK (prospectiq.is_owner());

DROP POLICY IF EXISTS owner_all_exclusions ON prospectiq.exclusions;
CREATE POLICY owner_all_exclusions ON prospectiq.exclusions
    FOR ALL TO authenticated
    USING (prospectiq.is_owner())
    WITH CHECK (prospectiq.is_owner());

-- ── 9. Atomic Owner-Gated RPC Functions (Publishable Key + Owner JWT Safe) ──

-- 9a. True Lead UPSERT preserving existing verified contacts & CRM notes
CREATE OR REPLACE FUNCTION prospectiq.upsert_lead(p_lead JSONB)
RETURNS TEXT
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = prospectiq, auth
AS $$
DECLARE
    v_place_id          TEXT := NULLIF(trim(p_lead->>'place_id'), '');
    v_business_name     TEXT := trim(p_lead->>'business_name');
    v_city              TEXT := trim(p_lead->>'city');
    v_industry          TEXT := trim(p_lead->>'industry');
    v_root_domain       TEXT := NULLIF(lower(trim(p_lead->>'root_domain')), '');
    v_secondary_emails  JSONB := COALESCE(p_lead->'secondary_emails', '[]'::jsonb);
    v_scrape_job_id     UUID := CASE
                                    WHEN NULLIF(trim(p_lead->>'scrape_job_id'), '') IS NOT NULL
                                    THEN (p_lead->>'scrape_job_id')::uuid
                                    ELSE NULL
                                END;
    v_existing_id       UUID;
    v_inserted          BOOLEAN;
BEGIN
    IF current_user NOT IN ('postgres', 'supabase_admin') AND NOT prospectiq.is_owner() THEN
        RAISE EXCEPTION 'Forbidden: ProspectIQ owner authentication required'
            USING ERRCODE = '42501';
    END IF;

    -- 1. Prevent inserting a distinct business that duplicates an existing root_domain
    IF v_root_domain IS NOT NULL THEN
        SELECT id INTO v_existing_id
        FROM prospectiq.leads
        WHERE lower(root_domain) = v_root_domain
          AND NOT (
              (lower(business_name) = lower(v_business_name) AND lower(city) = lower(v_city))
              OR (v_place_id IS NOT NULL AND place_id = v_place_id)
          )
        LIMIT 1;

        IF v_existing_id IS NOT NULL THEN
            RETURN 'skipped_domain_dup';
        END IF;
    END IF;

    -- 2. If place_id already exists under a renamed GBP listing, update that row in place
    IF v_place_id IS NOT NULL THEN
        SELECT id INTO v_existing_id
        FROM prospectiq.leads
        WHERE place_id = v_place_id
        LIMIT 1;

        IF v_existing_id IS NOT NULL THEN
            UPDATE prospectiq.leads SET
                phone              = COALESCE(NULLIF(p_lead->>'phone', ''), phone),
                address            = COALESCE(NULLIF(p_lead->>'address', ''), address),
                rating             = COALESCE((p_lead->>'rating')::numeric(2,1), rating),
                reviews_count      = GREATEST(COALESCE((p_lead->>'reviews_count')::integer, 0), reviews_count),
                business_status    = COALESCE(NULLIF(p_lead->>'business_status', ''), business_status),
                is_franchise       = COALESCE((p_lead->>'is_franchise')::boolean, is_franchise),
                website_status     = COALESCE(NULLIF(p_lead->>'website_status', ''), website_status),
                website_url        = COALESCE(NULLIF(p_lead->>'website_url', ''), website_url),
                root_domain        = COALESCE(v_root_domain, root_domain),
                http_status        = COALESCE(NULLIF(p_lead->>'http_status', ''), http_status),
                has_ssl            = COALESCE((p_lead->>'has_ssl')::boolean, has_ssl),
                is_mobile_friendly = COALESCE((p_lead->>'is_mobile_friendly')::boolean, is_mobile_friendly),
                cms_platform       = COALESCE(NULLIF(p_lead->>'cms_platform', ''), cms_platform),
                has_analytics      = COALESCE((p_lead->>'has_analytics')::boolean, has_analytics),
                has_meta_pixel     = COALESCE((p_lead->>'has_meta_pixel')::boolean, has_meta_pixel),
                load_time_ms       = COALESCE((p_lead->>'load_time_ms')::integer, load_time_ms),
                email              = COALESCE(NULLIF(p_lead->>'email', ''), email),
                email_status       = CASE
                                         WHEN NULLIF(p_lead->>'email', '') IS NOT NULL
                                         THEN COALESCE(NULLIF(p_lead->>'email_status', ''), email_status)
                                         ELSE email_status
                                     END,
                email_mx_valid     = COALESCE((p_lead->>'email_mx_valid')::boolean, email_mx_valid),
                secondary_emails   = CASE
                                         WHEN jsonb_array_length(v_secondary_emails) > 0
                                         THEN v_secondary_emails
                                         ELSE secondary_emails
                                     END,
                linkedin           = COALESCE(NULLIF(p_lead->>'linkedin', ''), linkedin),
                instagram          = COALESCE(NULLIF(p_lead->>'instagram', ''), instagram),
                facebook           = COALESCE(NULLIF(p_lead->>'facebook', ''), facebook),
                twitter            = COALESCE(NULLIF(p_lead->>'twitter', ''), twitter),
                social_status      = CASE
                                         WHEN NULLIF(p_lead->>'linkedin', '') IS NOT NULL
                                           OR NULLIF(p_lead->>'instagram', '') IS NOT NULL
                                           OR NULLIF(p_lead->>'facebook', '') IS NOT NULL
                                           OR NULLIF(p_lead->>'twitter', '') IS NOT NULL
                                         THEN COALESCE(NULLIF(p_lead->>'social_status', ''), social_status)
                                         ELSE social_status
                                     END,
                opportunity_score  = COALESCE((p_lead->>'opportunity_score')::integer, opportunity_score),
                pitch_tier         = COALESCE(NULLIF(p_lead->>'pitch_tier', ''), pitch_tier),
                pitch_angle        = COALESCE(NULLIF(p_lead->>'pitch_angle', ''), pitch_angle),
                pitch_summary      = COALESCE(NULLIF(p_lead->>'pitch_summary', ''), pitch_summary),
                scrape_job_id      = COALESCE(v_scrape_job_id, scrape_job_id),
                last_enriched_at   = NOW()
                -- outreach_status & outreach_notes intentionally preserved!
            WHERE id = v_existing_id;
            RETURN 'updated';
        END IF;
    END IF;

    -- 3. Insert or update on (business_name, city) conflict
    INSERT INTO prospectiq.leads (
        place_id, business_name, city, industry, phone, address,
        rating, reviews_count, business_status, is_franchise,
        website_status, website_url, root_domain, http_status,
        has_ssl, is_mobile_friendly, cms_platform, has_analytics, has_meta_pixel, load_time_ms,
        email, email_status, email_mx_valid, secondary_emails,
        linkedin, instagram, facebook, twitter, social_status,
        opportunity_score, pitch_tier, pitch_angle, pitch_summary,
        outreach_status, outreach_notes, scrape_job_id
    ) VALUES (
        v_place_id,
        v_business_name,
        v_city,
        v_industry,
        NULLIF(p_lead->>'phone', ''),
        NULLIF(p_lead->>'address', ''),
        (p_lead->>'rating')::numeric(2,1),
        COALESCE((p_lead->>'reviews_count')::integer, 0),
        COALESCE(NULLIF(p_lead->>'business_status', ''), 'OPERATIONAL'),
        COALESCE((p_lead->>'is_franchise')::boolean, FALSE),
        COALESCE(NULLIF(p_lead->>'website_status', ''), 'NO_WEBSITE'),
        NULLIF(p_lead->>'website_url', ''),
        v_root_domain,
        NULLIF(p_lead->>'http_status', ''),
        (p_lead->>'has_ssl')::boolean,
        (p_lead->>'is_mobile_friendly')::boolean,
        NULLIF(p_lead->>'cms_platform', ''),
        (p_lead->>'has_analytics')::boolean,
        (p_lead->>'has_meta_pixel')::boolean,
        (p_lead->>'load_time_ms')::integer,
        NULLIF(p_lead->>'email', ''),
        COALESCE(NULLIF(p_lead->>'email_status', ''), 'NOT_ATTEMPTED'),
        (p_lead->>'email_mx_valid')::boolean,
        v_secondary_emails,
        NULLIF(p_lead->>'linkedin', ''),
        NULLIF(p_lead->>'instagram', ''),
        NULLIF(p_lead->>'facebook', ''),
        NULLIF(p_lead->>'twitter', ''),
        COALESCE(NULLIF(p_lead->>'social_status', ''), 'NOT_ATTEMPTED'),
        COALESCE((p_lead->>'opportunity_score')::integer, 0),
        COALESCE(NULLIF(p_lead->>'pitch_tier', ''), 'COLD'),
        COALESCE(NULLIF(p_lead->>'pitch_angle', ''), 'ESTABLISHED'),
        NULLIF(p_lead->>'pitch_summary', ''),
        COALESCE(NULLIF(p_lead->>'outreach_status', ''), 'NEW'),
        COALESCE(p_lead->>'outreach_notes', ''),
        v_scrape_job_id
    )
    ON CONFLICT (business_name, city) DO UPDATE SET
        place_id           = COALESCE(EXCLUDED.place_id, prospectiq.leads.place_id),
        phone              = COALESCE(EXCLUDED.phone, prospectiq.leads.phone),
        address            = COALESCE(EXCLUDED.address, prospectiq.leads.address),
        rating             = COALESCE(EXCLUDED.rating, prospectiq.leads.rating),
        reviews_count      = GREATEST(EXCLUDED.reviews_count, prospectiq.leads.reviews_count),
        business_status    = EXCLUDED.business_status,
        is_franchise       = EXCLUDED.is_franchise,
        website_status     = EXCLUDED.website_status,
        website_url        = COALESCE(EXCLUDED.website_url, prospectiq.leads.website_url),
        root_domain        = COALESCE(EXCLUDED.root_domain, prospectiq.leads.root_domain),
        http_status        = EXCLUDED.http_status,
        has_ssl            = COALESCE(EXCLUDED.has_ssl, prospectiq.leads.has_ssl),
        is_mobile_friendly = COALESCE(EXCLUDED.is_mobile_friendly, prospectiq.leads.is_mobile_friendly),
        cms_platform       = COALESCE(EXCLUDED.cms_platform, prospectiq.leads.cms_platform),
        has_analytics      = COALESCE(EXCLUDED.has_analytics, prospectiq.leads.has_analytics),
        has_meta_pixel     = COALESCE(EXCLUDED.has_meta_pixel, prospectiq.leads.has_meta_pixel),
        load_time_ms       = COALESCE(EXCLUDED.load_time_ms, prospectiq.leads.load_time_ms),
        email              = COALESCE(EXCLUDED.email, prospectiq.leads.email),
        email_status       = CASE
                                 WHEN EXCLUDED.email IS NOT NULL THEN EXCLUDED.email_status
                                 ELSE prospectiq.leads.email_status
                             END,
        email_mx_valid     = COALESCE(EXCLUDED.email_mx_valid, prospectiq.leads.email_mx_valid),
        secondary_emails   = CASE
                                 WHEN jsonb_array_length(EXCLUDED.secondary_emails) > 0 THEN EXCLUDED.secondary_emails
                                 ELSE prospectiq.leads.secondary_emails
                             END,
        linkedin           = COALESCE(EXCLUDED.linkedin, prospectiq.leads.linkedin),
        instagram          = COALESCE(EXCLUDED.instagram, prospectiq.leads.instagram),
        facebook           = COALESCE(EXCLUDED.facebook, prospectiq.leads.facebook),
        twitter            = COALESCE(EXCLUDED.twitter, prospectiq.leads.twitter),
        social_status      = CASE
                                 WHEN EXCLUDED.linkedin IS NOT NULL OR EXCLUDED.instagram IS NOT NULL
                                   OR EXCLUDED.facebook IS NOT NULL OR EXCLUDED.twitter IS NOT NULL
                                 THEN EXCLUDED.social_status
                                 ELSE prospectiq.leads.social_status
                             END,
        opportunity_score  = EXCLUDED.opportunity_score,
        pitch_tier         = EXCLUDED.pitch_tier,
        pitch_angle        = EXCLUDED.pitch_angle,
        pitch_summary      = EXCLUDED.pitch_summary,
        scrape_job_id      = COALESCE(EXCLUDED.scrape_job_id, prospectiq.leads.scrape_job_id),
        last_enriched_at   = NOW()
        -- outreach_status & outreach_notes intentionally preserved on re-enrichment!
    RETURNING (xmax = 0) INTO v_inserted;

    RETURN CASE WHEN v_inserted THEN 'inserted' ELSE 'updated' END;
END;
$$;

-- 9b. Atomic Monthly API Quota Check & Increment (Owner-Gated, Race-Condition Safe)
CREATE OR REPLACE FUNCTION prospectiq.check_and_increment_quota(
    p_month_key     TEXT,
    p_provider      TEXT,
    p_monthly_limit INTEGER
)
RETURNS TABLE (
    allowed        BOOLEAN,
    calls_used     INTEGER,
    monthly_limit  INTEGER
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = prospectiq, auth
AS $$
DECLARE
    v_used  INTEGER;
    v_limit INTEGER;
BEGIN
    IF current_user NOT IN ('postgres', 'supabase_admin') AND NOT prospectiq.is_owner() THEN
        RAISE EXCEPTION 'Forbidden: ProspectIQ owner authentication required'
            USING ERRCODE = '42501';
    END IF;

    INSERT INTO prospectiq.api_quotas (month_key, provider, calls_used, monthly_limit)
    VALUES (p_month_key, p_provider, 0, p_monthly_limit)
    ON CONFLICT (month_key, provider) DO NOTHING;

    SELECT q.calls_used, LEAST(q.monthly_limit, p_monthly_limit)
      INTO v_used, v_limit
      FROM prospectiq.api_quotas q
     WHERE q.month_key = p_month_key
       AND q.provider  = p_provider
       FOR UPDATE;

    IF v_used >= v_limit THEN
        RETURN QUERY SELECT FALSE, v_used, v_limit;
        RETURN;
    END IF;

    UPDATE prospectiq.api_quotas
       SET calls_used = prospectiq.api_quotas.calls_used + 1,
           updated_at = NOW()
     WHERE month_key = p_month_key
       AND provider  = p_provider
    RETURNING prospectiq.api_quotas.calls_used INTO v_used;

    RETURN QUERY SELECT TRUE, v_used, v_limit;
END;
$$;

-- 9c. Atomic Target Queue Pagination Cursor Advance (Owner-Gated)
CREATE OR REPLACE FUNCTION prospectiq.advance_target_cursor(
    p_target_id   UUID,
    p_leads_found INTEGER DEFAULT 0,
    p_page_step   INTEGER DEFAULT 20
)
RETURNS VOID
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = prospectiq, auth
AS $$
BEGIN
    IF current_user NOT IN ('postgres', 'supabase_admin') AND NOT prospectiq.is_owner() THEN
        RAISE EXCEPTION 'Forbidden: ProspectIQ owner authentication required'
            USING ERRCODE = '42501';
    END IF;

    UPDATE prospectiq.target_queue
       SET next_page_offset  = next_page_offset + GREATEST(p_page_step, 0),
           total_leads_found = total_leads_found + GREATEST(p_leads_found, 0),
           last_scraped_at   = NOW()
     WHERE id = p_target_id;
END;
$$;

-- ── 10. Explicit Final PostgREST Grants (Authenticated & Service Role Only) ─
REVOKE ALL ON ALL TABLES IN SCHEMA prospectiq FROM PUBLIC, anon;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA prospectiq FROM PUBLIC, anon;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA prospectiq FROM PUBLIC, anon;

GRANT USAGE ON SCHEMA prospectiq TO anon, authenticated, service_role;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA prospectiq TO authenticated, service_role;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA prospectiq TO authenticated, service_role;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA prospectiq TO authenticated, service_role;

-- Re-lock internal owner config table strictly away from `authenticated`
REVOKE ALL ON TABLE prospectiq.app_config FROM PUBLIC, anon, authenticated;
GRANT ALL ON TABLE prospectiq.app_config TO service_role;

-- ── 11. Enable Supabase Realtime (Idempotent) ───────────────────────────────
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_publication WHERE pubname = 'supabase_realtime') THEN
        IF NOT EXISTS (
            SELECT 1 FROM pg_publication_tables
            WHERE pubname = 'supabase_realtime'
              AND schemaname = 'prospectiq'
              AND tablename = 'leads'
        ) THEN
            ALTER PUBLICATION supabase_realtime ADD TABLE prospectiq.leads;
        END IF;

        IF NOT EXISTS (
            SELECT 1 FROM pg_publication_tables
            WHERE pubname = 'supabase_realtime'
              AND schemaname = 'prospectiq'
              AND tablename = 'scrape_jobs'
        ) THEN
            ALTER PUBLICATION supabase_realtime ADD TABLE prospectiq.scrape_jobs;
        END IF;
    END IF;
END;
$$;

-- ── 12. Idempotent Starter Seeds (Target Queue & Core Exclusions) ───────────
INSERT INTO prospectiq.target_queue (city, industry, enabled, priority, next_page_offset, max_results_per_run)
VALUES
    ('Houston, TX',     'Plumbing',       TRUE,  1, 0, 10),
    ('Austin, TX',      'HVAC',           TRUE,  2, 0, 10),
    ('Dallas, TX',      'Roofing',        TRUE,  3, 0, 10),
    ('Miami, FL',       'Landscaping',    TRUE,  4, 0, 10),
    ('Atlanta, GA',     'Auto Detailing', TRUE,  5, 0, 10),
    ('San Antonio, TX', 'Plumbing',       TRUE,  6, 0, 10)
ON CONFLICT (city, industry) DO NOTHING;

INSERT INTO prospectiq.exclusions (pattern_type, pattern_value, reason)
VALUES
    ('DOMAIN',       'yelp.com',        'Business directory / aggregator'),
    ('DOMAIN',       'angi.com',        'Business directory / aggregator'),
    ('DOMAIN',       'thumbtack.com',   'Marketplace aggregator'),
    ('DOMAIN',       'homeadvisor.com', 'Marketplace aggregator'),
    ('DOMAIN',       'yellowpages.com', 'Business directory'),
    ('FRANCHISE',    'roto-rooter',     'National franchise chain'),
    ('FRANCHISE',    'service experts', 'National franchise chain'),
    ('FRANCHISE',    'mr. rooter',      'National franchise chain'),
    ('EMAIL_DOMAIN', 'wixpress.com',    'Platform internal tracking email'),
    ('EMAIL_DOMAIN', 'sentry.io',       'Error tracking email')
ON CONFLICT (pattern_type, pattern_value) DO NOTHING;
