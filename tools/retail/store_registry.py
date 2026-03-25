"""
Store Registry — Supabase interface for retail department stores

Purpose: Read/write to retail_department_stores and retail_store_brands tables
Inputs: Supabase client, store/brand queries
Outputs: Store lists, brand lookups
Dependencies: tools/logistics/supabase_client.py, unicodedata
"""

import re
import time
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


# In-memory cache for full brand table (avoids repeated fetches in a single run)
_brand_cache: Dict[str, tuple] = {}
_CACHE_TTL = 300  # 5 minutes


def _fetch_all_brands(client, country: Optional[str] = None) -> List[Dict]:
    """Fetch all brands from retail_store_brands, cached in-memory.

    Paginates through PostgREST's default 1000-row limit to get all rows.
    """
    cache_key = country or "__all__"
    now = time.time()

    if cache_key in _brand_cache:
        ts, rows = _brand_cache[cache_key]
        if now - ts < _CACHE_TTL:
            return rows

    # Paginate to get all rows (PostgREST defaults to 1000)
    all_rows: List[Dict] = []
    page_size = 1000
    offset = 0
    columns = ("brand_name,brand_name_normalized,detected_at,store_id,"
               "retail_department_stores(name,country)")

    while True:
        import requests as _requests
        params = {
            "select": columns,
            "order": "id",
            "limit": str(page_size),
            "offset": str(offset),
        }
        resp = _requests.get(
            f"{client.rest_url}/retail_store_brands",
            headers=client.headers,
            params=params,
            timeout=30,
        )
        resp.raise_for_status()
        page = resp.json()
        all_rows.extend(page)
        if len(page) < page_size:
            break
        offset += page_size

    if country:
        all_rows = [
            r for r in all_rows
            if r.get("retail_department_stores", {}).get("country") == country
        ]

    _brand_cache[cache_key] = (now, all_rows)
    return all_rows


def find_brand_in_stores_fuzzy(
    client,
    brand_name: str,
    country: Optional[str] = None,
    domain: Optional[str] = None,
    ig_username: Optional[str] = None,
    apollo_name: Optional[str] = None,
) -> List[Dict]:
    """
    Fuzzy brand search across retail stores using a cascade strategy.

    Tries exact match first (fast), then generates candidate name variants,
    then falls back to token containment and fuzzy matching.

    Falls back to exact-only find_brand_in_stores() if no fuzzy match found.
    """
    from retail.fuzzy_brand_match import generate_candidate_names, fuzzy_match_brand

    # Stage 0: Try exact match first (fast, single DB query)
    exact = find_brand_in_stores(client, brand_name, country)
    if exact:
        return exact

    # Generate all candidate name variants
    candidates = generate_candidate_names(
        brand_name, domain=domain, ig_username=ig_username, apollo_name=apollo_name,
    )

    # Try exact match for each additional candidate (skip first if same as brand_name)
    primary_norm = normalize_name(brand_name)
    for candidate in candidates:
        if candidate == primary_norm:
            continue
        exact = find_brand_in_stores(client, candidate, country)
        if exact:
            return exact

    # Full table scan for fuzzy matching (cached in-memory)
    all_brands = _fetch_all_brands(client, country)
    if not all_brands:
        return []

    return fuzzy_match_brand(candidates, all_brands)


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
