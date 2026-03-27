"""
Potential Scoring Module

Purpose: Compute company potential scores from enrichment + retail data.
Inputs: Dict with enrichment fields (from Supabase row or EnrichmentResult).
Outputs: 6 scores — ecommerce_size, retail_size, combined_size, fit, overall_potential, tier.
Dependencies: None (stdlib math only).
"""

import math

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Marketplace sets per country (canonical names as they appear in marketplace_names)
MEXICO_MARKETPLACES = {"Amazon", "MercadoLibre", "Liverpool", "Coppel", "Walmart", "TikTok Shop"}
COLOMBIA_MARKETPLACES = {"MercadoLibre", "Rappi", "Falabella", "Éxito", "Exito"}

# Category fit tiers
HIGH_FIT_CATEGORIES = {
    "Cosmeticos-belleza", "Accesorios", "Ropa", "Zapatos", "Joyeria/Bisuteria",
    "Suplementos", "Mascotas", "Infantiles y Bebés", "Juguetes",
    "Juguetes Sexuales", "Deporte", "Papeleria", "Libros",
}
MEDIUM_FIT_CATEGORIES = {
    "Tecnología", "Electrónicos", "Salud y Bienestar", "Farmacéutica", "Textil Hogar",
}
LOW_FIT_CATEGORIES = {
    "Hogar", "Autopartes", "Alimentos", "Alimentos refrigerados", "Bebidas",
}

# Piecewise linear breakpoints for orders → score mapping
_ORDERS_BREAKPOINTS = [(0, 0), (500, 40), (1000, 60), (2000, 80), (5000, 100)]

# Potential tiers
TIER_EXTRAORDINARY = "Extraordinary"
TIER_VERY_GOOD = "Very Good"
TIER_GOOD = "Good"
TIER_LOW = "Low"


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _piecewise_linear(value: float, breakpoints: list[tuple[float, float]]) -> float:
    """Interpolate value through piecewise linear breakpoints."""
    if value <= breakpoints[0][0]:
        return breakpoints[0][1]
    for i in range(1, len(breakpoints)):
        x0, y0 = breakpoints[i - 1]
        x1, y1 = breakpoints[i]
        if value <= x1:
            t = (value - x0) / (x1 - x0)
            return y0 + t * (y1 - y0)
    return breakpoints[-1][1]


def _own_store_score(count: int) -> float:
    """Map own store count to 0-100 score."""
    if count <= 0:
        return 0.0
    if count == 1:
        return 30.0
    if count == 2:
        return 45.0
    if count <= 4:
        return 60.0
    if count <= 9:
        return 80.0
    return 100.0


# ---------------------------------------------------------------------------
# Score Functions
# ---------------------------------------------------------------------------

def calculate_ecommerce_size_score(
    predicted_orders_p90: int | None,
    brand_demand_score: float | None,
) -> int:
    """
    E-commerce size score (0-100).
    80% from P90 orders (piecewise linear), 20% from Google brand demand.
    """
    orders_component = 0.0
    if predicted_orders_p90 is not None and predicted_orders_p90 > 0:
        orders_component = _piecewise_linear(predicted_orders_p90, _ORDERS_BREAKPOINTS)

    demand_component = 0.0
    if brand_demand_score is not None:
        demand_component = brand_demand_score * 100

    return round(0.80 * orders_component + 0.20 * demand_component)


def calculate_retail_size_score(
    has_multibrand_stores: bool | None,
    multibrand_store_names: list | None,
    has_own_stores: bool | None,
    own_store_count: int | None,
    on_mercadolibre: bool | None = None,
    on_amazon: bool | None = None,
    on_rappi: bool | None = None,
    marketplace_names: list | None = None,
    geography: str | None = None,
    on_walmart: bool | None = None,
    on_liverpool: bool | None = None,
    on_coppel: bool | None = None,
    on_tiktok_shop: bool | None = None,
) -> int:
    """
    Retail size score (0-100).
    40% multibrand presence, 25% own stores, 35% marketplace count.
    """
    # --- Multibrand component (40%) ---
    multibrand_component = 0.0
    if has_multibrand_stores:
        n_stores = len(multibrand_store_names) if multibrand_store_names else 0
        if n_stores >= 3:
            multibrand_component = 100.0
        elif n_stores == 2:
            multibrand_component = 85.0
        elif n_stores == 1:
            multibrand_component = 70.0
        else:
            multibrand_component = 70.0  # has_multibrand but no names listed

    # --- Own stores component (25%) ---
    own_stores_component = 0.0
    if has_own_stores and own_store_count is not None:
        own_stores_component = _own_store_score(own_store_count)
    elif has_own_stores:
        own_stores_component = 30.0  # has stores but count unknown

    # --- Marketplace component (35%) ---
    # Collect all detected marketplaces from all sources
    detected_marketplaces: set[str] = set()

    # From boolean fields
    if on_mercadolibre:
        detected_marketplaces.add("MercadoLibre")
    if on_amazon:
        detected_marketplaces.add("Amazon")
    if on_rappi:
        detected_marketplaces.add("Rappi")
    if on_walmart:
        detected_marketplaces.add("Walmart")
    if on_liverpool:
        detected_marketplaces.add("Liverpool")
    if on_coppel:
        detected_marketplaces.add("Coppel")
    if on_tiktok_shop:
        detected_marketplaces.add("TikTok Shop")

    # From marketplace_names list (populated by retail enrichment)
    if marketplace_names:
        for name in marketplace_names:
            detected_marketplaces.add(name)

    # From multibrand_store_names — check if any are actually marketplaces
    if multibrand_store_names:
        country_mp = (
            COLOMBIA_MARKETPLACES if geography == "COL"
            else MEXICO_MARKETPLACES if geography == "MEX"
            else COLOMBIA_MARKETPLACES | MEXICO_MARKETPLACES
        )
        for name in multibrand_store_names:
            if name in country_mp:
                detected_marketplaces.add(name)

    # Count marketplaces relevant to this country
    if geography == "COL":
        relevant = COLOMBIA_MARKETPLACES
        # Normalize: "Éxito" and "Exito" are the same
        normalized = set()
        for mp in detected_marketplaces:
            if mp in ("Éxito", "Exito"):
                normalized.add("Éxito")
            else:
                normalized.add(mp)
        count = len(normalized & relevant)
        total = 4  # MercadoLibre, Rappi, Falabella, Éxito
    elif geography == "MEX":
        relevant = MEXICO_MARKETPLACES
        count = len(detected_marketplaces & relevant)
        total = 5  # Amazon, MercadoLibre, Liverpool, Coppel, Walmart
    else:
        # Unknown geography — use the larger set
        all_mp = COLOMBIA_MARKETPLACES | MEXICO_MARKETPLACES
        count = len(detected_marketplaces & all_mp)
        total = 5  # Use 5 as denominator

    marketplace_component = min(100.0, (count / max(total, 1)) * 100)

    return round(
        0.40 * multibrand_component
        + 0.25 * own_stores_component
        + 0.35 * marketplace_component
    )


def calculate_combined_size_score(
    ecommerce_size_score: int,
    retail_size_score: int,
) -> int:
    """
    Combined size score (0-100).
    Takes the max of ecommerce and retail, with a bonus if both are strong.
    """
    base = max(ecommerce_size_score, retail_size_score)
    bonus = min(20, 0.2 * min(ecommerce_size_score, retail_size_score))
    return min(100, round(base + bonus))


def calculate_fit_score(category: str | None) -> int:
    """
    Fit score (0-100) based on product category.
    Proxies product weight/type from category classification.
    """
    if not category:
        return 50  # neutral when unknown

    if category in HIGH_FIT_CATEGORIES:
        return 90
    elif category in MEDIUM_FIT_CATEGORIES:
        return 60
    elif category in LOW_FIT_CATEGORIES:
        return 25
    else:
        return 50  # unknown category


def calculate_overall_potential(
    combined_size_score: int,
    fit_score: int,
) -> int:
    """
    Overall potential score (0-100).
    65% size (how big), 35% fit (how good for Melonn).
    """
    return round(0.65 * combined_size_score + 0.35 * fit_score)


def determine_potential_tier(overall_score: int) -> str:
    """Map overall potential score to a human-readable tier."""
    if overall_score >= 80:
        return TIER_EXTRAORDINARY
    elif overall_score >= 60:
        return TIER_VERY_GOOD
    elif overall_score >= 40:
        return TIER_GOOD
    else:
        return TIER_LOW


# ---------------------------------------------------------------------------
# Convenience wrapper
# ---------------------------------------------------------------------------

def score_company(data: dict) -> dict:
    """
    Compute all potential scores from a dict of enrichment + retail fields.

    Accepts a Supabase row or EnrichmentResult.to_dict().
    Returns dict with 6 scoring fields ready for upsert.
    """
    geography = data.get("geography")

    # Pick the right own_store_count based on geography
    own_store_count = None
    if geography == "COL":
        own_store_count = data.get("own_store_count_col")
    elif geography == "MEX":
        own_store_count = data.get("own_store_count_mex")
    else:
        # Use whichever is available
        own_store_count = data.get("own_store_count_col") or data.get("own_store_count_mex")

    ecom = calculate_ecommerce_size_score(
        predicted_orders_p90=data.get("predicted_orders_p90"),
        brand_demand_score=data.get("brand_demand_score"),
    )

    retail = calculate_retail_size_score(
        has_multibrand_stores=data.get("has_multibrand_stores"),
        multibrand_store_names=data.get("multibrand_store_names"),
        has_own_stores=data.get("has_own_stores"),
        own_store_count=own_store_count,
        on_mercadolibre=data.get("on_mercadolibre"),
        on_amazon=data.get("on_amazon"),
        on_rappi=data.get("on_rappi"),
        on_walmart=data.get("on_walmart"),
        on_liverpool=data.get("on_liverpool"),
        on_coppel=data.get("on_coppel"),
        on_tiktok_shop=data.get("on_tiktok_shop"),
        marketplace_names=data.get("marketplace_names"),
        geography=geography,
    )

    combined = calculate_combined_size_score(ecom, retail)
    fit = calculate_fit_score(data.get("category"))
    overall = calculate_overall_potential(combined, fit)
    tier = determine_potential_tier(overall)

    return {
        "ecommerce_size_score": ecom,
        "retail_size_score": retail,
        "combined_size_score": combined,
        "fit_score": fit,
        "overall_potential_score": overall,
        "potential_tier": tier,
    }
