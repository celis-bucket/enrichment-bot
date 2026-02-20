"""
Canonical Enrichment Result Schema

Single source of truth for the enrichment output contract.
Every enrichment run returns an EnrichmentResult dataclass.
SHEET_HEADERS defines the Google Sheets column order.
"""

from dataclasses import dataclass, field, fields, asdict
from typing import Optional
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
    # APOLLO (null for Phase 1)
    "contact_name",
    "contact_email",
    "company_linkedin",
    "number_employes",
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

    # APOLLO (null for Phase 1)
    contact_name: Optional[str] = None
    contact_email: Optional[str] = None
    company_linkedin: Optional[str] = None
    number_employes: Optional[int] = None          # Apollo estimated_num_employees; None = not found

    # EXECUTION META
    tool_coverage_pct: Optional[float] = None    # 0-1
    total_runtime_sec: Optional[float] = None
    cost_estimate_usd: Optional[float] = None
    workflow_execution_log: Optional[str] = None  # JSON string

    def to_dict(self) -> dict:
        """Convert to flat dict."""
        return asdict(self)

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


# Sanity check: field count must match header count
assert len(SHEET_HEADERS) == len(fields(EnrichmentResult)), (
    f"SHEET_HEADERS ({len(SHEET_HEADERS)}) != EnrichmentResult fields ({len(fields(EnrichmentResult))}). "
    "They must stay in sync."
)
