"""
Falabella Colombia — Brand Scraper

Purpose: Extract all brands sold on falabella.com.co
Method: Next.js __NEXT_DATA__ brand facets from search pages
Output: List of brand names → Supabase retail_store_brands

Platform: Next.js (custom Falabella BFF)
Strategy: Search by broad product terms, extract "Marca" facet values from __NEXT_DATA__,
          union all results across searches.
"""

import os
import sys
import json
import time
import requests
from typing import Dict, List, Set
from datetime import datetime, timezone
from bs4 import BeautifulSoup

_TOOLS_DIR = os.path.join(os.path.dirname(__file__), '..', '..')
if _TOOLS_DIR not in sys.path:
    sys.path.insert(0, _TOOLS_DIR)

STORE_NAME = "Falabella"
STORE_COUNTRY = "COL"
STORE_URL = "https://www.falabella.com.co"
SEARCH_URL = f"{STORE_URL}/falabella-co/search"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "text/html",
}

# Broad search terms designed to cover all product departments.
# Each search returns up to ~900 brand facet values.
SEARCH_TERMS = [
    # Core categories
    "ropa", "zapatos", "tecnologia", "hogar", "belleza", "deporte",
    "juguetes", "muebles", "cocina", "mascotas", "bebe", "salud",
    "alimentos", "herramientas", "jardin", "auto", "libros",
    "electrodomesticos", "celular", "computador", "televisor",
    "perfume", "reloj", "maleta", "cama", "sofa", "bicicleta",
    # Extended coverage
    "pintura", "iluminacion", "colchon", "lavadora", "nevera",
    "horno", "aspiradora", "ventilador", "aire", "jeans",
    "camiseta", "vestido", "pantalon", "chaqueta", "tenis",
    "sandalias", "botas", "accesorios", "joyeria", "gafas",
    "mochila", "bolso", "decoracion", "cortina", "alfombra",
    "lampara", "silla", "escritorio", "impresora", "audifonos",
    "parlante", "camara", "consola", "shampoo", "crema", "maquillaje",
]


def _extract_brands_from_search(term: str) -> Set[str]:
    """Extract brand names from a single Falabella search page."""
    brands = set()
    try:
        r = requests.get(SEARCH_URL, params={"Ntt": term}, headers=HEADERS, timeout=20)
        if r.status_code != 200:
            return brands

        soup = BeautifulSoup(r.text, "html.parser")
        script = soup.find("script", id="__NEXT_DATA__")
        if not script or not script.string:
            return brands

        data = json.loads(script.string)
        facets = data.get("props", {}).get("pageProps", {}).get("facets", [])

        for facet in facets:
            if facet.get("name") == "Marca":
                for value in facet.get("values", []):
                    title = value.get("title", "").strip()
                    if title:
                        brands.add(title)
                break

    except Exception:
        pass

    return brands


def scrape_brands() -> Dict:
    """
    Extract all brands from Falabella Colombia by searching across product categories.

    Returns:
        Dict with:
            - success: bool
            - data: {brands: [{name}], total: int, store: str}
            - error: str or None
    """
    try:
        all_brands: Set[str] = set()

        for i, term in enumerate(SEARCH_TERMS):
            new_brands = _extract_brands_from_search(term)
            before = len(all_brands)
            all_brands.update(new_brands)
            added = len(all_brands) - before

            if (i + 1) % 10 == 0 or i == len(SEARCH_TERMS) - 1:
                print(f"    ... {i + 1}/{len(SEARCH_TERMS)} searches, {len(all_brands)} brands")

            time.sleep(0.25)  # Be polite

        brand_list = [{"name": name} for name in sorted(all_brands, key=str.lower)]

        return {
            "success": True,
            "data": {
                "brands": brand_list,
                "total": len(brand_list),
                "searches": len(SEARCH_TERMS),
                "store": STORE_NAME,
                "country": STORE_COUNTRY,
            },
            "error": None,
        }

    except Exception as e:
        return {
            "success": False,
            "data": {},
            "error": f"Falabella scraper error: {str(e)}",
        }


def save_to_supabase(brands: List[Dict]) -> bool:
    """Save scraped brands to retail_store_brands table."""
    try:
        from export.supabase_writer import get_client
        from retail.store_registry import normalize_name

        client = get_client()

        # Get the store record (should already exist from seed data)
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
                    "type": "nextjs_search_facets",
                    "search_terms": len(SEARCH_TERMS),
                }),
            })

        store_id = stores[0]["id"]

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
    print(f"\nSuccess: {result['success']}")

    if result["success"]:
        data = result["data"]
        print(f"Total brands: {data['total']} (from {data['searches']} searches)")
        print(f"\nSample (first 20):")
        for b in data["brands"][:20]:
            print(f"  {b['name']}")

        print(f"\nSaving to Supabase...")
        save_to_supabase(data["brands"])
    else:
        print(f"Error: {result['error']}")
