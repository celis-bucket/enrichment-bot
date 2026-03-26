"""
Google Shopping Sellers Detection Tool

Purpose: Detect where a brand's products are sold using Google Shopping results
Inputs: brand_name, geography (COL/MEX)
Outputs: Classified sellers (marketplaces, multibrand stores, other retailers)
Dependencies: SearchAPI (SEARCHAPI_API_KEY), tools/retail/store_registry

One SearchAPI query returns up to 40 products with seller names, replacing
3-6 Serper site: queries for marketplace detection and complementing
multi-brand store detection.
"""

import os
import sys
import re
import requests
from typing import Dict, Any, Optional, List, Set

_TOOLS_DIR = os.path.join(os.path.dirname(__file__), "..")
if _TOOLS_DIR not in sys.path:
    sys.path.insert(0, _TOOLS_DIR)

from retail.store_registry import normalize_name

# Known marketplace sellers per country (normalized → canonical)
MARKETPLACE_NAMES_COL = {
    "mercadolibre": "MercadoLibre",
    "mercado libre": "MercadoLibre",
}

MARKETPLACE_NAMES_MEX = {
    "mercadolibre": "MercadoLibre",
    "mercado libre": "MercadoLibre",
    "amazon": "Amazon",
    "amazoncom": "Amazon",
    "amazon mexico": "Amazon",
    "liverpool": "Liverpool",
    "coppel": "Coppel",
    "walmart": "Walmart",
}

# Fallback: union of both for when geography is unknown
MARKETPLACE_NAMES_ALL = {**MARKETPLACE_NAMES_COL, **MARKETPLACE_NAMES_MEX}

# Country code mapping for SearchAPI gl parameter
GEO_TO_GL = {
    "COL": "co",
    "MEX": "mx",
}


def detect_sellers_from_shopping(
    brand_name: str,
    geography: Optional[str] = None,
    supabase_client=None,
) -> Dict[str, Any]:
    """
    Query Google Shopping for a brand and classify the sellers found.

    Args:
        brand_name: Brand name to search
        geography: 'COL', 'MEX', or None (defaults to COL)
        supabase_client: Optional Supabase client for store name lookups

    Returns:
        Dict with:
            - success: bool
            - data: {
                all_sellers: [str],
                multibrand_found: [str],
                marketplaces_found: {marketplace_name: bool},
                other_retailers: [str],
                product_count: int,
                brand_product_count: int,
              }
            - error: str or None
    """
    api_key = os.getenv("SEARCHAPI_API_KEY")
    if not api_key:
        try:
            from dotenv import load_dotenv
            load_dotenv()
            api_key = os.getenv("SEARCHAPI_API_KEY")
        except ImportError:
            pass
    if not api_key:
        return {"success": False, "data": {}, "error": "SEARCHAPI_API_KEY not set"}

    gl = GEO_TO_GL.get(geography, "co")

    try:
        resp = requests.get(
            "https://www.searchapi.io/api/v1/search",
            params={
                "engine": "google_shopping",
                "q": f'"{brand_name}"',
                "api_key": api_key,
                "gl": gl,
                "hl": "es",
            },
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        return {"success": False, "data": {}, "error": f"SearchAPI error: {e}"}

    results = data.get("shopping_results", [])
    if not results:
        return {
            "success": True,
            "data": {
                "all_sellers": [],
                "multibrand_found": [],
                "marketplaces_found": {},
                "other_retailers": [],
                "product_count": 0,
                "brand_product_count": 0,
            },
            "error": None,
        }

    # Filter results: only products whose title contains the brand name
    brand_norm = normalize_name(brand_name).replace(" ", "")
    brand_products = []
    for r in results:
        title_norm = normalize_name(r.get("title", "")).replace(" ", "")
        if brand_norm in title_norm or title_norm in brand_norm:
            brand_products.append(r)

    # If strict filter returns too few, use all results
    if len(brand_products) < 3 and len(results) >= 3:
        brand_products = results

    # Extract unique sellers
    raw_sellers: Dict[str, int] = {}  # seller_name → count of products
    for r in brand_products:
        seller = r.get("seller", "").strip()
        if seller:
            raw_sellers[seller] = raw_sellers.get(seller, 0) + 1

    # Load known store names from Supabase
    known_stores: Dict[str, str] = {}
    if supabase_client:
        try:
            from retail.store_registry import get_store_names_set
            known_stores = get_store_names_set(supabase_client, country=geography)
        except Exception:
            pass

    # If no DB, use fallback from detect_multibrand_stores
    if not known_stores:
        try:
            from retail.detect_multibrand_stores import _get_fallback_stores
            known_stores = _get_fallback_stores(geography)
        except Exception:
            pass

    # Classify each seller
    multibrand_found: Set[str] = set()
    marketplaces_found: Dict[str, bool] = {}
    other_retailers: Set[str] = set()
    brand_norm_name = normalize_name(brand_name)

    for seller_raw, count in raw_sellers.items():
        seller_norm = normalize_name(seller_raw)

        # Skip if it's the brand itself
        if _is_self_seller(seller_norm, brand_norm_name):
            continue

        # Check marketplaces (country-specific list)
        mp_names = (
            MARKETPLACE_NAMES_COL if geography == "COL"
            else MARKETPLACE_NAMES_MEX if geography == "MEX"
            else MARKETPLACE_NAMES_ALL
        )
        marketplace = _match_marketplace(seller_norm, mp_names)
        if marketplace:
            marketplaces_found[marketplace] = True
            continue

        # Check known multibrand stores
        store_match = _match_known_store(seller_norm, known_stores)
        if store_match:
            multibrand_found.add(store_match)
            continue

        # Everything else is an "other retailer"
        other_retailers.add(seller_raw)

    return {
        "success": True,
        "data": {
            "all_sellers": sorted(raw_sellers.keys()),
            "multibrand_found": sorted(multibrand_found),
            "marketplaces_found": marketplaces_found,
            "other_retailers": sorted(other_retailers),
            "product_count": len(results),
            "brand_product_count": len(brand_products),
        },
        "error": None,
    }


def _is_self_seller(seller_norm: str, brand_norm: str) -> bool:
    """Check if the seller is the brand itself."""
    # Exact match or one contains the other
    if seller_norm == brand_norm:
        return True
    if len(seller_norm) >= 4 and len(brand_norm) >= 4:
        if seller_norm in brand_norm or brand_norm in seller_norm:
            return True
    return False


def _match_marketplace(
    seller_norm: str, mp_names: Dict[str, str],
) -> Optional[str]:
    """Check if seller matches a known marketplace. Returns canonical name or None."""
    seller_nospace = seller_norm.replace(" ", "")
    for pattern, canonical in mp_names.items():
        pattern_nospace = pattern.replace(" ", "")
        if pattern_nospace in seller_nospace or seller_nospace in pattern_nospace:
            return canonical
    return None


def _match_known_store(
    seller_norm: str, known_stores: Dict[str, str],
) -> Optional[str]:
    """Match seller against known department/multi-brand stores.

    Uses substring + fuzzy matching to handle variations like
    'Farmacia Pasteur' matching 'Farmacias Pasteur', or
    'Farmatodo CO' matching 'farmatodo'.
    """
    seller_nospace = seller_norm.replace(" ", "")
    for store_norm, store_canonical in known_stores.items():
        store_nospace = store_norm.replace(" ", "")
        # Exact
        if seller_norm == store_norm:
            return store_canonical
        # Substring (both directions, min 4 chars)
        if len(store_nospace) >= 4 and len(seller_nospace) >= 4:
            if store_nospace in seller_nospace or seller_nospace in store_nospace:
                return store_canonical

    # Fuzzy fallback for close matches (e.g., "farmacia pasteur" vs "farmacias pasteur")
    if len(seller_norm) >= 5:
        try:
            from rapidfuzz import fuzz
            for store_norm, store_canonical in known_stores.items():
                if len(store_norm) < 4:
                    continue
                score = fuzz.ratio(
                    seller_norm.replace(" ", ""),
                    store_norm.replace(" ", ""),
                )
                if score >= 85:
                    return store_canonical
        except ImportError:
            pass

    return None


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()

    import json

    brand = sys.argv[1] if len(sys.argv) > 1 else "Savvy"
    geo = sys.argv[2] if len(sys.argv) > 2 else "COL"

    print(f"Google Shopping Sellers: {brand} ({geo})")
    print("=" * 60)

    # Try with Supabase
    sb_client = None
    try:
        from export.supabase_writer import get_client
        sb_client = get_client()
    except Exception:
        pass

    result = detect_sellers_from_shopping(brand, geo, supabase_client=sb_client)

    if result["success"]:
        d = result["data"]
        print(f"Products found: {d['product_count']} total, {d['brand_product_count']} matching brand")
        print(f"\nAll sellers ({len(d['all_sellers'])}):")
        for s in d["all_sellers"]:
            print(f"  - {s}")
        print(f"\nMultibrand stores: {d['multibrand_found']}")
        print(f"Marketplaces: {d['marketplaces_found']}")
        print(f"Other retailers: {d['other_retailers']}")
    else:
        print(f"Error: {result['error']}")
