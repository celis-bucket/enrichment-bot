"""
Farmacias Pasteur Colombia — Brand Scraper

Purpose: Extract all brands sold on farmaciaspasteur.com.co
Method: VTEX Catalog API (public endpoint, no auth needed)
Output: List of brand names → Supabase retail_store_brands

Platform: VTEX (account: pasteurio)
Endpoint: /api/catalog_system/pub/brand/list
"""

import os
import sys
import json
import requests
from typing import Dict, List
from datetime import datetime, timezone

_TOOLS_DIR = os.path.join(os.path.dirname(__file__), '..', '..')
if _TOOLS_DIR not in sys.path:
    sys.path.insert(0, _TOOLS_DIR)

STORE_NAME = "Farmacias Pasteur"
STORE_COUNTRY = "COL"
STORE_URL = "https://www.farmaciaspasteur.com.co"
BRAND_API = f"{STORE_URL}/api/catalog_system/pub/brand/list"


def scrape_brands() -> Dict:
    """
    Extract all active brands from Farmacias Pasteur via VTEX Catalog API.

    Returns:
        Dict with:
            - success: bool
            - data: {brands: [{name, vtex_id, is_active}], total: int, store: str}
            - error: str or None
    """
    try:
        resp = requests.get(
            BRAND_API,
            headers={"Accept": "application/json"},
            timeout=30,
        )
        resp.raise_for_status()
        raw_brands = resp.json()

        # Filter to active brands only
        brand_list = [
            {
                "name": b["name"].strip(),
                "vtex_id": b.get("id"),
                "is_active": b.get("isActive", True),
            }
            for b in raw_brands
            if b.get("isActive") and b.get("name", "").strip()
        ]

        return {
            "success": True,
            "data": {
                "brands": brand_list,
                "total": len(brand_list),
                "total_raw": len(raw_brands),
                "store": STORE_NAME,
                "country": STORE_COUNTRY,
            },
            "error": None,
        }

    except Exception as e:
        return {
            "success": False,
            "data": {},
            "error": f"Pasteur scraper error: {str(e)}",
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
            stores = client.insert("retail_department_stores", {
                "name": STORE_NAME,
                "name_normalized": normalize_name(STORE_NAME),
                "country": STORE_COUNTRY,
                "website_url": STORE_URL,
                "scraper_active": True,
                "scraper_config": json.dumps({
                    "type": "vtex",
                    "account": "pasteurio",
                    "endpoint": "/api/catalog_system/pub/brand/list",
                }),
            })

        store_id = stores[0]["id"]

        # Build rows
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

        # Batch upsert in chunks
        total_upserted = 0
        errors = 0
        chunk_size = 50
        for i in range(0, len(rows), chunk_size):
            chunk = rows[i:i + chunk_size]
            try:
                client.upsert("retail_store_brands", chunk, on_conflict="store_id,brand_name_normalized")
                total_upserted += len(chunk)
            except Exception:
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

        print(f"  Saved {total_upserted} brands to Supabase for store '{STORE_NAME}' ({errors} errors)")
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
        print(f"Total active brands: {data['total']} (of {data['total_raw']} total)")
        print(f"\nFirst 30 (alphabetical):")
        for b in sorted(data["brands"], key=lambda x: x["name"])[:30]:
            print(f"  {b['name']}")

        print(f"\nSaving to Supabase...")
        save_to_supabase(data["brands"])
    else:
        print(f"Error: {result['error']}")
