-- Migration: Add HubSpot CRM columns to enriched_companies
-- Run this in Supabase SQL Editor: https://supabase.com/dashboard/project/cbgqwnxwwzqfetpxkomr/sql

ALTER TABLE enriched_companies
  ADD COLUMN IF NOT EXISTS hubspot_company_id text,
  ADD COLUMN IF NOT EXISTS hubspot_company_url text,
  ADD COLUMN IF NOT EXISTS hubspot_deal_count integer,
  ADD COLUMN IF NOT EXISTS hubspot_deal_stage text,
  ADD COLUMN IF NOT EXISTS hubspot_contact_exists integer,
  ADD COLUMN IF NOT EXISTS hubspot_lifecycle_label text,
  ADD COLUMN IF NOT EXISTS hubspot_last_contacted text;
