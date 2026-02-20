"""
Pydantic models for API request/response schemas
"""

from datetime import datetime
from typing import Optional, Dict, Any, List
from enum import Enum
from pydantic import BaseModel, Field, HttpUrl


class AnalysisDepth(str, Enum):
    """Analysis depth options"""
    quick = "quick"
    standard = "standard"
    comprehensive = "comprehensive"


class JobStatus(str, Enum):
    """Job status options"""
    queued = "queued"
    processing = "processing"
    completed = "completed"
    failed = "failed"


# ===== Request Models =====

class EnrichmentRequest(BaseModel):
    """Request model for creating an enrichment job"""
    url: str = Field(..., description="E-commerce URL to analyze")
    depth: AnalysisDepth = Field(
        default=AnalysisDepth.standard,
        description="Analysis depth: quick, standard, or comprehensive"
    )
    include_social: bool = Field(
        default=True,
        description="Whether to include social media analysis"
    )
    include_quality: bool = Field(
        default=True,
        description="Whether to include quality metrics"
    )


class SyncEnrichmentRequest(BaseModel):
    """Request model for synchronous enrichment analysis"""
    url: str = Field(..., description="E-commerce URL or brand name with country (e.g., 'Armatura Colombia')")


# ===== Response Models =====

class PlatformInfo(BaseModel):
    """E-commerce platform information"""
    name: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    version: Optional[str] = None
    evidence: List[str] = Field(default_factory=list)


class GeographyInfo(BaseModel):
    """Geographic operation information"""
    countries: List[str] = Field(default_factory=list)
    primary_country: Optional[str] = None
    confidence: float = Field(..., ge=0.0, le=1.0)
    evidence: Dict[str, Any] = Field(default_factory=dict)


class SocialMediaProfile(BaseModel):
    """Individual social media profile"""
    url: str
    followers: Optional[int] = None
    posts_last_30d: Optional[int] = None
    engagement_rate: Optional[float] = None
    ig_size_score: Optional[int] = Field(None, ge=0, le=100, description="Instagram size score (0-100)")
    ig_health_score: Optional[int] = Field(None, ge=0, le=100, description="Instagram health score (0-100)")
    full_name: Optional[str] = None
    biography: Optional[str] = None
    is_verified: Optional[bool] = None
    is_private: Optional[bool] = None
    product_tags_count: Optional[int] = None
    avg_days_between_posts: Optional[float] = None


class SocialMediaInfo(BaseModel):
    """Social media information"""
    instagram: Optional[SocialMediaProfile] = None
    facebook: Optional[SocialMediaProfile] = None
    tiktok: Optional[SocialMediaProfile] = None
    youtube: Optional[SocialMediaProfile] = None
    linkedin: Optional[SocialMediaProfile] = None


class CatalogInfo(BaseModel):
    """Product catalog information"""
    product_count: int
    avg_price: float
    price_range: Dict[str, float]  # {"min": float, "max": float}
    currency: str


class QualityMetrics(BaseModel):
    """E-commerce quality metrics"""
    overall_score: int = Field(..., ge=0, le=100)
    has_reviews: bool
    review_platform: Optional[str] = None
    avg_images_per_product: float
    avg_image_resolution: Dict[str, int]  # {"width": int, "height": int}
    has_shipping_policy: bool
    has_return_policy: bool
    policy_quality_score: int = Field(..., ge=0, le=100)


class CategoryInfo(BaseModel):
    """LLM-derived product category classification"""
    category: Optional[str] = None
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0)
    evidence: Optional[str] = None


class TrafficInfo(BaseModel):
    """Estimated traffic information"""
    estimated_monthly_visits: Optional[int] = None
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0)
    signals_used: Optional[List[str]] = None


class GoogleDemandInfo(BaseModel):
    """Google search demand scoring"""
    brand_demand_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    site_serp_coverage_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0)


class FulfillmentInfo(BaseModel):
    """Fulfillment/logistics provider information"""
    provider: Optional[str] = None
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0)


class EnrichmentSummary(BaseModel):
    """Overall enrichment summary"""
    volume_score: int = Field(..., ge=0, le=100)
    quality_score: int = Field(..., ge=0, le=100)
    recommendation: str


class WorkflowStep(BaseModel):
    """Individual workflow step execution log"""
    step: str
    status: str  # "ok", "warn", "fail", "skip"
    duration_ms: int
    detail: Optional[str] = None


class EnrichmentResults(BaseModel):
    """Complete enrichment results"""
    url: str
    domain: Optional[str] = None
    platform: Optional[PlatformInfo] = None
    geography: Optional[GeographyInfo] = None
    category: Optional[CategoryInfo] = None
    social_media: Optional[SocialMediaInfo] = None
    catalog: Optional[CatalogInfo] = None
    traffic: Optional[TrafficInfo] = None
    google_demand: Optional[GoogleDemandInfo] = None
    fulfillment: Optional[FulfillmentInfo] = None
    quality_metrics: Optional[QualityMetrics] = None
    summary: Optional[EnrichmentSummary] = None
    workflow_log: List[WorkflowStep] = Field(default_factory=list)


class JobResponse(BaseModel):
    """Response model for job creation"""
    job_id: str
    status: JobStatus
    created_at: datetime


class JobDetailResponse(BaseModel):
    """Response model for job status and results"""
    job_id: str
    status: JobStatus
    progress: int = Field(..., ge=0, le=100)
    current_step: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    results: Optional[EnrichmentResults] = None
    errors: List[str] = Field(default_factory=list)


class JobListResponse(BaseModel):
    """Response model for job listing"""
    jobs: List[JobDetailResponse]
    total: int
    page: int
    per_page: int


class ExportResponse(BaseModel):
    """Response model for Google Sheets export"""
    sheet_url: str
    exported_at: datetime


class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    redis: str
    workers: int
    timestamp: datetime


# ===== V2 Models (Enrichment Flow V2) =====

class OrdersPrediction(BaseModel):
    """Orders estimation model output"""
    predicted_orders_p10: int
    predicted_orders_p50: int
    predicted_orders_p90: int
    prediction_confidence: str  # "high", "medium", "low"


class EnrichmentV2Results(BaseModel):
    """V2 enrichment results — lean schema for frontend + Google Sheet"""
    company_name: Optional[str] = None
    domain: Optional[str] = None
    platform: Optional[str] = None
    category: Optional[str] = None
    instagram_url: Optional[str] = None
    ig_followers: Optional[int] = None
    ig_size_score: Optional[int] = None
    ig_health_score: Optional[int] = None
    company_linkedin: Optional[str] = None
    contact_name: Optional[str] = None
    contact_email: Optional[str] = None
    number_employes: Optional[int] = None
    prediction: Optional[OrdersPrediction] = None
    workflow_log: List[WorkflowStep] = Field(default_factory=list)


class DuplicateCheckResponse(BaseModel):
    """Response for domain duplicate check against Sheet V2"""
    exists: bool
    domain: Optional[str] = None
    last_analyzed: Optional[str] = None


# ===== Batch Processing Models =====

class BatchRequest(BaseModel):
    """Request model for batch URL processing"""
    urls: List[str] = Field(..., min_length=1, description="List of URLs or brand names to analyze")
    spreadsheet_url: Optional[str] = Field(None, description="Optional existing Google Sheets URL to append to")


class BatchResponse(BaseModel):
    """Response model for batch submission"""
    batch_id: str
    sheet_url: str
    status: str = "processing"
    total: int
    deduplicated: int
    message: str


class BatchStatusResponse(BaseModel):
    """Response model for batch status polling"""
    batch_id: str
    status: str  # "processing", "completed", "failed"
    total: int
    processed: int
    succeeded: int
    failed: int
    sheet_url: str
    current_url: Optional[str] = None
