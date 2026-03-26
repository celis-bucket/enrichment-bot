-- Migration: Add potential scoring columns to enriched_companies
-- Run this in Supabase SQL Editor

ALTER TABLE enriched_companies
ADD COLUMN IF NOT EXISTS ecommerce_size_score SMALLINT,
ADD COLUMN IF NOT EXISTS retail_size_score SMALLINT,
ADD COLUMN IF NOT EXISTS combined_size_score SMALLINT,
ADD COLUMN IF NOT EXISTS fit_score SMALLINT,
ADD COLUMN IF NOT EXISTS overall_potential_score SMALLINT,
ADD COLUMN IF NOT EXISTS potential_tier TEXT;

CREATE INDEX IF NOT EXISTS idx_ec_potential
ON enriched_companies (overall_potential_score DESC NULLS LAST);

CREATE INDEX IF NOT EXISTS idx_ec_potential_tier
ON enriched_companies (potential_tier);
