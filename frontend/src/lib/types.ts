/**
 * TypeScript types for the Enrichment Agent API
 */

export interface WorkflowStep {
  step: string;
  status: "running" | "ok" | "warn" | "fail" | "skip";
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
  fb_followers?: number | null;
  tiktok_followers?: number | null;
  // Company / Apollo
  company_linkedin?: string | null;
  contact_name?: string | null;
  contact_email?: string | null;
  number_employes?: number | null;
  contacts?: ApolloContact[];
  // Meta Ads
  meta_active_ads_count?: number | null;
  meta_ad_library_url?: string | null;
  // TikTok Ads
  tiktok_active_ads_count?: number | null;
  tiktok_ads_library_url?: string | null;
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
  // HubSpot CRM
  hubspot_company_id?: string | null;
  hubspot_company_url?: string | null;
  hubspot_deal_count?: number | null;
  hubspot_deal_stage?: string | null;
  hubspot_contact_exists?: number | null;
  hubspot_lifecycle_label?: string | null;
  hubspot_last_contacted?: string | null;
  // Retail Channels
  has_distributors?: boolean | null;
  has_own_stores?: boolean | null;
  own_store_count_col?: number | null;
  own_store_count_mex?: number | null;
  has_multibrand_stores?: boolean | null;
  multibrand_store_names?: string[];
  on_mercadolibre?: boolean | null;
  on_amazon?: boolean | null;
  on_rappi?: boolean | null;
  on_walmart?: boolean | null;
  on_liverpool?: boolean | null;
  on_coppel?: boolean | null;
  on_tiktok_shop?: boolean | null;
  marketplace_names?: string[];
  retail_confidence?: number | null;
  // Prediction
  prediction?: OrdersPrediction | null;
  // Potential Scoring
  ecommerce_size_score?: number | null;
  retail_size_score?: number | null;
  combined_size_score?: number | null;
  fit_score?: number | null;
  overall_potential_score?: number | null;
  potential_tier?: string | null;
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
  predicted_orders_p90?: number | null;
  prediction_confidence?: string | null;
  hubspot_company_id?: string | null;
  hubspot_deal_count?: number | null;
  hubspot_deal_stage?: string | null;
  // Potential Scoring
  ecommerce_size_score?: number | null;
  retail_size_score?: number | null;
  combined_size_score?: number | null;
  fit_score?: number | null;
  overall_potential_score?: number | null;
  potential_tier?: string | null;
  tool_coverage_pct?: number | null;
  updated_at?: string | null;
}

export interface CompanyListResponse {
  companies: CompanyListItem[];
  total: number;
  page: number;
  limit: number;
}

// ===== Lead Dashboard Types =====

export interface LeadListItem {
  id?: string;
  domain?: string | null;
  clean_url?: string | null;
  company_name?: string | null;
  platform?: string | null;
  geography?: string | null;
  ig_followers?: number | null;
  ig_size_score?: number | null;
  lite_triage_score?: number | null;
  worth_full_enrichment?: boolean | null;
  enrichment_type?: string | null;
  hubspot_company_id?: string | null;
  hubspot_company_url?: string | null;
  hubspot_deal_stage?: string | null;
  hubspot_deal_count?: number | null;
  source?: string | null;
  hs_lead_stage?: string | null;
  hs_lead_label?: string | null;
  hs_lead_owner?: string | null;
  hs_last_lost_deal_date?: string | null;
  hs_lead_created_at?: string | null;
  hs_last_activity_date?: string | null;
  hs_activity_count?: number | null;
  hs_open_tasks_count?: number | null;
  overall_potential_score?: number | null;
  potential_tier?: string | null;
  predicted_orders_p90?: number | null;
  tool_coverage_pct?: number | null;
  updated_at?: string | null;
}

export interface LeadListResponse {
  companies: LeadListItem[];
  total: number;
  page: number;
  limit: number;
  total_leads: number;
  worth_full_count: number;
  fully_enriched_count: number;
}

export interface FeedbackItem {
  id?: string;
  domain: string;
  section: string;
  comment: string;
  suggested_value?: string | null;
  created_by: string;
  created_at?: string | null;
}

export interface HubSpotDeal {
  id: string;
  name: string;
  stage: string;
  pipeline: string;
  amount: string;
  closedate: string;
}

export interface HubSpotContact {
  name?: string | null;
  email?: string | null;
  title?: string | null;
}

// ===== TikTok Shop Types =====

export interface TikTokShopWeeklyItem {
  shop_name: string;
  company_name?: string | null;
  category?: string | null;
  rating?: number | null;
  sales_count?: number | null;
  gmv?: number | null;
  products?: number | null;
  influencers?: number | null;
  fastmoss_url?: string | null;
  week_start: string;
  matched_domain?: string | null;
  wow_sales_pct?: number | null;
  wow_gmv_pct?: number | null;
  is_new: boolean;
}

export interface TikTokWeeklyResponse {
  shops: TikTokShopWeeklyItem[];
  total: number;
  page: number;
  limit: number;
  week_start?: string | null;
  prev_week_start?: string | null;
  total_new: number;
}

export interface TikTokShopHistoryItem {
  week_start: string;
  sales_count?: number | null;
  gmv?: number | null;
  products?: number | null;
  rating?: number | null;
}

export interface TikTokShopHistoryResponse {
  shop_name: string;
  matched_domain?: string | null;
  category?: string | null;
  history: TikTokShopHistoryItem[];
}

export interface TikTokShopForDomainResponse {
  shop_name?: string | null;
  sales_count?: number | null;
  gmv?: number | null;
  products?: number | null;
  rating?: number | null;
  influencers?: number | null;
  fastmoss_url?: string | null;
  week_start?: string | null;
  wow_sales_pct?: number | null;
  wow_gmv_pct?: number | null;
  has_data: boolean;
}

// ===== Team Prospecting Panel Types =====

export interface TeamStatsResponse {
  owner: string;
  total_leads: number;
  tier_distribution: Record<string, number>;
  stage_distribution: Record<string, number>;
  leads_not_enriched: number;
  leads_worth_enrichment: number;
  leads_cold_30d: number;
  leads_stale_6m: number;
  enrichment_pct: number;
  avg_potential_score: number;
}

export interface TeamAlert {
  alert_type: string;
  title: string;
  severity: 'red' | 'yellow' | 'green';
  count: number;
  description: string;
  affected_domains: string[];
}

export interface TeamAlertsResponse {
  owner: string;
  alerts: TeamAlert[];
}

export interface TeamLeadListResponse {
  companies: LeadListItem[];
  total: number;
  page: number;
  limit: number;
}

export interface HubSpotDetail {
  company_name: string;
  created_at?: string | null;
  lifecycle_stage?: string | null;
  lifecycle_label?: string | null;
  lead_status?: string | null;
  owner_name?: string | null;
  owner_email?: string | null;
  last_contacted?: string | null;
  last_activity?: string | null;
  total_activities: number;
  contact_activities: number;
  associated_contacts_count: number;
  deals: HubSpotDeal[];
  deal_count: number;
  most_advanced_stage: string;
  contacts: HubSpotContact[];
  hubspot_url: string;
}
