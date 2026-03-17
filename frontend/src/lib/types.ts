/**
 * TypeScript types for the Enrichment Agent API
 */

export interface WorkflowStep {
  step: string;
  status: "ok" | "warn" | "fail" | "skip";
  duration_ms: number;
  detail?: string | null;
}

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

export interface ApolloContact {
  name: string;
  title: string;
  email?: string | null;
  linkedin_url?: string | null;
  phone?: string | null;
}

export interface EnrichmentV2Results {
  // Identity
  company_name?: string | null;
  domain?: string | null;
  // Platform
  platform?: string | null;
  platform_confidence?: number | null;
  // Geography
  geography?: string | null;
  geography_confidence?: number | null;
  // Category
  category?: string | null;
  category_confidence?: number | null;
  category_evidence?: string | null;
  // Social
  instagram_url?: string | null;
  ig_followers?: number | null;
  ig_size_score?: number | null;
  ig_health_score?: number | null;
  // Company / Apollo
  company_linkedin?: string | null;
  contact_name?: string | null;
  contact_email?: string | null;
  number_employes?: number | null;
  contacts?: ApolloContact[];
  // Meta Ads
  meta_active_ads_count?: number | null;
  meta_ad_library_url?: string | null;
  // Catalog
  product_count?: number | null;
  avg_price?: number | null;
  price_range_min?: number | null;
  price_range_max?: number | null;
  currency?: string | null;
  // Traffic
  estimated_monthly_visits?: number | null;
  traffic_confidence?: number | null;
  signals_used?: string | null;
  // Google Demand
  brand_demand_score?: number | null;
  site_serp_coverage_score?: number | null;
  google_confidence?: number | null;
  // Fulfillment
  fulfillment_provider?: string | null;
  fulfillment_confidence?: number | null;
  // Prediction
  prediction?: OrdersPrediction | null;
  // Execution meta
  tool_coverage_pct?: number | null;
  total_runtime_sec?: number | null;
  cost_estimate_usd?: number | null;
  // Workflow
  workflow_log: WorkflowStep[];
}

export interface DuplicateCheckResult {
  exists: boolean;
  domain?: string | null;
  last_analyzed?: string | null;
}

export interface CompanyListItem {
  id?: string;
  domain?: string | null;
  company_name?: string | null;
  platform?: string | null;
  category?: string | null;
  geography?: string | null;
  ig_followers?: number | null;
  ig_size_score?: number | null;
  ig_health_score?: number | null;
  meta_active_ads_count?: number | null;
  contact_name?: string | null;
  contact_email?: string | null;
  predicted_orders_p50?: number | null;
  prediction_confidence?: string | null;
  tool_coverage_pct?: number | null;
  updated_at?: string | null;
}

export interface CompanyListResponse {
  companies: CompanyListItem[];
  total: number;
  page: number;
  limit: number;
}
