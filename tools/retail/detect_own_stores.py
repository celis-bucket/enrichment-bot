"""
Own Physical Stores Detection Tool

Purpose: Detect if a brand has its own physical stores, with count per country
Inputs: HTML content, domain, brand name, geography, IG bio, knowledge graph
Outputs: has_own_stores (bool), own_store_count_col (int), own_store_count_mex (int)
Dependencies: tools/core/web_scraper.py, tools/core/google_search.py, re, bs4

Detection strategies:
1. Scan HTML for store locator pages (links in nav/footer)
2. Scrape store locator page and count addresses/locations
3. Serper Places search for physical locations per country
4. Google Business Profile from knowledge graph (if available)
5. Instagram bio mentions of stores/locations
"""

import re
import sys
import os
from typing import Dict, Any, Optional, List
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from core.web_scraper import scrape_website
from core.google_search import google_search
from retail.store_registry import normalize_name

# Patterns for store locator links
STORE_LOCATOR_LINK_PATTERNS = [
    r'tiendas?\b',
    r'sucursal',
    r'nuestras?\s*tiendas?',
    r'store[\s-]*locator',
    r'stores?\b',
    r'ubicacion',
    r'puntos?\s*de\s*venta',
    r'encuentra\s*tu\s*tienda',
    r'find\s*(?:a\s*)?store',
    r'locations?\b',
    r'sedes?\b',
    r'showroom',
]

STORE_LOCATOR_HREF_PATTERNS = [
    r'/tiendas?\b',
    r'/sucursal',
    r'/store[-_]?locator',
    r'/stores?\b',
    r'/ubicacion',
    r'/locations?\b',
    r'/puntos-de-venta',
    r'/showroom',
    r'/sedes?\b',
    r'/encuentra',
]

# Patterns that indicate a store address in page content
ADDRESS_PATTERNS = [
    # Colombian addresses
    r'(?:calle|carrera|cra|cl|transversal|diagonal|avenida|av)\s*\.?\s*\d+',
    r'(?:local|l\.?)\s*\d+',
    r'(?:centro\s*comercial|c\.?\s*c\.?)\s+\w+',
    # Mexican addresses
    r'(?:colonia|col\.?)\s+\w+',
    r'(?:avenida|av\.?)\s+\w+\s+#?\s*\d+',
    r'(?:plaza|paseo|boulevard|blvd)\s+\w+',
    r'c\.?\s*p\.?\s*\d{5}',  # Código postal mexicano
    # Generic
    r'(?:tel|teléfono|phone)[.:\s]*[\+\(]?\d[\d\s\-\(\)]{7,}',
    r'(?:lunes|martes|miércoles|jueves|viernes|sábado|domingo)\s*(?:a|-)\s*(?:lunes|martes|miércoles|jueves|viernes|sábado|domingo)',
]

# Colombia cities
COL_CITIES = [
    'bogotá', 'bogota', 'medellín', 'medellin', 'cali', 'barranquilla',
    'cartagena', 'bucaramanga', 'pereira', 'manizales', 'santa marta',
    'ibagué', 'ibague', 'villavicencio', 'pasto', 'montería', 'monteria',
    'neiva', 'armenia', 'sincelejo', 'popayán', 'popayan', 'tunja',
    'valledupar', 'cúcuta', 'cucuta',
]

# Mexico cities
MEX_CITIES = [
    'ciudad de méxico', 'cdmx', 'guadalajara', 'monterrey', 'puebla',
    'cancún', 'cancun', 'tijuana', 'león', 'leon', 'mérida', 'merida',
    'querétaro', 'queretaro', 'san luis potosí', 'aguascalientes',
    'toluca', 'chihuahua', 'morelia', 'hermosillo', 'saltillo',
    'culiacán', 'culiacan', 'oaxaca', 'veracruz', 'playa del carmen',
]


def _scan_html_for_store_links(html: str, base_url: str) -> List[Dict]:
    """Find links that suggest a store locator page."""
    candidates = []
    try:
        soup = BeautifulSoup(html, 'html.parser')
        for a_tag in soup.find_all('a', href=True):
            href = a_tag['href'].strip()
            text = a_tag.get_text(strip=True).lower()
            href_lower = href.lower()

            matched = False
            # Check anchor text
            for pattern in STORE_LOCATOR_LINK_PATTERNS:
                if re.search(pattern, text, re.IGNORECASE):
                    candidates.append({
                        "url": urljoin(base_url, href),
                        "anchor_text": a_tag.get_text(strip=True)[:100],
                        "match_type": "text",
                    })
                    matched = True
                    break

            if not matched:
                for pattern in STORE_LOCATOR_HREF_PATTERNS:
                    if re.search(pattern, href_lower):
                        candidates.append({
                            "url": urljoin(base_url, href),
                            "anchor_text": a_tag.get_text(strip=True)[:100],
                            "match_type": "href",
                        })
                        break

        # VTEX store-locator app: rendered client-side, no <a> tags in HTML.
        # Detect the app and add the standard route as a candidate.
        if not candidates and 'store-locator@' in html:
            candidates.append({
                "url": urljoin(base_url, "/stores"),
                "anchor_text": "VTEX store-locator app",
                "match_type": "vtex_app",
            })

    except Exception:
        pass

    # Deduplicate
    seen = set()
    unique = []
    for c in candidates:
        if c["url"] not in seen:
            seen.add(c["url"])
            unique.append(c)
    return unique


def _count_stores_from_page(url: str) -> Dict[str, Any]:
    """
    Scrape a store locator page and count locations per country.

    Returns:
        {total: int, col_count: int, mex_count: int, evidence: str}
    """
    result = scrape_website(url, timeout=20, parse_html=True)
    if not result["success"]:
        return {"total": 0, "col_count": 0, "mex_count": 0, "evidence": "Failed to scrape"}

    html = result["data"]["html"]
    soup = result["data"].get("soup")
    text = soup.get_text(separator=' ', strip=True).lower() if soup else html.lower()

    # Count addresses by looking for repeated address patterns
    address_count = 0
    for pattern in ADDRESS_PATTERNS:
        matches = re.findall(pattern, text, re.IGNORECASE)
        address_count += len(matches)

    # Count by looking for map markers or location list items
    # Many store locators use structured elements
    location_elements = 0
    if soup:
        # Look for repeated elements that suggest individual stores
        for selector in ['.store', '.location', '.tienda', '.sucursal',
                         '[data-store]', '[data-location]', '.store-item',
                         '.location-item', '.punto-venta']:
            elements = soup.select(selector)
            if len(elements) > 1:
                location_elements = max(location_elements, len(elements))

    # Count Colombian city mentions
    col_cities_found = set()
    for city in COL_CITIES:
        if city in text:
            col_cities_found.add(city)

    # Count Mexican city mentions
    mex_cities_found = set()
    for city in MEX_CITIES:
        if city in text:
            mex_cities_found.add(city)

    # Estimate total — best signal is structured elements, then addresses, then cities
    if location_elements > 0:
        total = location_elements
    elif address_count > 2:
        total = address_count // 2  # Addresses often appear in pairs (street + phone)
    else:
        total = len(col_cities_found) + len(mex_cities_found)

    # Rough country split
    col_count = len(col_cities_found) if col_cities_found else 0
    mex_count = len(mex_cities_found) if mex_cities_found else 0

    # If we have a total but no city breakdown, assign to the country with more mentions
    if total > 0 and col_count == 0 and mex_count == 0:
        # Check for country-level mentions
        if 'colombia' in text:
            col_count = total
        elif 'méxico' in text or 'mexico' in text:
            mex_count = total

    evidence = (
        f"Parsed store page: {total} locations estimated "
        f"(elements={location_elements}, addresses={address_count}, "
        f"COL cities={len(col_cities_found)}, MEX cities={len(mex_cities_found)})"
    )

    return {
        "total": total,
        "col_count": col_count,
        "mex_count": mex_count,
        "evidence": evidence,
    }


def _places_search(brand_name: str, country: str) -> Dict[str, Any]:
    """
    Use Serper Places search to find physical stores.

    Args:
        brand_name: Brand name to search
        country: 'co' or 'mx' country code

    Returns:
        {count: int, places: list, evidence: str}
    """
    query = f'"{brand_name}" tienda'
    result = google_search(query, search_type="places", country=country, num_results=20)

    if not result["success"]:
        return {"count": 0, "places": [], "evidence": "Places search failed"}

    places = result["data"].get("places", [])

    # Filter places that actually match the brand name
    # Normalize both sides (strip accents, punctuation, spaces) to handle
    # domain-as-name cases like "olecapilar" vs "Olé Capilar"
    brand_norm = normalize_name(brand_name).replace(" ", "")
    matching = []
    for place in places:
        title_norm = normalize_name(place.get("title", "")).replace(" ", "")
        if brand_norm in title_norm or title_norm in brand_norm:
            matching.append({
                "name": place.get("title", ""),
                "address": place.get("address", ""),
                "rating": place.get("rating"),
                "reviews": place.get("reviews"),
            })

    return {
        "count": len(matching),
        "places": matching[:20],
        "evidence": f"Places search: {len(matching)} matching locations (of {len(places)} results)",
    }


def _check_ig_bio(ig_bio: str) -> Dict[str, Any]:
    """
    Check Instagram bio for store/location mentions.

    Returns:
        {has_stores_signal: bool, evidence: str}
    """
    if not ig_bio:
        return {"has_stores_signal": False, "evidence": "No IG bio available"}

    bio_lower = ig_bio.lower()
    store_patterns = [
        r'tienda\s*f[ií]sica',
        r'tiendas?\s*en\s+',
        r'sucursal',
        r'visítanos\s*en',
        r'visitanos\s*en',
        r'showroom',
        r'punto\s*de\s*venta',
        r'\d+\s*tiendas?',
        r'stores?\s*in\s+',
        r'physical\s*store',
    ]

    for pattern in store_patterns:
        match = re.search(pattern, bio_lower)
        if match:
            return {
                "has_stores_signal": True,
                "evidence": f"IG bio mention: '{match.group(0)}'",
            }

    return {"has_stores_signal": False, "evidence": "No store mentions in IG bio"}


def _check_knowledge_graph(knowledge_graph: Optional[Dict]) -> Dict[str, Any]:
    """
    Check Google Business Profile from knowledge graph for physical presence.

    Returns:
        {has_physical_signal: bool, evidence: str}
    """
    if not knowledge_graph:
        return {"has_physical_signal": False, "evidence": "No knowledge graph data"}

    kg_type = knowledge_graph.get("type", "").lower()
    attributes = knowledge_graph.get("attributes", {})

    # Check for physical address
    has_address = bool(attributes.get("Address") or attributes.get("Dirección"))

    # Check for store-related type
    store_types = ["store", "shop", "tienda", "retail", "boutique", "showroom"]
    is_store_type = any(st in kg_type for st in store_types)

    if has_address or is_store_type:
        evidence_parts = []
        if has_address:
            addr = attributes.get("Address") or attributes.get("Dirección", "")
            evidence_parts.append(f"Address: {addr}")
        if is_store_type:
            evidence_parts.append(f"Type: {kg_type}")
        return {
            "has_physical_signal": True,
            "evidence": f"Google Business Profile: {'; '.join(evidence_parts)}",
        }

    return {"has_physical_signal": False, "evidence": "No physical signals in knowledge graph"}


def detect_own_stores(
    html: str,
    domain: str,
    brand_name: str,
    geography: Optional[str] = None,
    ig_bio: Optional[str] = None,
    knowledge_graph: Optional[Dict] = None,
) -> Dict[str, Any]:
    """
    Detect if a brand has its own physical stores.

    Args:
        html: Brand website HTML content
        domain: Brand domain
        brand_name: Brand/company name
        geography: 'COL', 'MEX', or None
        ig_bio: Instagram bio text (optional)
        knowledge_graph: Knowledge graph dict from Google Demand step (optional)

    Returns:
        Dict with:
            - success: bool
            - data: {has_own_stores, own_store_count_col, own_store_count_mex, evidence}
            - error: str or None
    """
    try:
        evidence_list = []
        has_own_stores = False
        col_count = 0
        mex_count = 0

        base_url = f"https://{domain}"

        # Strategy 1: Scan HTML for store locator links
        candidates = _scan_html_for_store_links(html, base_url) if html else []

        if candidates:
            evidence_list.append(f"Found {len(candidates)} store locator link(s)")

            # Scrape the top candidate to count stores
            for candidate in candidates[:2]:
                page_data = _count_stores_from_page(candidate["url"])
                evidence_list.append(page_data["evidence"])

                if page_data["total"] > 0:
                    has_own_stores = True
                    col_count = max(col_count, page_data["col_count"])
                    mex_count = max(mex_count, page_data["mex_count"])
                    break

        # Strategy 2: Serper Places search
        countries_to_search = []
        if geography == "COL":
            countries_to_search = ["co"]
        elif geography == "MEX":
            countries_to_search = ["mx"]
        else:
            countries_to_search = ["co", "mx"]

        for country_code in countries_to_search:
            places_result = _places_search(brand_name, country_code)
            evidence_list.append(places_result["evidence"])

            if places_result["count"] > 0:
                has_own_stores = True
                if country_code == "co":
                    col_count = max(col_count, places_result["count"])
                elif country_code == "mx":
                    mex_count = max(mex_count, places_result["count"])

        # Strategy 3: Instagram bio
        ig_result = _check_ig_bio(ig_bio)
        if ig_result["has_stores_signal"]:
            has_own_stores = True
            evidence_list.append(ig_result["evidence"])
        elif ig_bio:
            evidence_list.append(ig_result["evidence"])

        # Strategy 4: Google Business Profile
        kg_result = _check_knowledge_graph(knowledge_graph)
        if kg_result["has_physical_signal"]:
            has_own_stores = True
            evidence_list.append(kg_result["evidence"])
        elif knowledge_graph:
            evidence_list.append(kg_result["evidence"])

        return {
            "success": True,
            "data": {
                "has_own_stores": has_own_stores,
                "own_store_count_col": col_count if col_count > 0 else None,
                "own_store_count_mex": mex_count if mex_count > 0 else None,
                "evidence": evidence_list,
            },
            "error": None,
        }

    except Exception as e:
        return {
            "success": False,
            "data": {},
            "error": f"Own stores detection error: {str(e)}",
        }


if __name__ == "__main__":
    test_url = sys.argv[1] if len(sys.argv) > 1 else "https://republiccosmetics.com"
    test_brand = sys.argv[2] if len(sys.argv) > 2 else "Republic Cosmetics"

    print("Own Physical Stores Detection")
    print("=" * 60)
    print(f"URL: {test_url}")
    print(f"Brand: {test_brand}")

    scrape_result = scrape_website(test_url, parse_html=False)
    html_content = scrape_result["data"]["html"] if scrape_result["success"] else ""
    domain_name = urlparse(test_url).netloc.replace("www.", "")

    result = detect_own_stores(html_content, domain_name, test_brand)

    print(f"\nSuccess: {result['success']}")
    if result["success"]:
        data = result["data"]
        print(f"  Has own stores: {data['has_own_stores']}")
        print(f"  Store count COL: {data['own_store_count_col']}")
        print(f"  Store count MEX: {data['own_store_count_mex']}")
        print(f"\n  Evidence:")
        for ev in data["evidence"]:
            print(f"    - {ev}")
    else:
        print(f"  Error: {result['error']}")
