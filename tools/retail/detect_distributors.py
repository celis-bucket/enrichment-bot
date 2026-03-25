"""
Distributor/Wholesaler Detection Tool

Purpose: Detect if a brand has a distributor/wholesaler/reseller program
Inputs: HTML content, domain, brand name, geography
Outputs: Binary (has_distributors) + evidence
Dependencies: tools/core/web_scraper.py, tools/core/google_search.py, re, bs4

Detection strategies:
1. Scan HTML for distributor-related links (href + anchor text)
2. If candidate page found, scrape and confirm distributor content
3. Google search fallback: "{brand_name}" "distribuidor" OR "donde comprar" OR "mayorista"
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

# Patterns that indicate a distributor/wholesaler page (in link text or href)
DISTRIBUTOR_LINK_PATTERNS = [
    # Spanish
    r'distribuid',           # distribuidor, distribuidores, distribución
    r'mayorist',             # mayorista, mayoristas
    r'donde\s*comprar',
    r'puntos?\s*de\s*venta',
    r'inicia\s*tu\s*(propio\s*)?negocio',
    r'empren',               # emprende, emprendimiento
    r'revende',              # revendedor, revender
    r'vende\s*nuestros',
    r'se\s*nuestro\s*aliado',
    r'franquicia',
    r'negocio\s*propio',
    r'compra\s*al\s*por\s*mayor',
    r'al\s*mayor',
    r'venta\s*al\s*por\s*mayor',
    r'programa\s*de\s*afiliados',
    # English (for bilingual sites)
    r'wholesal',             # wholesale, wholesaler
    r'become\s*a?\s*dealer',
    r'become\s*a?\s*distributor',
    r'resell',               # reseller, resell
    r'where\s*to\s*buy',
    r'find\s*a\s*store',
    r'retail\s*partner',
    r'start\s*your\s*(own\s*)?business',
]

# Patterns in the page content that confirm it's a distributor page
DISTRIBUTOR_CONTENT_PATTERNS = [
    r'formulario',           # application form
    r'requisitos',           # requirements
    r'condiciones\s*comerciales',
    r'compra\s*m[ií]nima',
    r'pedido\s*m[ií]nimo',
    r'precio\s*(?:de\s*)?mayorista',
    r'precio\s*(?:de\s*)?distribuidor',
    r'catálogo\s*(?:de\s*)?mayorista',
    r'margen\s*(?:de\s*)?ganancia',
    r'contacta?\s*(?:a\s*)?(?:nuestro|un)\s*(?:asesor|representante)',
    r'zona\s*disponible',
    r'whatsapp.*mayorista',
    r'wholesale\s*price',
    r'minimum\s*order',
    r'bulk\s*order',
]

DISTRIBUTOR_HREF_PATTERNS = [
    r'/distribuid',
    r'/mayorist',
    r'/wholesale',
    r'/donde-comprar',
    r'/puntos-de-venta',
    r'/negocio',
    r'/reseller',
    r'/dealer',
    r'/where-to-buy',
    r'/empren',
    r'/afiliado',
    r'/al-mayor',
]


def _scan_html_for_distributor_links(html: str, base_url: str) -> List[Dict[str, str]]:
    """
    Scan HTML for links that suggest a distributor/wholesale program.

    Returns list of candidate pages: [{url, anchor_text, match_type}]
    """
    candidates = []
    try:
        soup = BeautifulSoup(html, 'html.parser')

        for a_tag in soup.find_all('a', href=True):
            href = a_tag['href'].strip()
            text = a_tag.get_text(strip=True).lower()
            href_lower = href.lower()

            # Check anchor text
            for pattern in DISTRIBUTOR_LINK_PATTERNS:
                if re.search(pattern, text, re.IGNORECASE):
                    full_url = urljoin(base_url, href)
                    candidates.append({
                        "url": full_url,
                        "anchor_text": a_tag.get_text(strip=True)[:100],
                        "match_type": "anchor_text",
                        "pattern": pattern,
                    })
                    break

            # Check href path
            if not any(c["url"] == urljoin(base_url, href) for c in candidates):
                for pattern in DISTRIBUTOR_HREF_PATTERNS:
                    if re.search(pattern, href_lower):
                        full_url = urljoin(base_url, href)
                        candidates.append({
                            "url": full_url,
                            "anchor_text": a_tag.get_text(strip=True)[:100],
                            "match_type": "href",
                            "pattern": pattern,
                        })
                        break

    except Exception:
        pass

    # Deduplicate by URL
    seen = set()
    unique = []
    for c in candidates:
        if c["url"] not in seen:
            seen.add(c["url"])
            unique.append(c)
    return unique


def _confirm_distributor_page(url: str) -> Dict[str, Any]:
    """
    Scrape a candidate page and check if it confirms distributor/wholesale content.

    Returns:
        Dict with confirmed (bool) and evidence snippets
    """
    result = scrape_website(url, timeout=15, parse_html=False)
    if not result["success"]:
        return {"confirmed": False, "evidence": []}

    html = result["data"]["html"]
    html_lower = html.lower()
    found_patterns = []

    for pattern in DISTRIBUTOR_CONTENT_PATTERNS:
        if re.search(pattern, html_lower, re.IGNORECASE):
            found_patterns.append(pattern)

    # Also check for form elements (contact/application forms)
    has_form = bool(re.search(r'<form[\s>]', html_lower))
    if has_form:
        found_patterns.append("form_element")

    # Consider confirmed if we find at least 1 content pattern or a form
    return {
        "confirmed": len(found_patterns) >= 1,
        "evidence": found_patterns[:5],
    }


def _google_search_distributors(brand_name: str, geography: Optional[str] = None,
                                 domain: str = "") -> Dict[str, Any]:
    """
    Search Google for distributor pages of this brand.
    """
    # Build query
    query = f'"{brand_name}" "distribuidor" OR "donde comprar" OR "mayorista" OR "wholesale"'

    country_code = None
    if geography == "COL":
        country_code = "co"
    elif geography == "MEX":
        country_code = "mx"

    result = google_search(query, num_results=5, country=country_code, language="es")
    if not result["success"]:
        return {"found": False, "evidence": "Google search failed"}

    data = result["data"]
    organic = data.get("organic", [])

    # Check if any top results are from the brand's own domain
    if domain:
        domain_clean = domain.replace("www.", "")
        for item in organic[:5]:
            link = item.get("link", "").lower()
            if domain_clean in link:
                # Brand has its own distributor page indexed in Google
                return {
                    "found": True,
                    "evidence": f"Brand distributor page found: {item.get('title', '')[:80]}",
                    "url": item.get("link"),
                }

    # Check if brand appears with distributor-related content
    brand_lower = brand_name.lower()
    for item in organic[:3]:
        title = item.get("title", "").lower()
        snippet = item.get("snippet", "").lower()
        combined = f"{title} {snippet}"
        if brand_lower in combined and any(
            kw in combined for kw in ["distribuidor", "mayorista", "donde comprar", "wholesale"]
        ):
            return {
                "found": True,
                "evidence": f"Google result: {item.get('title', '')[:80]}",
                "url": item.get("link"),
            }

    return {"found": False, "evidence": "No distributor signals in Google results"}


def detect_distributors(
    html: str,
    domain: str,
    brand_name: str,
    geography: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Detect if a brand has a distributor/wholesaler program.

    Args:
        html: Brand website HTML content
        domain: Brand domain
        brand_name: Brand/company name
        geography: 'COL', 'MEX', or None

    Returns:
        Dict with:
            - success: bool
            - data: {has_distributors: bool, evidence: str, source_url: str|None}
            - error: str or None
    """
    try:
        evidence_parts = []
        source_url = None
        has_distributors = False

        # Strategy 1: Scan website HTML for distributor links
        base_url = f"https://{domain}"
        candidates = _scan_html_for_distributor_links(html, base_url) if html else []

        if candidates:
            evidence_parts.append(f"Found {len(candidates)} candidate link(s) in HTML")

            # Try to confirm the top candidate(s)
            for candidate in candidates[:3]:  # Check up to 3 candidates
                confirmation = _confirm_distributor_page(candidate["url"])
                if confirmation["confirmed"]:
                    has_distributors = True
                    source_url = candidate["url"]
                    evidence_parts.append(
                        f"Confirmed: {candidate['anchor_text']} -> {', '.join(confirmation['evidence'][:3])}"
                    )
                    break
                else:
                    # Even finding the link is a signal — distributor page exists
                    has_distributors = True
                    source_url = candidate["url"]
                    evidence_parts.append(
                        f"Distributor link found: '{candidate['anchor_text']}' ({candidate['match_type']})"
                    )
                    break

        # Strategy 2: Google fallback if nothing found in HTML
        if not has_distributors:
            google_result = _google_search_distributors(brand_name, geography, domain)
            if google_result["found"]:
                has_distributors = True
                source_url = google_result.get("url")
                evidence_parts.append(f"Google: {google_result['evidence']}")
            else:
                evidence_parts.append(google_result["evidence"])

        return {
            "success": True,
            "data": {
                "has_distributors": has_distributors,
                "evidence": "; ".join(evidence_parts),
                "source_url": source_url,
            },
            "error": None,
        }

    except Exception as e:
        return {
            "success": False,
            "data": {},
            "error": f"Distributor detection error: {str(e)}",
        }


if __name__ == "__main__":
    test_url = sys.argv[1] if len(sys.argv) > 1 else "https://accesoriosavemaria.com"
    test_brand = sys.argv[2] if len(sys.argv) > 2 else "Ave Maria"

    print("Distributor/Wholesaler Detection")
    print("=" * 60)
    print(f"URL: {test_url}")
    print(f"Brand: {test_brand}")

    # Scrape the site first
    scrape_result = scrape_website(test_url, parse_html=False)
    html_content = scrape_result["data"]["html"] if scrape_result["success"] else ""
    domain_name = urlparse(test_url).netloc.replace("www.", "")

    result = detect_distributors(html_content, domain_name, test_brand)

    print(f"\nSuccess: {result['success']}")
    if result["success"]:
        data = result["data"]
        print(f"  Has distributors: {data['has_distributors']}")
        print(f"  Evidence: {data['evidence']}")
        if data.get("source_url"):
            print(f"  Source URL: {data['source_url']}")
    else:
        print(f"  Error: {result['error']}")
