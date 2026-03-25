"""
Farmatodo Colombia — Brand Scraper

Purpose: Extract all brands sold on farmatodo.com.co
Method: Algolia API (public search-only credentials from frontend)
Output: List of brand names with product counts → Supabase retail_store_brands

Index: products (Algolia)
Facet: marca
Strategy: Query per department to bypass the 1000-facet-value limit
"""

import os
import sys
import json
import requests
from typing import Dict, List, Tuple
from datetime import datetime, timezone

_TOOLS_DIR = os.path.join(os.path.dirname(__file__), '..', '..')
if _TOOLS_DIR not in sys.path:
    sys.path.insert(0, _TOOLS_DIR)

# Algolia public credentials (embedded in farmatodo.com.co frontend)
ALGOLIA_APP_ID = "VCOJEYD2PO"
ALGOLIA_API_KEY = "eb9544fe7bfe7ec4c1aa5e5bf7740feb"
ALGOLIA_INDEX = "products"

STORE_NAME = "Farmatodo"
STORE_COUNTRY = "COL"
STORE_URL = "https://www.farmatodo.com.co"

# Departments to iterate (each can return up to 1000 brands)
DEPARTMENTS = [
    "Salud y medicamentos",
    "Cuidado personal",
    "Belleza",
    "Alimentos y bebidas",
    "Hogar, mascotas y otros.",
    "Bebés y maternidad",
    "Bienestar sexual",
    "Librería",
]


def scrape_brands() -> Dict:
    """
    Extract all brands from Farmatodo Colombia via Algolia.

    Returns:
        Dict with:
            - success: bool
            - data: {brands: [{name, product_count}], total: int, store: str}
            - error: str or None
    """
    url = f"https://{ALGOLIA_APP_ID.lower()}-dsn.algolia.net/1/indexes/{ALGOLIA_INDEX}/query"
    headers = {
        "X-Algolia-Application-Id": ALGOLIA_APP_ID,
        "X-Algolia-API-Key": ALGOLIA_API_KEY,
        "Content-Type": "application/json",
    }

    all_brands: Dict[str, int] = {}

    try:
        # Query each department to bypass 1000-value facet limit
        for dept in DEPARTMENTS:
            payload = {
                "query": "",
                "hitsPerPage": 0,
                "facets": ["marca"],
                "maxValuesPerFacet": 1000,
                "facetFilters": [f"departments:{dept}"],
            }
            resp = requests.post(url, headers=headers, json=payload, timeout=15)
            resp.raise_for_status()
            brands = resp.json().get("facets", {}).get("marca", {})
            for name, count in brands.items():
                all_brands[name] = all_brands.get(name, 0) + count

        # Also query without department filter to catch any stragglers
        payload = {
            "query": "",
            "hitsPerPage": 0,
            "facets": ["marca"],
            "maxValuesPerFacet": 1000,
        }
        resp = requests.post(url, headers=headers, json=payload, timeout=15)
        resp.raise_for_status()
        general_brands = resp.json().get("facets", {}).get("marca", {})
        for name, count in general_brands.items():
            if name not in all_brands:
                all_brands[name] = count

        # Build sorted list
        brand_list = [
            {"name": name, "product_count": count}
            for name, count in sorted(all_brands.items(), key=lambda x: x[1], reverse=True)
        ]

        return {
            "success": True,
            "data": {
                "brands": brand_list,
                "total": len(brand_list),
                "store": STORE_NAME,
                "country": STORE_COUNTRY,
            },
            "error": None,
        }

    except Exception as e:
        return {
            "success": False,
            "data": {},
            "error": f"Farmatodo scraper error: {str(e)}",
        }


def save_to_supabase(brands: List[Dict]) -> bool:
    """Save scraped brands to retail_store_brands table."""
    try:
        from export.supabase_writer import get_client
        from retail.store_registry import normalize_name

        client = get_client()

        # Get or create the store record
        stores = client.select(
            "retail_department_stores",
            eq={"name": STORE_NAME},
            limit=1,
        )
        if not stores:
            # Create the store entry
            stores = client.insert("retail_department_stores", {
                "name": STORE_NAME,
                "name_normalized": normalize_name(STORE_NAME),
                "country": STORE_COUNTRY,
                "website_url": STORE_URL,
                "scraper_active": True,
                "scraper_config": json.dumps({
                    "type": "algolia",
                    "app_id": ALGOLIA_APP_ID,
                    "index": ALGOLIA_INDEX,
                    "facet": "marca",
                }),
            })

        store_id = stores[0]["id"]

        # Batch upsert brands (in chunks of 100)
        rows = [
            {
                "store_id": store_id,
                "brand_name": b["name"],
                "brand_name_normalized": normalize_name(b["name"]),
                "source_url": STORE_URL,
            }
            for b in brands
            if b["name"] and normalize_name(b["name"])
        ]

        total_upserted = 0
        errors = 0
        chunk_size = 50
        for i in range(0, len(rows), chunk_size):
            chunk = rows[i:i + chunk_size]
            try:
                client.upsert("retail_store_brands", chunk, on_conflict="store_id,brand_name_normalized")
                total_upserted += len(chunk)
            except Exception as chunk_err:
                # Fallback: insert one by one to skip bad rows
                for row in chunk:
                    try:
                        client.upsert("retail_store_brands", row, on_conflict="store_id,brand_name_normalized")
                        total_upserted += 1
                    except Exception:
                        errors += 1
            if (i + chunk_size) % 500 == 0:
                print(f"    ... {total_upserted} saved, {errors} errors")

        # Update last_scraped_at
        import requests as _requests
        _requests.patch(
            f"{client.rest_url}/retail_department_stores",
            headers=client.headers,
            params={"id": f"eq.{store_id}"},
            json={"last_scraped_at": datetime.now(timezone.utc).isoformat()},
            timeout=15,
        )

        print(f"  Saved {total_upserted} brands to Supabase for store '{STORE_NAME}'")
        return True

    except Exception as e:
        print(f"  [ERROR] Supabase save failed: {e}")
        return False


if __name__ == "__main__":
    print(f"Scraping brands from {STORE_NAME} ({STORE_URL})")
    print("=" * 60)

    result = scrape_brands()
    print(f"Success: {result['success']}")

    if result["success"]:
        data = result["data"]
        print(f"Total brands: {data['total']}")
        print(f"\nTop 30:")
        for b in data["brands"][:30]:
            print(f"  {b['product_count']:6d}  {b['name']}")

        # Save to Supabase
        print(f"\nSaving to Supabase...")
        save_to_supabase(data["brands"])
    else:
        print(f"Error: {result['error']}")
