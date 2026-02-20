/**
 * TypeScript types for the Enrichment Agent API
 * These mirror the backend Pydantic schemas
 */

export interface PlatformInfo {
  name: string;
  confidence: number;
  version?: string | null;
  evidence: string[];
}

export interface GeographyInfo {
  countries: string[];
  primary_country?: string | null;
  confidence: number;
  evidence: Record<string, string[]>;
}

export interface SocialMediaProfile {
  url: string;
  followers?: number | null;
  posts_last_30d?: number | null;
  engagement_rate?: number | null;
  ig_size_score?: number | null;
  ig_health_score?: number | null;
  full_name?: string | null;
  biography?: string | null;
  is_verified?: boolean | null;
  is_private?: boolean | null;
  product_tags_count?: number | null;
  avg_days_between_posts?: number | null;
}

export interface SocialMediaInfo {
  instagram?: SocialMediaProfile | null;
  facebook?: SocialMediaProfile | null;
  tiktok?: SocialMediaProfile | null;
  youtube?: SocialMediaProfile | null;
  linkedin?: SocialMediaProfile | null;
}

export interface CatalogInfo {
  product_count: number;
  avg_price: number;
  price_range: {
    min: number;
    max: number;
  };
  currency: string;
}

export interface WorkflowStep {
  step: string;
  status: "ok" | "warn" | "fail" | "skip";
  duration_ms: number;
  detail?: string | null;
}

export interface EnrichmentResults {
  url: string;
  platform?: PlatformInfo | null;
  geography?: GeographyInfo | null;
  social_media?: SocialMediaInfo | null;
  catalog?: CatalogInfo | null;
  workflow_log?: WorkflowStep[];
}

export interface EnrichmentError {
  detail: string;
}

// ===== V2 Types (Enrichment Flow V2) =====

export interface PipelineStep {
  step: string;
  status: "running" | "ok" | "warn" | "fail" | "skip";
  duration_ms?: number;
  detail?: string;
}

export interface OrdersPrediction {
  predicted_orders_p10: number;
  predicted_orders_p50: number;
  predicted_orders_p90: number;
  prediction_confidence: "high" | "medium" | "low";
}

export interface EnrichmentV2Results {
  company_name?: string | null;
  domain?: string | null;
  platform?: string | null;
  category?: string | null;
  instagram_url?: string | null;
  ig_followers?: number | null;
  ig_size_score?: number | null;
  ig_health_score?: number | null;
  company_linkedin?: string | null;
  contact_name?: string | null;
  contact_email?: string | null;
  number_employes?: number | null;
  prediction?: OrdersPrediction | null;
  workflow_log: WorkflowStep[];
}

export interface DuplicateCheckResult {
  exists: boolean;
  domain?: string | null;
  last_analyzed?: string | null;
}
