"""
Marketplace Presence Detection Tool

Purpose: Detect if a brand sells on MercadoLibre, Amazon, and Rappi
Inputs: HTML content, domain, brand name, geography
Outputs: Binary presence per marketplace + evidence
Dependencies: tools/core/google_search.py, re, bs4

Detection strategies:
1. Check brand website HTML for outbound links to marketplaces
2. Google site-restricted search on each marketplace domain
3. Rappi search (for CPG categories: Alimentos, Bebidas, Cosmeticos-belleza, etc.)
"""

import re
import sys
import os
from typing import Dict, Any, Optional, List
from bs4 import BeautifulSoup

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from core.google_search import google_search

# Marketplace domains by country
MARKETPLACE_DOMAINS = {
    "mercadolibre": {
        "COL": "mercadolibre.com.co",
        "MEX": "mercadolibre.com.mx",
    },
    "amazon": {
        "COL": "amazon.com",        # No .co TLD for Amazon Colombia
        "MEX": "amazon.com.mx",
    },
    "rappi": {
        "COL": "rappi.com.co",
        "MEX": "rappi.com.mx",
    },
}

# Categories where Rappi presence is most relevant (CPG / consumer goods)
RAPPI_RELEVANT_CATEGORIES = {
    "Alimentos", "Alimentos refrigerados", "Bebidas", "Cosmeticos-belleza",
    "Salud y Bienestar", "Suplementos", "Mascotas", "Farmacéutica",
    "Hogar", "Infantiles y Bebés",
}

# Patterns to find marketplace links in HTML
MARKETPLACE_LINK_PATTERNS = {
    "mercadolibre": [
        r'mercadolibre\.com\.\w+',
        r'mercadolib\.re',
        r'articulo\.mercadolibre',
    ],
    "amazon": [
        r'amazon\.com\.mx',
        r'amazon\.com/[^\s"\']+',
        r'amzn\.to',
    ],
    "rappi": [
        r'rappi\.com\.\w+',
    ],
}


def _check_html_links(html: str) -> Dict[str, Dict]:
    """
    Check brand website HTML for outbound links to marketplaces.

    Returns dict per marketplace with found URLs.
    """
    results = {}
    try:
        soup = BeautifulSoup(html, 'html.parser')
        all_links = []
        for tag in soup.find_all('a', href=True):
            all_links.append(tag['href'])
        # Also check for marketplace references in text/images
        html_lower = html.lower()

        for marketplace, patterns in MARKETPLACE_LINK_PATTERNS.items():
            for pattern in patterns:
                match = re.search(pattern, html_lower)
                if match:
                    # Find the actual URL from <a> tags
                    url_found = None
                    for link in all_links:
                        if re.search(pattern, link, re.IGNORECASE):
                            url_found = link
                            break
                    results[marketplace] = {
                        "found": True,
                        "source": "html_link",
                        "url": url_found,
                        "snippet": match.group(0),
                    }
                    break  # One match per marketplace is enough
    except Exception:
        pass

    return results


def _search_marketplace(brand_name: str, marketplace: str, domain: str,
                         geography: Optional[str] = None) -> Dict[str, Any]:
    """
    Search for a brand on a specific marketplace using Google site: search.

    Returns:
        Dict with found (bool), url (str|None), total_results (int), evidence (str)
    """
    domains_by_geo = MARKETPLACE_DOMAINS.get(marketplace, {})

    # Determine which marketplace domain(s) to search
    if geography and geography in domains_by_geo:
        search_domains = [domains_by_geo[geography]]
    else:
        # Search all available country domains
        search_domains = list(domains_by_geo.values())

    for site_domain in search_domains:
        # Build query: site:mercadolibre.com.co "brand name"
        query = f'site:{site_domain} "{brand_name}"'

        # Set country code for localized results
        country_code = None
        if "com.co" in site_domain:
            country_code = "co"
        elif "com.mx" in site_domain:
            country_code = "mx"

        result = google_search(query, num_results=5, country=country_code)

        if not result["success"]:
            continue

        data = result["data"]
        total_results = data.get("search_information", {}).get("total_results", 0)
        organic = data.get("organic", [])

        # Serper sometimes returns total_results=0 even when organic results exist,
        # so check organic list directly instead of relying on total_results
        if organic:
            brand_lower = brand_name.lower()
            for item in organic[:5]:
                title = item.get("title", "").lower()
                snippet = item.get("snippet", "").lower()
                link = item.get("link", "").lower()
                # Check if the result is actually on the marketplace domain
                if site_domain not in link:
                    continue
                if brand_lower in title or brand_lower in snippet or brand_lower in link:
                    return {
                        "found": True,
                        "url": item.get("link"),
                        "total_results": max(total_results, len(organic)),
                        "evidence": f"Found on {site_domain}: {item.get('title', '')[:80]}",
                    }

            # If we have organic results on the marketplace domain, it's a signal
            marketplace_results = [o for o in organic if site_domain in o.get("link", "").lower()]
            if len(marketplace_results) >= 1:
                return {
                    "found": True,
                    "url": marketplace_results[0].get("link"),
                    "total_results": max(total_results, len(marketplace_results)),
                    "evidence": f"{len(marketplace_results)} results on {site_domain}",
                }

    return {
        "found": False,
        "url": None,
        "total_results": 0,
        "evidence": f"No results on {marketplace}",
    }


def detect_marketplaces(
    html: str,
    domain: str,
    brand_name: str,
    geography: Optional[str] = None,
    category: Optional[str] = None,
    shopping_marketplaces: Optional[Dict[str, bool]] = None,
) -> Dict[str, Any]:
    """
    Detect brand presence on MercadoLibre, Amazon, and Rappi.

    Args:
        html: Brand website HTML content
        domain: Brand domain
        brand_name: Brand/company name
        geography: 'COL', 'MEX', or None (searches both)
        category: Product category (used to decide if Rappi is relevant)

    Returns:
        Dict with:
            - success: bool
            - data: {on_mercadolibre, on_amazon, on_rappi, evidence}
            - error: str or None
    """
    try:
        evidence_list = []
        shop_mp = shopping_marketplaces or {}

        # Step 1: Check HTML for outbound marketplace links
        html_links = _check_html_links(html) if html else {}

        # Step 2: Google site: searches for each marketplace
        # Skip Serper query if Google Shopping already detected the marketplace

        # MercadoLibre
        if shop_mp.get("MercadoLibre"):
            on_mercadolibre = True
            evidence_list.append("MercadoLibre: detected via Google Shopping")
        else:
            ml_html = html_links.get("mercadolibre", {})
            if ml_html.get("found"):
                on_mercadolibre = True
                evidence_list.append(f"MercadoLibre: link found in website HTML ({ml_html.get('snippet', '')})")
            else:
                ml_search = _search_marketplace(brand_name, "mercadolibre", domain, geography)
                on_mercadolibre = ml_search["found"]
                evidence_list.append(f"MercadoLibre: {ml_search['evidence']}")

        # Amazon
        if shop_mp.get("Amazon"):
            on_amazon = True
            evidence_list.append("Amazon: detected via Google Shopping")
        else:
            amz_html = html_links.get("amazon", {})
            if amz_html.get("found"):
                on_amazon = True
                evidence_list.append(f"Amazon: link found in website HTML ({amz_html.get('snippet', '')})")
            else:
                amz_search = _search_marketplace(brand_name, "amazon", domain, geography)
                on_amazon = amz_search["found"]
                evidence_list.append(f"Amazon: {amz_search['evidence']}")

        # Rappi — only search if category is relevant or category is unknown
        on_rappi = None
        skip_rappi = category and category not in RAPPI_RELEVANT_CATEGORIES
        if shop_mp.get("Rappi"):
            on_rappi = True
            evidence_list.append("Rappi: detected via Google Shopping")
        elif skip_rappi:
            evidence_list.append(f"Rappi: skipped (category '{category}' not CPG)")
            on_rappi = None
        else:
            rappi_html = html_links.get("rappi", {})
            if rappi_html.get("found"):
                on_rappi = True
                evidence_list.append(f"Rappi: link found in website HTML")
            else:
                rappi_search = _search_marketplace(brand_name, "rappi", domain, geography)
                on_rappi = rappi_search["found"]
                evidence_list.append(f"Rappi: {rappi_search['evidence']}")

        return {
            "success": True,
            "data": {
                "on_mercadolibre": on_mercadolibre,
                "on_amazon": on_amazon,
                "on_rappi": on_rappi,
                "evidence": evidence_list,
            },
            "error": None,
        }

    except Exception as e:
        return {
            "success": False,
            "data": {},
            "error": f"Marketplace detection error: {str(e)}",
        }


if __name__ == "__main__":
    test_brand = sys.argv[1] if len(sys.argv) > 1 else "Republic Cosmetics"
    test_geo = sys.argv[2] if len(sys.argv) > 2 else None

    print("Marketplace Presence Detection")
    print("=" * 60)
    print(f"Brand: {test_brand}")
    print(f"Geography: {test_geo or 'All'}")

    result = detect_marketplaces("", "", test_brand, geography=test_geo)

    print(f"\nSuccess: {result['success']}")
    if result["success"]:
        data = result["data"]
        print(f"  MercadoLibre: {data['on_mercadolibre']}")
        print(f"  Amazon: {data['on_amazon']}")
        print(f"  Rappi: {data['on_rappi']}")
        print(f"\n  Evidence:")
        for ev in data["evidence"]:
            print(f"    - {ev}")
    else:
        print(f"  Error: {result['error']}")
