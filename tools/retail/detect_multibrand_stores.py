"""
Multi-brand Store Detection Tool

Purpose: Detect if a brand is sold through department/multi-brand stores
Inputs: HTML content, domain, brand name, geography, IG bio
Outputs: has_multibrand_stores (bool), store_names (list from controlled vocabulary)
Dependencies: tools/core/web_scraper.py, tools/retail/store_registry.py, re, bs4

Detection strategies:
1. Brand website: find "where to buy" section with store logos/names
2. Supabase DB: check retail_store_brands for brand presence (populated by scrapers)
3. Instagram bio: mentions of department store names
"""

import re
import sys
import os
from typing import Dict, Any, Optional, List, Set
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from core.web_scraper import scrape_website

# Patterns for "where to buy" / retail partners pages
RETAILER_PAGE_LINK_PATTERNS = [
    r'donde\s*comprar',
    r'donde\s*encontrarnos',
    r'puntos?\s*de\s*venta',
    r'tiendas?\s*autorizad',
    r'nuestros?\s*aliados',
    r'nuestros?\s*retailers?',
    r'retail\s*partners?',
    r'where\s*to\s*buy',
    r'find\s*us',
    r'stockists?',
    r'stores?\s*(?:that\s*)?carry',
    r'encuent?ranos',
    r'nos\s*encuentras?\s*en',
]

RETAILER_PAGE_HREF_PATTERNS = [
    r'/donde-comprar',
    r'/puntos-de-venta',
    r'/tiendas-autorizadas',
    r'/aliados',
    r'/retailers?',
    r'/where-to-buy',
    r'/stockists?',
    r'/find-us',
    r'/encuentranos',
]


def _scan_html_for_retailer_pages(html: str, base_url: str) -> List[Dict]:
    """Find links to 'where to buy' or retail partner pages."""
    candidates = []
    try:
        soup = BeautifulSoup(html, 'html.parser')
        for a_tag in soup.find_all('a', href=True):
            href = a_tag['href'].strip()
            text = a_tag.get_text(strip=True).lower()
            href_lower = href.lower()

            for pattern in RETAILER_PAGE_LINK_PATTERNS:
                if re.search(pattern, text, re.IGNORECASE):
                    candidates.append({
                        "url": urljoin(base_url, href),
                        "anchor_text": a_tag.get_text(strip=True)[:100],
                    })
                    break

            if not any(c["url"] == urljoin(base_url, href) for c in candidates):
                for pattern in RETAILER_PAGE_HREF_PATTERNS:
                    if re.search(pattern, href_lower):
                        candidates.append({
                            "url": urljoin(base_url, href),
                            "anchor_text": a_tag.get_text(strip=True)[:100],
                        })
                        break
    except Exception:
        pass

    seen = set()
    unique = []
    for c in candidates:
        if c["url"] not in seen:
            seen.add(c["url"])
            unique.append(c)
    return unique


def _extract_store_names_from_page(
    url: str,
    known_stores: Dict[str, str],
) -> List[str]:
    """
    Scrape a retail partners page and extract store names.

    Matches against known_stores vocabulary.

    Args:
        url: Page URL to scrape
        known_stores: Dict mapping normalized_name -> canonical_name

    Returns:
        List of canonical store names found
    """
    result = scrape_website(url, timeout=20, parse_html=True)
    if not result["success"]:
        return []

    html = result["data"]["html"]
    soup = result["data"].get("soup")
    if not soup:
        return []

    found_stores: Set[str] = set()
    text_lower = soup.get_text(separator=' ', strip=True).lower()

    # Strategy A: Check text content for store names
    for normalized, canonical in known_stores.items():
        # Use word boundary matching to avoid false positives
        if re.search(r'\b' + re.escape(normalized) + r'\b', text_lower):
            found_stores.add(canonical)

    # Strategy B: Check image alt text (store logos)
    for img in soup.find_all('img', alt=True):
        alt_lower = img['alt'].strip().lower()
        for normalized, canonical in known_stores.items():
            if normalized in alt_lower:
                found_stores.add(canonical)

    # Strategy C: Check image src filenames (often contain store names)
    for img in soup.find_all('img', src=True):
        src_lower = img['src'].lower()
        for normalized, canonical in known_stores.items():
            # Only match longer names to avoid false positives from short names
            if len(normalized) >= 4 and normalized.replace(' ', '') in src_lower.replace('-', '').replace('_', ''):
                found_stores.add(canonical)

    # Strategy D: Check <a> hrefs wrapping images — many "where to buy" pages
    # use store logos as clickable images linking to the store's website.
    # The href URL domain/path often contains the store name.
    for a_tag in soup.find_all('a', href=True):
        # Only consider links that wrap images (store logo pattern)
        if not a_tag.find('img'):
            continue
        href = a_tag['href'].lower()
        # Skip internal links and empty anchors
        if not href.startswith('http'):
            continue
        for normalized, canonical in known_stores.items():
            if len(normalized) >= 3 and normalized.replace(' ', '') in href.replace('-', '').replace('_', ''):
                found_stores.add(canonical)

    return sorted(found_stores)


def _extract_store_names_from_homepage(
    html: str,
    known_stores: Dict[str, str],
) -> List[str]:
    """
    Check the homepage HTML for store logos/mentions.

    Some brands show retail partner logos directly on their homepage.
    """
    found_stores: Set[str] = set()
    try:
        soup = BeautifulSoup(html, 'html.parser')

        # Check for sections with multiple store-related images
        # Look for clusters of <img> tags near "where to buy" text
        text_lower = soup.get_text(separator=' ', strip=True).lower()

        # Quick check — if homepage mentions store names, match them
        for normalized, canonical in known_stores.items():
            if len(normalized) >= 5:  # Skip very short names to avoid false positives
                if re.search(r'\b' + re.escape(normalized) + r'\b', text_lower):
                    found_stores.add(canonical)

        # Check image alt text on homepage
        for img in soup.find_all('img', alt=True):
            alt_lower = img['alt'].strip().lower()
            for normalized, canonical in known_stores.items():
                if len(normalized) >= 4 and normalized in alt_lower:
                    found_stores.add(canonical)

    except Exception:
        pass

    return sorted(found_stores)


def _check_ig_bio_for_stores(
    ig_bio: str,
    known_stores: Dict[str, str],
) -> List[str]:
    """Check Instagram bio for mentions of known department stores."""
    if not ig_bio:
        return []

    found_stores: Set[str] = set()
    bio_lower = ig_bio.lower()

    for normalized, canonical in known_stores.items():
        if len(normalized) >= 4 and normalized in bio_lower:
            found_stores.add(canonical)

    return sorted(found_stores)


def detect_multibrand_stores(
    html: str,
    domain: str,
    brand_name: str,
    geography: Optional[str] = None,
    ig_bio: Optional[str] = None,
    supabase_client=None,
    ig_username: Optional[str] = None,
    apollo_name: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Detect if a brand is sold through department/multi-brand stores.

    Args:
        html: Brand website HTML content
        domain: Brand domain
        brand_name: Brand/company name
        geography: 'COL', 'MEX', or None
        ig_bio: Instagram bio text (optional)
        supabase_client: SupabaseClient instance (optional, for DB lookups)
        ig_username: Instagram username (optional, for fuzzy brand matching)
        apollo_name: Apollo org name (optional, for fuzzy brand matching)

    Returns:
        Dict with:
            - success: bool
            - data: {has_multibrand_stores, multibrand_store_names, evidence}
            - error: str or None
    """
    try:
        from retail.store_registry import get_store_names_set, find_brand_in_stores, normalize_name
    except ImportError:
        from store_registry import get_store_names_set, find_brand_in_stores, normalize_name

    try:
        evidence_list = []
        all_stores: Set[str] = set()
        base_url = f"https://{domain}"

        # Load known store names from Supabase (or use empty dict if no client)
        known_stores: Dict[str, str] = {}
        if supabase_client:
            try:
                known_stores = get_store_names_set(supabase_client, country=geography)
                evidence_list.append(f"Loaded {len(known_stores)} known stores from DB")
            except Exception as e:
                evidence_list.append(f"DB store load failed: {str(e)}")

        # If no DB connection, use a hardcoded fallback of major stores
        if not known_stores:
            known_stores = _get_fallback_stores(geography)
            evidence_list.append(f"Using {len(known_stores)} fallback store names")

        # Source A: Brand website — find "where to buy" pages
        candidates = _scan_html_for_retailer_pages(html, base_url) if html else []

        if candidates:
            evidence_list.append(f"Found {len(candidates)} retailer page link(s)")
            for candidate in candidates[:2]:
                stores_found = _extract_store_names_from_page(candidate["url"], known_stores)
                if stores_found:
                    all_stores.update(stores_found)
                    evidence_list.append(
                        f"Retailer page ({candidate['anchor_text']}): {', '.join(stores_found)}"
                    )
                    break

        # Source A2: Fallback — try common "where to buy" URLs directly.
        # Many Shopify/VTEX sites have JS-rendered navigation, so the link
        # to the retailer page may not appear in static HTML.
        if not all_stores and not candidates:
            COMMON_RETAILER_PATHS = [
                "/pages/donde-comprar",
                "/pages/puntos-de-venta",
                "/pages/tiendas",
                "/pages/tiendas-autorizadas",
                "/donde-comprar",
                "/puntos-de-venta",
                "/tiendas-autorizadas",
                "/pages/encuentranos",
                "/pages/retailers",
                "/pages/where-to-buy",
                "/pages/find-us",
            ]
            for path in COMMON_RETAILER_PATHS:
                page_url = urljoin(base_url, path)
                stores_found = _extract_store_names_from_page(page_url, known_stores)
                if stores_found:
                    all_stores.update(stores_found)
                    evidence_list.append(
                        f"Retailer page (fallback {path}): {', '.join(stores_found)}"
                    )
                    break

        # Also check homepage for store logos/mentions
        homepage_stores = _extract_store_names_from_homepage(html, known_stores) if html else []
        if homepage_stores:
            all_stores.update(homepage_stores)
            evidence_list.append(f"Homepage mentions: {', '.join(homepage_stores)}")

        # Source B: Supabase DB — check if brand appears in scraped store data
        # Uses fuzzy matching cascade: exact → candidates → token containment → fuzzy
        if supabase_client:
            try:
                from retail.store_registry import find_brand_in_stores_fuzzy
                db_matches = find_brand_in_stores_fuzzy(
                    supabase_client, brand_name, country=geography,
                    domain=domain, ig_username=ig_username,
                    apollo_name=apollo_name,
                )
                if db_matches:
                    db_store_names = [m["store_name"] for m in db_matches]
                    all_stores.update(db_store_names)
                    match_type = db_matches[0].get("match_type", "exact")
                    match_score = db_matches[0].get("match_score", 100)
                    evidence_list.append(
                        f"DB matches ({match_type}@{match_score}): {', '.join(db_store_names)}"
                    )
            except Exception as e:
                evidence_list.append(f"DB brand lookup failed: {str(e)}")

        # Source C: Instagram bio
        ig_stores = _check_ig_bio_for_stores(ig_bio, known_stores)
        if ig_stores:
            all_stores.update(ig_stores)
            evidence_list.append(f"IG bio mentions: {', '.join(ig_stores)}")

        store_names = sorted(all_stores)
        has_multibrand = len(store_names) > 0

        return {
            "success": True,
            "data": {
                "has_multibrand_stores": has_multibrand,
                "multibrand_store_names": store_names,
                "evidence": evidence_list,
            },
            "error": None,
        }

    except Exception as e:
        return {
            "success": False,
            "data": {},
            "error": f"Multibrand store detection error: {str(e)}",
        }


def _get_fallback_stores(geography: Optional[str] = None) -> Dict[str, str]:
    """
    Hardcoded fallback store names for when Supabase is not available.
    Maps normalized_name -> canonical_name.
    """
    stores = {}

    if geography != "MEX":
        # Colombia stores
        stores.update({
            "falabella": "Falabella",
            "exito": "Exito",
            "alkosto": "Alkosto",
            "homecenter": "Homecenter",
            "flamingo": "Flamingo",
            "jumbo": "Jumbo",
            "ktronix": "Ktronix",
            "panamericana": "Panamericana",
            "olimpica": "Olimpica",
            "cencosud": "Cencosud",
            "la 14": "La 14",
            "metro": "Metro",
            "ara": "Ara",
            "d1": "D1",
        })

    if geography != "COL":
        # Mexico stores
        stores.update({
            "liverpool": "Liverpool",
            "palacio de hierro": "Palacio de Hierro",
            "coppel": "Coppel",
            "sears": "Sears",
            "suburbia": "Suburbia",
            "walmart": "Walmart",
            "soriana": "Soriana",
            "heb": "HEB",
            "sanborns": "Sanborns",
            "bodega aurrera": "Bodega Aurrera",
            "costco": "Costco",
            "la comer": "La Comer",
            "chedraui": "Chedraui",
            "city club": "City Club",
            "farmacia san pablo": "Farmacia San Pablo",
            "sally beauty": "Sally Beauty",
            "dax": "DAX",
            "privalia": "Privalia",
            "chapur": "Chapur",
            "cimaco": "Cimaco",
            "del sol": "Del Sol",
            "la marina": "La Marina",
        })

    return stores


if __name__ == "__main__":
    test_url = sys.argv[1] if len(sys.argv) > 1 else "https://republiccosmetics.com"
    test_brand = sys.argv[2] if len(sys.argv) > 2 else "Republic Cosmetics"

    print("Multi-brand Store Detection")
    print("=" * 60)
    print(f"URL: {test_url}")
    print(f"Brand: {test_brand}")

    scrape_result = scrape_website(test_url, parse_html=False)
    html_content = scrape_result["data"]["html"] if scrape_result["success"] else ""
    domain_name = urlparse(test_url).netloc.replace("www.", "")

    result = detect_multibrand_stores(html_content, domain_name, test_brand)

    print(f"\nSuccess: {result['success']}")
    if result["success"]:
        data = result["data"]
        print(f"  Has multibrand stores: {data['has_multibrand_stores']}")
        print(f"  Store names: {data['multibrand_store_names']}")
        print(f"\n  Evidence:")
        for ev in data["evidence"]:
            print(f"    - {ev}")
    else:
        print(f"  Error: {result['error']}")
