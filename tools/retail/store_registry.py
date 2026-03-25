"""
Store Registry — Supabase interface for retail department stores

Purpose: Read/write to retail_department_stores and retail_store_brands tables
Inputs: Supabase client, store/brand queries
Outputs: Store lists, brand lookups
Dependencies: tools/logistics/supabase_client.py, unicodedata
"""

import re
import unicodedata
from typing import List, Dict, Optional


def normalize_name(name: str) -> str:
    """
    Normalize a name for matching: lowercase, strip accents, remove punctuation.

    Examples:
        'Palacio de Hierro' -> 'palacio de hierro'
        'República Cosmetics' -> 'republica cosmetics'
        "L'Oréal" -> 'loreal'
    """
    if not name:
        return ""
    # Lowercase
    text = name.strip().lower()
    # Remove accents
    text = unicodedata.normalize('NFD', text)
    text = ''.join(c for c in text if unicodedata.category(c) != 'Mn')
    # Remove punctuation except spaces
    text = re.sub(r"[^\w\s]", "", text)
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text


def get_all_stores(client, country: Optional[str] = None) -> List[Dict]:
    """
    Load all department stores from Supabase.

    Args:
        client: SupabaseClient instance
        country: Optional filter ('COL' or 'MEX')

    Returns:
        List of store dicts with id, name, name_normalized, country, website_url, scraper_active
    """
    eq = {"country": country} if country else None
    return client.select(
        "retail_department_stores",
        columns="id,name,name_normalized,country,website_url,scraper_active",
        eq=eq,
        order="country,name",
    )


def find_brand_in_stores(client, brand_name: str, country: Optional[str] = None) -> List[Dict]:
    """
    Check if a brand exists in any department store's scraped brand list.

    Args:
        client: SupabaseClient instance
        brand_name: Brand name to search for
        country: Optional country filter

    Returns:
        List of dicts with store_name, store_country, detected_at
    """
    normalized = normalize_name(brand_name)
    if not normalized:
        return []

    # Query retail_store_brands joined with store info
    # PostgREST supports foreign key joins via select syntax
    rows = client.select(
        "retail_store_brands",
        columns="brand_name,detected_at,store_id,retail_department_stores(name,country)",
        eq={"brand_name_normalized": normalized},
    )

    results = []
    for row in rows:
        store_info = row.get("retail_department_stores", {})
        store_country = store_info.get("country", "")

        # Apply country filter if specified
        if country and store_country != country:
            continue

        results.append({
            "store_name": store_info.get("name", ""),
            "store_country": store_country,
            "brand_name": row.get("brand_name", ""),
            "detected_at": row.get("detected_at", ""),
        })

    return results


def get_store_names_set(client, country: Optional[str] = None) -> Dict[str, str]:
    """
    Get a mapping of normalized store names to canonical names.
    Used for matching store mentions in brand websites.

    Returns:
        Dict mapping normalized_name -> canonical_name
        e.g. {'falabella': 'Falabella', 'palacio de hierro': 'Palacio de Hierro'}
    """
    stores = get_all_stores(client, country=country)
    return {s["name_normalized"]: s["name"] for s in stores}
