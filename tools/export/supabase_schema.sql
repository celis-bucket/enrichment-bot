-- ============================================================
-- Enrichment Agent — Supabase Schema
-- Run this entire script in Supabase SQL Editor (one shot)
-- ============================================================

-- 1. ENRICHED COMPANIES TABLE
-- One row per domain (upsert on re-enrichment)
CREATE TABLE enriched_companies (
  id                        UUID DEFAULT gen_random_uuid() PRIMARY KEY,

  -- IDENTITY
  run_id                    TEXT NOT NULL,
  batch_id                  TEXT,
  clean_url                 TEXT,
  domain                    TEXT NOT NULL UNIQUE,
  company_name              TEXT,

  -- PLATFORM
  platform                  TEXT,
  platform_confidence       NUMERIC(4,3),

  -- GEOGRAPHY
  geography                 TEXT,
  geography_confidence      NUMERIC(4,3),

  -- CATEGORY (LLM)
  category                  TEXT,
  category_confidence       NUMERIC(4,3),
  category_evidence         TEXT,

  -- SOCIAL (Instagram)
  instagram_url             TEXT,
  ig_followers              INTEGER,
  ig_engagement_rate        NUMERIC(8,5),
  ig_size_score             INTEGER,
  ig_health_score           INTEGER,
  ig_is_verified            SMALLINT,

  -- SOCIAL (Facebook & TikTok)
  fb_followers              INTEGER,
  tiktok_followers          INTEGER,

  -- CATALOG
  product_count             INTEGER,
  avg_price                 NUMERIC(12,2),
  price_range_min           NUMERIC(12,2),
  price_range_max           NUMERIC(12,2),
  currency                  TEXT,

  -- TRAFFIC
  estimated_monthly_visits  INTEGER,
  traffic_confidence        NUMERIC(4,3),
  signals_used              TEXT,

  -- GOOGLE DEMAND
  brand_demand_score        NUMERIC(4,3),
  site_serp_coverage_score  NUMERIC(4,3),
  google_confidence         NUMERIC(4,3),

  -- FULFILLMENT
  fulfillment_provider      TEXT,
  fulfillment_confidence    NUMERIC(4,3),

  -- META ADS
  meta_active_ads_count     INTEGER,

  -- TIKTOK ADS
  tiktok_active_ads_count   INTEGER,

  -- APOLLO (primary contact as scalars for easy filtering)
  contact_name              TEXT,
  contact_email             TEXT,
  company_linkedin          TEXT,
  number_employes           INTEGER,
  founded_year              INTEGER,

  -- APOLLO (all contacts as JSONB)
  contacts_list             JSONB DEFAULT '[]',

  -- ORDERS PREDICTION
  predicted_orders_p10      INTEGER,
  predicted_orders_p50      INTEGER,
  predicted_orders_p90      INTEGER,
  prediction_confidence     TEXT,

  -- EXECUTION META
  tool_coverage_pct         NUMERIC(4,3),
  total_runtime_sec         NUMERIC(8,2),
  cost_estimate_usd         NUMERIC(8,4),
  workflow_execution_log    JSONB DEFAULT '[]',

  -- TIMESTAMPS
  created_at                TIMESTAMPTZ DEFAULT now(),
  updated_at                TIMESTAMPTZ DEFAULT now()
);

-- 2. INDEXES
CREATE INDEX idx_ec_domain ON enriched_companies(domain);
CREATE INDEX idx_ec_created_at ON enriched_companies(created_at DESC);
CREATE INDEX idx_ec_updated_at ON enriched_companies(updated_at DESC);
CREATE INDEX idx_ec_batch_id ON enriched_companies(batch_id);
CREATE INDEX idx_ec_category ON enriched_companies(category);
CREATE INDEX idx_ec_geography ON enriched_companies(geography);

-- 3. AUTO-UPDATE updated_at ON UPSERT
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_updated_at
  BEFORE UPDATE ON enriched_companies
  FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- 4. ROW LEVEL SECURITY
ALTER TABLE enriched_companies ENABLE ROW LEVEL SECURITY;

-- anon key = read-only (for dashboard / frontend via backend)
CREATE POLICY "anon_read_enriched" ON enriched_companies
  FOR SELECT USING (true);

-- service_role = full access (for backend writes)
CREATE POLICY "service_write_enriched" ON enriched_companies
  FOR ALL USING (true) WITH CHECK (true);

-- ============================================================
-- Done! You should see 1 table in the Table Editor.
-- Run an enrichment to verify writes work.
-- ============================================================
