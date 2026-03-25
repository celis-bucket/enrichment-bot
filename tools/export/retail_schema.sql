-- ============================================================
-- Retail Channel Detection — Supabase Schema
-- Run this entire script in Supabase SQL Editor (one shot)
-- ============================================================

-- 1. DEPARTMENT STORE REGISTRY
-- Controlled list of multi-brand/department stores in COL & MEX
CREATE TABLE retail_department_stores (
  id              UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  name            TEXT NOT NULL UNIQUE,
  name_normalized TEXT NOT NULL UNIQUE,
  country         TEXT NOT NULL CHECK (country IN ('COL', 'MEX')),
  website_url     TEXT,
  scraper_active  BOOLEAN DEFAULT false,
  scraper_config  JSONB DEFAULT '{}',
  last_scraped_at TIMESTAMPTZ,
  created_at      TIMESTAMPTZ DEFAULT now()
);

-- 2. BRANDS DETECTED PER STORE (populated by periodic scrapers)
CREATE TABLE retail_store_brands (
  id                    UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  store_id              UUID NOT NULL REFERENCES retail_department_stores(id) ON DELETE CASCADE,
  brand_name            TEXT NOT NULL,
  brand_name_normalized TEXT NOT NULL,
  detected_at           TIMESTAMPTZ DEFAULT now(),
  source_url            TEXT,
  UNIQUE(store_id, brand_name_normalized)
);

CREATE INDEX idx_rsb_store ON retail_store_brands(store_id);
CREATE INDEX idx_rsb_brand_norm ON retail_store_brands(brand_name_normalized);

-- 3. NEW COLUMNS ON enriched_companies
ALTER TABLE enriched_companies
  ADD COLUMN IF NOT EXISTS has_distributors       BOOLEAN,
  ADD COLUMN IF NOT EXISTS has_own_stores         BOOLEAN,
  ADD COLUMN IF NOT EXISTS own_store_count_col    INTEGER,
  ADD COLUMN IF NOT EXISTS own_store_count_mex    INTEGER,
  ADD COLUMN IF NOT EXISTS has_multibrand_stores  BOOLEAN,
  ADD COLUMN IF NOT EXISTS multibrand_store_names JSONB DEFAULT '[]',
  ADD COLUMN IF NOT EXISTS on_mercadolibre       BOOLEAN,
  ADD COLUMN IF NOT EXISTS on_amazon             BOOLEAN,
  ADD COLUMN IF NOT EXISTS on_rappi              BOOLEAN,
  ADD COLUMN IF NOT EXISTS retail_confidence     NUMERIC(4,3),
  ADD COLUMN IF NOT EXISTS retail_enriched_at    TIMESTAMPTZ;

-- 4. RLS FOR NEW TABLES
ALTER TABLE retail_department_stores ENABLE ROW LEVEL SECURITY;
ALTER TABLE retail_store_brands ENABLE ROW LEVEL SECURITY;

CREATE POLICY "anon_read_stores" ON retail_department_stores
  FOR SELECT USING (true);
CREATE POLICY "service_write_stores" ON retail_department_stores
  FOR ALL USING (true) WITH CHECK (true);

CREATE POLICY "anon_read_store_brands" ON retail_store_brands
  FOR SELECT USING (true);
CREATE POLICY "service_write_store_brands" ON retail_store_brands
  FOR ALL USING (true) WITH CHECK (true);

-- 5. SEED DATA: Initial department stores
-- Colombia
INSERT INTO retail_department_stores (name, name_normalized, country, website_url) VALUES
  ('Falabella', 'falabella', 'COL', 'https://www.falabella.com.co'),
  ('Exito', 'exito', 'COL', 'https://www.exito.com'),
  ('Alkosto', 'alkosto', 'COL', 'https://www.alkosto.com'),
  ('Homecenter', 'homecenter', 'COL', 'https://www.homecenter.com.co'),
  ('Flamingo', 'flamingo', 'COL', 'https://www.flamingo.com.co'),
  ('Jumbo', 'jumbo', 'COL', 'https://www.tiendasjumbo.co'),
  ('Ktronix', 'ktronix', 'COL', 'https://www.ktronix.com'),
  ('Panamericana', 'panamericana', 'COL', 'https://www.panamericana.com.co'),
  ('Olimpica', 'olimpica', 'COL', 'https://www.olimpica.com'),
  ('Cencosud', 'cencosud', 'COL', 'https://www.cencosud.com.co')
ON CONFLICT (name) DO NOTHING;

-- Mexico
INSERT INTO retail_department_stores (name, name_normalized, country, website_url) VALUES
  ('Liverpool', 'liverpool', 'MEX', 'https://www.liverpool.com.mx'),
  ('Palacio de Hierro', 'palacio de hierro', 'MEX', 'https://www.elpalaciodehierro.com'),
  ('Coppel', 'coppel', 'MEX', 'https://www.coppel.com'),
  ('Sears', 'sears', 'MEX', 'https://www.sears.com.mx'),
  ('Suburbia', 'suburbia', 'MEX', 'https://www.suburbia.com.mx'),
  ('Walmart', 'walmart', 'MEX', 'https://www.walmart.com.mx'),
  ('Soriana', 'soriana', 'MEX', 'https://www.soriana.com'),
  ('HEB', 'heb', 'MEX', 'https://www.heb.com.mx'),
  ('Sanborns', 'sanborns', 'MEX', 'https://www.sanborns.com.mx'),
  ('Bodega Aurrera', 'bodega aurrera', 'MEX', 'https://www.bodegaaurrera.com.mx')
ON CONFLICT (name) DO NOTHING;

-- ============================================================
-- Done! You should see 2 new tables + 11 new columns on enriched_companies.
-- ============================================================
