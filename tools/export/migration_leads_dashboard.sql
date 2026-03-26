-- Migration: Add leads dashboard columns to enriched_companies
-- Run this in Supabase SQL Editor

ALTER TABLE enriched_companies
ADD COLUMN IF NOT EXISTS source TEXT,
ADD COLUMN IF NOT EXISTS hs_lead_stage TEXT,
ADD COLUMN IF NOT EXISTS hs_lead_label TEXT;

CREATE INDEX IF NOT EXISTS idx_ec_source
ON enriched_companies (source);

-- Backfill existing lite-enriched leads
UPDATE enriched_companies SET source = 'hubspot_leads' WHERE batch_id = 'lite-full-mar26';
UPDATE enriched_companies SET source = 'hubspot_leads' WHERE batch_id = 'lite-100-mar26';
