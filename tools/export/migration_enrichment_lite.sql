-- Migration: Add enrichment lite columns to enriched_companies
-- Run this in Supabase SQL Editor

ALTER TABLE enriched_companies
ADD COLUMN IF NOT EXISTS enrichment_type TEXT,
ADD COLUMN IF NOT EXISTS lite_triage_score SMALLINT,
ADD COLUMN IF NOT EXISTS worth_full_enrichment BOOLEAN;

CREATE INDEX IF NOT EXISTS idx_ec_enrichment_type
ON enriched_companies (enrichment_type);

CREATE INDEX IF NOT EXISTS idx_ec_lite_score
ON enriched_companies (lite_triage_score DESC NULLS LAST);
