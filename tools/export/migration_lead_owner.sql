-- Migration: Add lead owner and last lost deal date
-- Run this in Supabase SQL Editor

ALTER TABLE enriched_companies
ADD COLUMN IF NOT EXISTS hs_lead_owner TEXT,
ADD COLUMN IF NOT EXISTS hs_last_lost_deal_date TEXT;
