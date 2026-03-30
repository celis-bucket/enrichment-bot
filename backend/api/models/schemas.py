"""
Pydantic models for API request/response schemas
"""

from datetime import datetime
import json
from typing import Any, Optional, List
from pydantic import BaseModel, Field, field_validator


# ===== Request Models =====

class SyncEnrichmentRequest(BaseModel):
    """Request model for synchronous enrichment analysis"""
    url: str = Field(..., description="E-commerce URL or brand name (e.g., 'armatura.com.co')")
    geography: str = Field(..., description="Country code: COL or MEX", pattern=r"^(COL|MEX)$")


# ===== Response Models =====

class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    redis: str
    workers: int
    timestamp: datetime


class WorkflowStep(BaseModel):
    """Individual workflow step execution log"""
    step: str
    status: str  # "ok", "warn", "fail", "skip"
    duration_ms: int
    detail: Optional[str] = None


class OrdersPrediction(BaseModel):
    """Orders estimation model output"""
    predicted_orders_p10: int
    predicted_orders_p50: int
    predicted_orders_p90: int
    prediction_confidence: str  # "high", "medium", "low"


class ApolloContact(BaseModel):
    """Single Apollo contact"""
    name: str = ""
    title: str = ""
    email: Optional[str] = None
    linkedin_url: Optional[str] = None
    phone: Optional[str] = None


class EnrichmentV2Results(BaseModel):
    """V2 enrichment results — full schema for frontend + Google Sheet"""
    # Identity
    company_name: Optional[str] = None
    domain: Optional[str] = None
    # Platform
    platform: Optional[str] = None
    platform_confidence: Optional[float] = None
    # Geography
    geography: Optional[str] = None
    geography_confidence: Optional[float] = None
    # Category
    category: Optional[str] = None
    category_confidence: Optional[float] = None
    category_evidence: Optional[str] = None
    # Social
    instagram_url: Optional[str] = None
    ig_followers: Optional[int] = None
    ig_size_score: Optional[int] = None
    ig_health_score: Optional[int] = None
    fb_followers: Optional[int] = None
    tiktok_followers: Optional[int] = None
    # Company / Apollo
    company_linkedin: Optional[str] = None
    contact_name: Optional[str] = None
    contact_email: Optional[str] = None
    number_employes: Optional[int] = None
    contacts: List[ApolloContact] = Field(default_factory=list)
    # Meta Ads
    meta_active_ads_count: Optional[int] = None
    meta_ad_library_url: Optional[str] = None
    # Catalog
    product_count: Optional[int] = None
    avg_price: Optional[float] = None
    price_range_min: Optional[float] = None
    price_range_max: Optional[float] = None
    currency: Optional[str] = None
    # Traffic
    estimated_monthly_visits: Optional[int] = None
    traffic_confidence: Optional[float] = None
    signals_used: Optional[str] = None
    # Google Demand
    brand_demand_score: Optional[float] = None
    site_serp_coverage_score: Optional[float] = None
    google_confidence: Optional[float] = None
    # HubSpot CRM
    hubspot_company_id: Optional[str] = None
    hubspot_company_url: Optional[str] = None
    hubspot_deal_count: Optional[int] = None
    hubspot_deal_stage: Optional[str] = None
    hubspot_contact_exists: Optional[int] = None
    hubspot_lifecycle_label: Optional[str] = None
    hubspot_last_contacted: Optional[str] = None
    # Prediction
    prediction: Optional[OrdersPrediction] = None
    # Potential Scoring
    ecommerce_size_score: Optional[int] = None
    retail_size_score: Optional[int] = None
    combined_size_score: Optional[int] = None
    fit_score: Optional[int] = None
    overall_potential_score: Optional[int] = None
    potential_tier: Optional[str] = None
    # Execution meta
    tool_coverage_pct: Optional[float] = None
    total_runtime_sec: Optional[float] = None
    cost_estimate_usd: Optional[float] = None
    # Workflow
    workflow_log: List[WorkflowStep] = Field(default_factory=list)


class DuplicateCheckResponse(BaseModel):
    """Response for domain duplicate check"""
    exists: bool
    domain: Optional[str] = None
    last_analyzed: Optional[str] = None


class CompanyListItem(BaseModel):
    """Compact company row for the history table"""
    id: Optional[str] = None
    domain: Optional[str] = None
    company_name: Optional[str] = None
    platform: Optional[str] = None
    category: Optional[str] = None
    geography: Optional[str] = None
    ig_followers: Optional[int] = None
    ig_size_score: Optional[int] = None
    ig_health_score: Optional[int] = None
    meta_active_ads_count: Optional[int] = None
    contact_name: Optional[str] = None
    contact_email: Optional[str] = None
    predicted_orders_p50: Optional[int] = None
    predicted_orders_p90: Optional[int] = None
    prediction_confidence: Optional[str] = None
    hubspot_company_id: Optional[str] = None
    hubspot_deal_count: Optional[int] = None
    hubspot_deal_stage: Optional[str] = None
    # Retail Channels
    has_distributors: Optional[bool] = None
    has_own_stores: Optional[bool] = None
    has_multibrand_stores: Optional[bool] = None
    multibrand_store_names: Optional[Any] = None
    on_mercadolibre: Optional[bool] = None
    on_amazon: Optional[bool] = None
    on_rappi: Optional[bool] = None
    on_walmart: Optional[bool] = None
    on_liverpool: Optional[bool] = None
    on_coppel: Optional[bool] = None
    on_tiktok_shop: Optional[bool] = None
    marketplace_names: Optional[Any] = None
    retail_confidence: Optional[float] = None
    # Potential Scoring
    ecommerce_size_score: Optional[int] = None
    retail_size_score: Optional[int] = None
    combined_size_score: Optional[int] = None
    fit_score: Optional[int] = None
    overall_potential_score: Optional[int] = None
    potential_tier: Optional[str] = None
    tool_coverage_pct: Optional[float] = None
    updated_at: Optional[str] = None


class CompanyListResponse(BaseModel):
    """Paginated list of enriched companies"""
    companies: List[CompanyListItem] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    limit: int = 25


# ===== Lead Dashboard Models =====

class LeadListItem(BaseModel):
    """Compact lead row for the leads dashboard"""
    id: Optional[str] = None
    domain: Optional[str] = None
    clean_url: Optional[str] = None
    company_name: Optional[str] = None
    platform: Optional[str] = None
    geography: Optional[str] = None
    ig_followers: Optional[int] = None
    ig_size_score: Optional[int] = None
    lite_triage_score: Optional[int] = None
    worth_full_enrichment: Optional[bool] = None
    enrichment_type: Optional[str] = None
    hubspot_company_id: Optional[str] = None
    hubspot_company_url: Optional[str] = None
    hubspot_deal_stage: Optional[str] = None
    hubspot_deal_count: Optional[int] = None
    source: Optional[str] = None
    hs_lead_stage: Optional[str] = None
    hs_lead_label: Optional[str] = None
    hs_lead_owner: Optional[str] = None
    hs_last_lost_deal_date: Optional[str] = None
    hs_lead_created_at: Optional[str] = None
    hs_last_activity_date: Optional[str] = None
    hs_activity_count: Optional[int] = None
    hs_open_tasks_count: Optional[int] = None
    overall_potential_score: Optional[int] = None
    potential_tier: Optional[str] = None
    predicted_orders_p90: Optional[int] = None
    # Retail Channels
    has_distributors: Optional[bool] = None
    has_own_stores: Optional[bool] = None
    has_multibrand_stores: Optional[bool] = None
    multibrand_store_names: Optional[Any] = None
    on_mercadolibre: Optional[bool] = None
    on_amazon: Optional[bool] = None
    on_rappi: Optional[bool] = None
    on_walmart: Optional[bool] = None
    on_liverpool: Optional[bool] = None
    on_coppel: Optional[bool] = None
    on_tiktok_shop: Optional[bool] = None
    marketplace_names: Optional[Any] = None
    retail_confidence: Optional[float] = None
    tool_coverage_pct: Optional[float] = None
    updated_at: Optional[str] = None


class LeadListResponse(BaseModel):
    """Paginated list of leads"""
    companies: List[LeadListItem] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    limit: int = 25
    total_leads: int = 0
    worth_full_count: int = 0
    fully_enriched_count: int = 0


# ===== Feedback Models =====

class FeedbackRequest(BaseModel):
    """Request model for submitting feedback on an enrichment section"""
    section: str = Field(..., description="Section name: overview, instagram, catalog, traffic, meta_ads, contacts, prediction, general, retail, leads")
    comment: str = Field(..., min_length=1, description="Free-form feedback text")
    suggested_value: Optional[str] = Field(None, description="Optional corrected value")
    created_by: Optional[str] = Field("anonymous", description="User identifier")


class FeedbackItem(BaseModel):
    """Single feedback entry"""
    id: Optional[str] = None
    domain: str
    section: str
    comment: str
    suggested_value: Optional[str] = None
    created_by: str = "anonymous"
    created_at: Optional[str] = None
    resolved_at: Optional[str] = None
    resolved_note: Optional[str] = None


class FeedbackListResponse(BaseModel):
    """List of feedback items for a domain"""
    domain: str
    feedback: List[FeedbackItem] = Field(default_factory=list)
    total: int = 0


class FeedbackResolveRequest(BaseModel):
    """Request to mark feedback as resolved"""
    resolved_note: Optional[str] = Field(None, description="Note explaining resolution")


class UnresolvedFeedbackResponse(BaseModel):
    """All unresolved feedback across domains"""
    feedback: List[FeedbackItem] = Field(default_factory=list)
    total: int = 0


# ===== HubSpot Detail Models =====

class HubSpotDeal(BaseModel):
    """Single HubSpot deal"""
    id: str = ""
    name: str = ""
    stage: str = ""
    pipeline: str = ""
    amount: str = ""
    closedate: str = ""


class HubSpotContact(BaseModel):
    """Single HubSpot contact"""
    name: Optional[str] = None
    email: Optional[str] = None
    title: Optional[str] = None


# ===== TikTok Shop Models =====

class TikTokShopWeeklyItem(BaseModel):
    """Single TikTok Shop from the weekly ranking"""
    shop_name: str
    company_name: Optional[str] = None
    category: Optional[str] = None
    rating: Optional[float] = None
    sales_count: Optional[float] = None
    gmv: Optional[float] = None
    products: Optional[int] = None
    influencers: Optional[int] = None
    fastmoss_url: Optional[str] = None
    week_start: str
    matched_domain: Optional[str] = None
    wow_sales_pct: Optional[float] = None
    wow_gmv_pct: Optional[float] = None
    is_new: bool = False


class TikTokWeeklyResponse(BaseModel):
    """Paginated weekly TikTok Shop ranking"""
    shops: List[TikTokShopWeeklyItem] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    limit: int = 50
    week_start: Optional[str] = None
    prev_week_start: Optional[str] = None
    total_new: int = 0


class TikTokShopHistoryItem(BaseModel):
    """Single week snapshot for a shop"""
    week_start: str
    sales_count: Optional[float] = None
    gmv: Optional[float] = None
    products: Optional[int] = None
    rating: Optional[float] = None


class TikTokShopHistoryResponse(BaseModel):
    """Time-series history for a single shop"""
    shop_name: str
    matched_domain: Optional[str] = None
    category: Optional[str] = None
    history: List[TikTokShopHistoryItem] = Field(default_factory=list)


class TikTokShopForDomainResponse(BaseModel):
    """TikTok Shop data for a single enriched company"""
    shop_name: Optional[str] = None
    sales_count: Optional[float] = None
    gmv: Optional[float] = None
    products: Optional[int] = None
    rating: Optional[float] = None
    influencers: Optional[int] = None
    fastmoss_url: Optional[str] = None
    week_start: Optional[str] = None
    wow_sales_pct: Optional[float] = None
    wow_gmv_pct: Optional[float] = None
    has_data: bool = False


# ===== Team Prospecting Panel Models =====

class TeamStatsResponse(BaseModel):
    """Aggregated KPIs for one SDR"""
    owner: str
    total_leads: int = 0
    tier_distribution: dict = Field(default_factory=dict)
    stage_distribution: dict = Field(default_factory=dict)
    leads_not_enriched: int = 0
    leads_worth_enrichment: int = 0
    leads_cold_30d: int = 0
    leads_stale_6m: int = 0
    enrichment_pct: float = 0.0
    avg_potential_score: float = 0.0


class TeamAlert(BaseModel):
    """A single actionable alert for an SDR"""
    alert_type: str
    title: str
    severity: str  # "red", "yellow", "green"
    count: int
    description: str
    affected_domains: List[str] = Field(default_factory=list)


class TeamAlertsResponse(BaseModel):
    """Computed alerts for one SDR"""
    owner: str
    alerts: List[TeamAlert] = Field(default_factory=list)


class TeamLeadListResponse(BaseModel):
    """Paginated lead list for a specific SDR"""
    companies: List[LeadListItem] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    limit: int = 25


class HubSpotDetailResponse(BaseModel):
    """Extended HubSpot company detail for the history modal"""
    company_name: str = ""
    created_at: Optional[str] = None
    lifecycle_stage: Optional[str] = None
    lifecycle_label: Optional[str] = None
    lead_status: Optional[str] = None
    owner_name: Optional[str] = None
    owner_email: Optional[str] = None
    last_contacted: Optional[str] = None
    last_activity: Optional[str] = None
    total_activities: int = 0
    contact_activities: int = 0
    associated_contacts_count: int = 0
    deals: List[HubSpotDeal] = Field(default_factory=list)
    deal_count: int = 0
    most_advanced_stage: str = ""
    contacts: List[HubSpotContact] = Field(default_factory=list)
    hubspot_url: str = ""
