"""
Pydantic models for API request/response schemas
"""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


# ===== Request Models =====

class SyncEnrichmentRequest(BaseModel):
    """Request model for synchronous enrichment analysis"""
    url: str = Field(..., description="E-commerce URL or brand name with country (e.g., 'Armatura Colombia')")


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


# ===== Feedback Models =====

class FeedbackRequest(BaseModel):
    """Request model for submitting feedback on an enrichment section"""
    section: str = Field(..., description="Section name: overview, instagram, catalog, traffic, meta_ads, contacts, prediction, general")
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


class FeedbackListResponse(BaseModel):
    """List of feedback items for a domain"""
    domain: str
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
