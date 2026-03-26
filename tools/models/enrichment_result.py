"""
Canonical Enrichment Result Schema

Single source of truth for the enrichment output contract.
Every enrichment run returns an EnrichmentResult dataclass.
SHEET_HEADERS defines the Google Sheets column order.
"""

import json
from dataclasses import dataclass, field, fields, asdict
from typing import Optional, List, Dict, Any
from uuid import uuid4


ALLOWED_CATEGORIES = [
    "Accesorios",
    "Alimentos",
    "Alimentos refrigerados",
    "Autopartes",
    "Bebidas",
    "Cosmeticos-belleza",
    "Deporte",
    "Electrónicos",
    "Farmacéutica",
    "Hogar",
    "Infantiles y Bebés",
    "Joyeria/Bisuteria",
    "Juguetes",
    "Juguetes Sexuales",
    "Libros",
    "Mascotas",
    "Papeleria",
    "Ropa",
    "Salud y Bienestar",
    "Suplementos",
    "Tecnología",
    "Textil Hogar",
    "Zapatos",
]

# Column order for Google Sheets — must match EnrichmentResult field names exactly.
SHEET_HEADERS = [
    # IDENTITY
    "run_id",
    "batch_id",
    "clean_url",
    "domain",
    "company_name",
    # PLATFORM
    "platform",
    "platform_confidence",
    # GEOGRAPHY
    "geography",
    "geography_confidence",
    # CATEGORY (LLM)
    "category",
    "category_confidence",
    "category_evidence",
    # SOCIAL (Instagram)
    "instagram_url",
    "ig_followers",
    "ig_engagement_rate",
    "ig_size_score",
    "ig_health_score",
    "ig_is_verified",
    # SOCIAL (Facebook & TikTok)
    "fb_followers",
    "tiktok_followers",
    # CATALOG
    "product_count",
    "avg_price",
    "price_range_min",
    "price_range_max",
    "currency",
    # TRAFFIC
    "estimated_monthly_visits",
    "traffic_confidence",
    "signals_used",
    # GOOGLE DEMAND
    "brand_demand_score",
    "site_serp_coverage_score",
    "google_confidence",
    # FULFILLMENT
    "fulfillment_provider",
    "fulfillment_confidence",
    # META ADS
    "meta_active_ads_count",
    # TIKTOK ADS
    "tiktok_active_ads_count",
    # APOLLO
    "contact_name",
    "contact_email",
    "company_linkedin",
    "number_employes",
    "founded_year",
    # HUBSPOT CRM
    "hubspot_company_id",
    "hubspot_company_url",
    "hubspot_deal_count",
    "hubspot_deal_stage",
    "hubspot_contact_exists",
    "hubspot_lifecycle_label",
    "hubspot_last_contacted",
    # POTENTIAL SCORING
    "ecommerce_size_score",
    "retail_size_score",
    "combined_size_score",
    "fit_score",
    "overall_potential_score",
    "potential_tier",
    # ENRICHMENT LITE
    "enrichment_type",
    "lite_triage_score",
    "worth_full_enrichment",
    # LEAD SOURCE
    "source",
    "hs_lead_stage",
    "hs_lead_label",
    "hs_lead_owner",
    "hs_last_lost_deal_date",
    # EXECUTION META
    "tool_coverage_pct",
    "total_runtime_sec",
    "cost_estimate_usd",
    "workflow_execution_log",
]


@dataclass
class EnrichmentResult:
    """Canonical output for a single company enrichment run."""

    # IDENTITY
    run_id: str = field(default_factory=lambda: str(uuid4()))
    batch_id: Optional[str] = None
    clean_url: Optional[str] = None
    domain: Optional[str] = None
    company_name: Optional[str] = None          # LLM-extracted commercial brand name

    # PLATFORM
    platform: Optional[str] = None              # shopify|vtex|woocommerce|magento|other|unknown
    platform_confidence: Optional[float] = None  # 0-1

    # GEOGRAPHY
    geography: Optional[str] = None             # COL|MEX|UNKNOWN
    geography_confidence: Optional[float] = None  # 0-1

    # CATEGORY (LLM-derived)
    category: Optional[str] = None              # one of ALLOWED_CATEGORIES or empty
    category_confidence: Optional[float] = None  # 0-1
    category_evidence: Optional[str] = None

    # SOCIAL (Instagram)
    instagram_url: Optional[str] = None
    ig_followers: Optional[int] = None
    ig_engagement_rate: Optional[float] = None
    ig_size_score: Optional[int] = None         # 0-100
    ig_health_score: Optional[int] = None       # 0-100
    ig_is_verified: Optional[int] = None        # 0 or 1

    # SOCIAL (Facebook & TikTok)
    fb_followers: Optional[int] = None
    tiktok_followers: Optional[int] = None

    # CATALOG
    product_count: Optional[int] = None
    avg_price: Optional[float] = None
    price_range_min: Optional[float] = None
    price_range_max: Optional[float] = None
    currency: Optional[str] = None

    # TRAFFIC
    estimated_monthly_visits: Optional[int] = None
    traffic_confidence: Optional[float] = None   # 0-1
    signals_used: Optional[str] = None

    # GOOGLE DEMAND
    brand_demand_score: Optional[float] = None       # 0-1
    site_serp_coverage_score: Optional[float] = None  # 0-1
    google_confidence: Optional[float] = None         # 0-1

    # FULFILLMENT
    fulfillment_provider: Optional[str] = None
    fulfillment_confidence: Optional[float] = None    # 0-1

    # META ADS
    meta_active_ads_count: Optional[int] = None       # active ads in Meta Ad Library; None = not found

    # TIKTOK ADS
    tiktok_active_ads_count: Optional[int] = None     # active ads in TikTok Ads Library; None = not found

    # APOLLO
    contact_name: Optional[str] = None
    contact_email: Optional[str] = None
    company_linkedin: Optional[str] = None
    number_employes: Optional[int] = None          # Apollo estimated_num_employees; None = not found
    founded_year: Optional[int] = None             # Apollo org founded_year; None = not found
    contacts_list: Optional[List[Dict[str, Any]]] = None  # Full contacts list (not exported to Sheet)

    # HUBSPOT CRM
    hubspot_company_id: Optional[str] = None        # HubSpot company record ID
    hubspot_company_url: Optional[str] = None        # Direct link to HubSpot record
    hubspot_deal_count: Optional[int] = None         # Number of associated deals
    hubspot_deal_stage: Optional[str] = None         # Most advanced deal stage name
    hubspot_contact_exists: Optional[int] = None     # 1 if primary contact in HubSpot, 0 if not
    hubspot_lifecycle_label: Optional[str] = None    # Cliente, Lead Ventas, etc.
    hubspot_last_contacted: Optional[str] = None     # ISO date of last contact

    # POTENTIAL SCORING
    ecommerce_size_score: Optional[int] = None       # 0-100
    retail_size_score: Optional[int] = None           # 0-100
    combined_size_score: Optional[int] = None         # 0-100
    fit_score: Optional[int] = None                   # 0-100
    overall_potential_score: Optional[int] = None      # 0-100
    potential_tier: Optional[str] = None               # Extraordinary|Very Good|Good|Low

    # ENRICHMENT LITE
    enrichment_type: Optional[str] = None              # "lite" | "full"
    lite_triage_score: Optional[int] = None            # 0-100
    worth_full_enrichment: Optional[bool] = None       # True/False

    # LEAD SOURCE
    source: Optional[str] = None                       # "hubspot_leads" | None
    hs_lead_stage: Optional[str] = None                # Lead pipeline stage name
    hs_lead_label: Optional[str] = None                # WARM, HOT, etc.
    hs_lead_owner: Optional[str] = None                # Lead owner name (resolved)
    hs_last_lost_deal_date: Optional[str] = None       # Date of last Cierre Perdido

    # EXECUTION META
    tool_coverage_pct: Optional[float] = None    # 0-1
    total_runtime_sec: Optional[float] = None
    cost_estimate_usd: Optional[float] = None
    workflow_execution_log: Optional[str] = None  # JSON string

    def to_dict(self) -> dict:
        """Convert to flat dict."""
        return asdict(self)

    def to_supabase_dict(self, prediction: dict = None) -> dict:
        """Convert to dict matching the Supabase enriched_companies schema.

        Args:
            prediction: Optional dict with predicted_orders_p10/p50/p90 and prediction_confidence.

        Returns:
            Dict ready for Supabase upsert (None values stripped, JSON fields parsed).
        """
        d = self.to_dict()
        # Parse workflow_execution_log from JSON string to list for JSONB column
        wlog = d.get("workflow_execution_log")
        if isinstance(wlog, str):
            try:
                d["workflow_execution_log"] = json.loads(wlog)
            except (json.JSONDecodeError, TypeError):
                d["workflow_execution_log"] = []
        # Merge prediction fields if provided
        if prediction:
            d["predicted_orders_p10"] = prediction.get("predicted_orders_p10")
            d["predicted_orders_p50"] = prediction.get("predicted_orders_p50")
            d["predicted_orders_p90"] = prediction.get("predicted_orders_p90")
            d["prediction_confidence"] = prediction.get("prediction_confidence")
        # Strip None values so Supabase uses column defaults
        return {k: v for k, v in d.items() if v is not None}

    def to_row(self) -> list:
        """Convert to a list matching SHEET_HEADERS order. None -> empty string."""
        d = self.to_dict()
        row = []
        for header in SHEET_HEADERS:
            val = d.get(header)
            if val is None:
                row.append("")
            elif isinstance(val, float):
                row.append(round(val, 4))
            else:
                row.append(val)
        return row


# Fields not exported to Google Sheets (nested/non-scalar)
_NON_SHEET_FIELDS = {"contacts_list"}

# Sanity check: field count (minus non-sheet fields) must match header count
_sheet_field_count = len([f for f in fields(EnrichmentResult) if f.name not in _NON_SHEET_FIELDS])
assert len(SHEET_HEADERS) == _sheet_field_count, (
    f"SHEET_HEADERS ({len(SHEET_HEADERS)}) != EnrichmentResult sheet fields ({_sheet_field_count}). "
    "They must stay in sync."
)
