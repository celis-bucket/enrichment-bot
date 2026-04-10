"""
Marketplace Presence Detection Tool

Purpose: Detect if a brand sells on marketplaces relevant to its geography
  COL: MercadoLibre, Rappi
  MEX: MercadoLibre, Amazon, Walmart, Liverpool, Coppel, TikTok Shop
Inputs: HTML content, domain, brand name, geography
Outputs: Binary presence per marketplace + evidence
Dependencies: tools/core/google_search.py, re, bs4

Detection strategies:
1. Check brand website HTML for outbound links to marketplaces
2. Google site-restricted search on each marketplace domain
3. Rappi (COL only): only searched for CPG categories
4. TikTok Shop (MEX only): HTML links + TikTok profile bio + Google fallback
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
        "MEX": "amazon.com.mx",
    },
    "rappi": {
        "COL": "rappi.com.co",
    },
    "walmart": {
        "MEX": "walmart.com.mx",
    },
    "liverpool": {
        "MEX": "liverpool.com.mx",
    },
    "coppel": {
        "MEX": "coppel.com",
    },
    "tiktok_shop": {
        "MEX": "shop.tiktok.com",
    },
}

# Which marketplaces to evaluate per country
MARKETPLACES_BY_COUNTRY = {
    "COL": ["mercadolibre", "rappi"],
    "MEX": ["mercadolibre", "amazon", "walmart", "liverpool", "coppel", "tiktok_shop"],
}
# When geography is unknown, evaluate all
ALL_MARKETPLACES = ["mercadolibre", "amazon", "rappi", "walmart", "liverpool", "coppel", "tiktok_shop"]

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
    "walmart": [
        r'walmart\.com\.mx',
        r'super\.walmart\.com\.mx',
    ],
    "liverpool": [
        r'liverpool\.com\.mx',
    ],
    "coppel": [
        r'coppel\.com',
    ],
    "tiktok_shop": [
        r'shop\.tiktok\.com',
        r'tiktok\.com/@[^/]+/shop',
        r'tiktok\.com/shop',
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
                # Only match actual <a href> links, not plain text mentions
                url_found = None
                for link in all_links:
                    if re.search(pattern, link, re.IGNORECASE):
                        url_found = link
                        break
                if url_found:
                    results[marketplace] = {
                        "found": True,
                        "source": "html_link",
                        "url": url_found,
                        "snippet": url_found[:80],
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

            # If we have organic results on the marketplace domain, require at least 2
            # AND brand name must appear in at least one result title to reduce false positives
            marketplace_results = [o for o in organic if site_domain in o.get("link", "").lower()]
            brand_in_title = any(
                brand_lower in o.get("title", "").lower() for o in marketplace_results
            )
            if len(marketplace_results) >= 2 and brand_in_title:
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


def _check_tiktok_profile_for_shop(tiktok_profile_data: Optional[Dict]) -> bool:
    """
    Check if TikTok profile data contains a shop link (bio or bio_link).

    Args:
        tiktok_profile_data: Profile dict from SearchAPI tiktok_profile engine.

    Returns:
        True if a TikTok Shop link is found in the profile.
    """
    if not tiktok_profile_data:
        return False
    try:
        # Check bio text
        bio = str(tiktok_profile_data.get("bio", "") or "").lower()
        if "shop.tiktok.com" in bio or "tiktok.com/shop" in bio:
            return True

        # Check bio_link field
        bio_link = str(tiktok_profile_data.get("bio_link", "") or "").lower()
        if "shop.tiktok.com" in bio_link or "tiktok.com/shop" in bio_link:
            return True

        # Check links array (some profile responses include this)
        links = tiktok_profile_data.get("links", []) or []
        for link in links:
            link_str = str(link).lower() if link else ""
            if "shop.tiktok.com" in link_str or "tiktok.com/shop" in link_str:
                return True
    except Exception:
        pass
    return False


def detect_marketplaces(
    html: str,
    domain: str,
    brand_name: str,
    geography: Optional[str] = None,
    category: Optional[str] = None,
    shopping_marketplaces: Optional[Dict[str, bool]] = None,
    tiktok_profile_data: Optional[Dict] = None,
) -> Dict[str, Any]:
    """
    Detect brand presence on marketplaces relevant to the brand's geography.

    COL: MercadoLibre, Rappi
    MEX: MercadoLibre, Amazon, Walmart, Liverpool, Coppel, TikTok Shop

    Args:
        html: Brand website HTML content
        domain: Brand domain
        brand_name: Brand/company name
        geography: 'COL', 'MEX', or None (searches all)
        category: Product category (used to decide if Rappi is relevant)
        shopping_marketplaces: Pre-detected marketplaces from Google Shopping
        tiktok_profile_data: TikTok profile dict (optional, for shop link detection)

    Returns:
        Dict with:
            - success: bool
            - data: {on_mercadolibre, on_amazon, on_rappi|on_walmart|on_liverpool|on_coppel|on_tiktok_shop, evidence}
            - error: str or None
    """
    try:
        evidence_list = []
        shop_mp = shopping_marketplaces or {}

        # Determine which marketplaces to evaluate based on geography
        mp_list = MARKETPLACES_BY_COUNTRY.get(geography, ALL_MARKETPLACES)

        # Step 1: Check HTML for outbound marketplace links
        html_links = _check_html_links(html) if html else {}

        # Step 2: Detect each marketplace
        results = {}
        for mp_key in mp_list:
            mp_label = _marketplace_label(mp_key)
            output_key = f"on_{mp_key}"

            # Rappi: skip if category is not CPG-relevant
            if mp_key == "rappi":
                skip_rappi = category and category not in RAPPI_RELEVANT_CATEGORIES
                if skip_rappi:
                    evidence_list.append(f"{mp_label}: skipped (category '{category}' not CPG)")
                    results[output_key] = None
                    continue

            # Check if already detected via Google Shopping
            if shop_mp.get(mp_label):
                results[output_key] = True
                evidence_list.append(f"{mp_label}: detected via Google Shopping")
                continue

            # Check HTML links
            html_match = html_links.get(mp_key, {})
            if html_match.get("found"):
                results[output_key] = True
                evidence_list.append(f"{mp_label}: link found in website HTML ({html_match.get('snippet', '')})")
                continue

            # TikTok Shop: check profile bio before Google fallback
            if mp_key == "tiktok_shop" and _check_tiktok_profile_for_shop(tiktok_profile_data):
                results[output_key] = True
                evidence_list.append(f"{mp_label}: shop link found in TikTok profile bio")
                continue

            # Google site: search fallback
            search_result = _search_marketplace(brand_name, mp_key, domain, geography)
            results[output_key] = search_result["found"]
            evidence_list.append(f"{mp_label}: {search_result['evidence']}")

        results["evidence"] = evidence_list

        return {
            "success": True,
            "data": results,
            "error": None,
        }

    except Exception as e:
        return {
            "success": False,
            "data": {},
            "error": f"Marketplace detection error: {str(e)}",
        }


def _marketplace_label(mp_key: str) -> str:
    """Convert marketplace key to display label for evidence and Shopping matching."""
    labels = {
        "mercadolibre": "MercadoLibre",
        "amazon": "Amazon",
        "rappi": "Rappi",
        "walmart": "Walmart",
        "liverpool": "Liverpool",
        "coppel": "Coppel",
        "tiktok_shop": "TikTok Shop",
    }
    return labels.get(mp_key, mp_key.capitalize())


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
        for key, val in data.items():
            if key.startswith("on_"):
                print(f"  {key}: {val}")
        print(f"\n  Evidence:")
        for ev in data["evidence"]:
            print(f"    - {ev}")
    else:
        print(f"  Error: {result['error']}")
