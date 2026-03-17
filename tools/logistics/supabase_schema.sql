-- ============================================================
-- Logistics Crisis Monitor — Supabase Schema
-- Run this entire script in Supabase SQL Editor (one shot)
-- ============================================================

-- 1. COMPANIES TABLE
-- The list of monitored companies (managed via Supabase Table Editor)
CREATE TABLE companies (
  id          UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  ig_username TEXT NOT NULL UNIQUE,
  name        TEXT NOT NULL,
  ig_url      TEXT GENERATED ALWAYS AS ('https://instagram.com/' || ig_username) STORED,
  website_url TEXT,
  country     TEXT DEFAULT 'CO',
  added_at    TIMESTAMPTZ DEFAULT now(),
  is_active   BOOLEAN DEFAULT true,
  notes       TEXT
);

-- 2. SCANS TABLE
-- One row per company per weekly scan
CREATE TABLE scans (
  id                    UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  company_id            UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
  scanned_at            TIMESTAMPTZ DEFAULT now(),
  status                TEXT NOT NULL CHECK (status IN ('completed', 'not_available', 'error')),
  risk_score            INTEGER,
  risk_level            TEXT,
  summary               TEXT,
  posts_analyzed        INTEGER,
  total_comments_scraped INTEGER,
  brand_replies_excluded INTEGER,
  comments_analyzed     INTEGER,
  complaints_found      INTEGER,
  complaint_rate_pct    NUMERIC(5,2),
  category_breakdown    JSONB DEFAULT '{}',
  recency_trend         TEXT CHECK (recency_trend IN ('worsening', 'stable', 'improving')),
  recent_complaint_rate NUMERIC(5,1),
  older_complaint_rate  NUMERIC(5,1),
  ig_followers          INTEGER,
  runtime_sec           NUMERIC(6,1),
  claude_tokens_used    INTEGER,
  error_message         TEXT,
  -- Delta vs previous scan (computed by cron script)
  prev_risk_score       INTEGER,
  score_delta           INTEGER,

  UNIQUE(company_id, scanned_at)
);

CREATE INDEX idx_scans_company_date ON scans(company_id, scanned_at DESC);
CREATE INDEX idx_scans_date ON scans(scanned_at DESC);

-- 3. FLAGGED COMMENTS TABLE
-- Individual logistics complaints detected by Claude
CREATE TABLE flagged_comments (
  id              UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  scan_id         UUID NOT NULL REFERENCES scans(id) ON DELETE CASCADE,
  company_id      UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
  comment_id      TEXT,
  text            TEXT NOT NULL,
  category        TEXT NOT NULL,
  severity        TEXT NOT NULL,
  owner           TEXT,
  comment_timestamp TEXT,
  likes           INTEGER DEFAULT 0,
  post_url        TEXT
);

CREATE INDEX idx_flagged_scan ON flagged_comments(scan_id);
CREATE INDEX idx_flagged_company ON flagged_comments(company_id);

-- 4. VIEW: Latest scan per company (powers the dashboard overview)
CREATE VIEW company_latest_scan AS
SELECT DISTINCT ON (c.id)
  c.id AS company_id,
  c.ig_username,
  c.name,
  c.ig_url,
  c.country,
  c.is_active,
  c.website_url,
  s.id AS scan_id,
  s.scanned_at,
  s.status,
  s.risk_score,
  s.risk_level,
  s.recency_trend,
  s.complaints_found,
  s.comments_analyzed,
  s.complaint_rate_pct,
  s.ig_followers,
  s.summary,
  s.score_delta,
  s.prev_risk_score,
  s.category_breakdown
FROM companies c
LEFT JOIN scans s ON s.company_id = c.id AND s.status = 'completed'
WHERE c.is_active = true
ORDER BY c.id, s.scanned_at DESC;

-- 5. ROW LEVEL SECURITY
-- anon key = read-only (for the public dashboard)
-- service_role key = full access (for GitHub Actions cron)

ALTER TABLE companies ENABLE ROW LEVEL SECURITY;
ALTER TABLE scans ENABLE ROW LEVEL SECURITY;
ALTER TABLE flagged_comments ENABLE ROW LEVEL SECURITY;

-- Public read policies (anon)
CREATE POLICY "anon_read_companies" ON companies FOR SELECT USING (true);
CREATE POLICY "anon_read_scans" ON scans FOR SELECT USING (true);
CREATE POLICY "anon_read_flagged" ON flagged_comments FOR SELECT USING (true);

-- Service role write policies (cron script)
CREATE POLICY "service_write_companies" ON companies FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "service_write_scans" ON scans FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "service_write_flagged" ON flagged_comments FOR ALL USING (true) WITH CHECK (true);

-- ============================================================
-- Done! You should see 3 tables + 1 view in the Table Editor.
-- ============================================================
