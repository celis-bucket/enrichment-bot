"""
Fulfillment Provider Detection Tool

Purpose: Detect logistics/fulfillment providers used by an e-commerce brand
Inputs: URL, HTML content (optional)
Outputs: Detected providers, confidence, evidence, shipping options
Dependencies: requests, beautifulsoup4, re, tools/core/web_scraper.py, tools/core/browser_scraper.py

Detection strategies:
1. Source code analysis (HTML/JS for provider signatures)
2. Tracking page detection (/tracking, /seguimiento, /rastreo)
3. Shipping info page analysis (/shipping, /envios, /politica-de-envio)
4. Light checkout via Playwright (add product to cart, inspect shipping options)
"""

import re
import sys
import os
from typing import Dict, Any, List, Optional
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from core.web_scraper import scrape_website


# Provider signatures organized by market
PROVIDER_SIGNATURES = {
    # Colombia
    'Coordinadora': {
        'patterns': [r'coordinadora\.com', r'coordinadora\b'],
        'tracking_domains': ['coordinadora.com'],
        'market': 'Colombia',
    },
    'Servientrega': {
        'patterns': [r'servientrega\.com', r'servientrega\b'],
        'tracking_domains': ['servientrega.com'],
        'market': 'Colombia',
    },
    'Envia': {
        'patterns': [r'envia\.co', r'envia\.com', r'enviá\b'],
        'tracking_domains': ['envia.co'],
        'market': 'Colombia',
    },
    'TCC': {
        'patterns': [r'tcc\.com\.co', r'\btcc\b'],
        'tracking_domains': ['tcc.com.co'],
        'market': 'Colombia',
    },
    'Deprisa': {
        'patterns': [r'deprisa\.com', r'deprisa\b'],
        'tracking_domains': ['deprisa.com'],
        'market': 'Colombia',
    },
    'Inter Rapidisimo': {
        'patterns': [r'interrapidisimo\.com', r'interrapidisimo\b', r'inter\s*rapidísimo'],
        'tracking_domains': ['interrapidisimo.com'],
        'market': 'Colombia',
    },
    'Logitech Fulfillment': {
        'patterns': [r'logitech[-_]?fulfillment', r'logitechfulfillment'],
        'tracking_domains': [],
        'market': 'Colombia',
    },
    # Mexico
    '99minutos': {
        'patterns': [r'99minutos\.com', r'99min', r'99\s*minutos'],
        'tracking_domains': ['99minutos.com'],
        'market': 'Mexico',
    },
    'Estafeta': {
        'patterns': [r'estafeta\.com', r'estafeta\b'],
        'tracking_domains': ['estafeta.com'],
        'market': 'Mexico',
    },
    'FedEx Mexico': {
        'patterns': [r'fedex\.com', r'fedex\b'],
        'tracking_domains': ['fedex.com'],
        'market': 'Multi-market',
    },
    'DHL Express': {
        'patterns': [r'dhl\.com', r'\bdhl\b'],
        'tracking_domains': ['dhl.com'],
        'market': 'Multi-market',
    },
    'Skydropx': {
        'patterns': [r'skydropx\.com', r'skydropx\b'],
        'tracking_domains': ['skydropx.com'],
        'market': 'Mexico',
    },
    'Enviame': {
        'patterns': [r'enviame\.io', r'enviame\b'],
        'tracking_domains': ['enviame.io'],
        'market': 'Mexico',
    },
    'iVoy': {
        'patterns': [r'ivoy\.mx', r'\bivoy\b'],
        'tracking_domains': ['ivoy.mx'],
        'market': 'Mexico',
    },
    # Multi-market / Fulfillment platforms
    'Cubbo': {
        'patterns': [r'cubbo\.co', r'cubbo\.com', r'cubbo\b'],
        'tracking_domains': ['cubbo.co'],
        'market': 'Multi-market',
    },
    'Shopify Shipping': {
        'patterns': [r'shopify[-_]shipping', r'shopify\.delivery', r'shopify_shipping'],
        'tracking_domains': [],
        'market': 'Multi-market',
    },
    'ShipHero': {
        'patterns': [r'shiphero\.com', r'shiphero\b'],
        'tracking_domains': ['shiphero.com'],
        'market': 'Multi-market',
    },
    'ShipBob': {
        'patterns': [r'shipbob\.com', r'shipbob\b'],
        'tracking_domains': ['shipbob.com'],
        'market': 'Multi-market',
    },
}

# Common tracking page paths
TRACKING_PATHS = [
    '/tracking', '/track', '/seguimiento', '/rastreo',
    '/track-order', '/rastrear-pedido', '/estado-de-pedido',
    '/order-tracking',
]

# Common shipping info page paths
SHIPPING_INFO_PATHS = [
    '/shipping', '/envios', '/envio', '/politica-de-envio',
    '/shipping-policy', '/delivery', '/entregas',
    '/politica-de-envios', '/metodos-de-envio',
    '/informacion-de-envio', '/costos-de-envio',
]

# Scoring weights per detection source
SCORE_WEIGHTS = {
    'source_code': 5,
    'tracking_page': 10,
    'shipping_page': 8,
    'checkout': 15,
}


def _scan_source_code(html_content: str, url: str) -> List[Dict[str, Any]]:
    """
    Strategy (a): Scan HTML/JS source for provider signatures.

    Checks script tags, link tags, image tags, data attributes, and plain text.
    """
    evidence = []
    html_lower = html_content.lower()

    for provider, sig in PROVIDER_SIGNATURES.items():
        for pattern in sig['patterns']:
            matches = re.findall(pattern, html_lower, re.IGNORECASE)
            if matches:
                # Get a short snippet around the match
                match_obj = re.search(pattern, html_content, re.IGNORECASE)
                snippet = ''
                if match_obj:
                    start = max(0, match_obj.start() - 30)
                    end = min(len(html_content), match_obj.end() + 30)
                    snippet = html_content[start:end].replace('\n', ' ').strip()

                evidence.append({
                    'provider': provider,
                    'source': 'source_code',
                    'pattern': pattern,
                    'snippet': snippet[:100],
                    'market': sig['market'],
                    'match_count': len(matches)
                })
                break  # One match per provider is enough for source code

    return evidence


def _check_tracking_pages(base_url: str) -> List[Dict[str, Any]]:
    """
    Strategy (b): Check common tracking URL patterns.

    Scrapes each tracking path and looks for provider names/domains.
    """
    evidence = []
    parsed = urlparse(base_url)
    base = f"{parsed.scheme}://{parsed.netloc}"

    for path in TRACKING_PATHS:
        tracking_url = urljoin(base, path)
        result = scrape_website(tracking_url, timeout=10, parse_html=False)

        if not result['success']:
            continue

        html = result['data']['html']
        html_lower = html.lower()

        # Check for provider references in tracking page
        for provider, sig in PROVIDER_SIGNATURES.items():
            for pattern in sig['patterns']:
                if re.search(pattern, html_lower, re.IGNORECASE):
                    evidence.append({
                        'provider': provider,
                        'source': 'tracking_page',
                        'pattern': pattern,
                        'snippet': f'Found on {path}',
                        'market': sig['market'],
                        'match_count': 1
                    })
                    break

        # Also check for tracking domain references
        for provider, sig in PROVIDER_SIGNATURES.items():
            for domain in sig['tracking_domains']:
                if domain in html_lower:
                    # Avoid duplicate evidence
                    already_found = any(
                        e['provider'] == provider and e['source'] == 'tracking_page'
                        for e in evidence
                    )
                    if not already_found:
                        evidence.append({
                            'provider': provider,
                            'source': 'tracking_page',
                            'pattern': domain,
                            'snippet': f'Tracking domain on {path}',
                            'market': sig['market'],
                            'match_count': 1
                        })

    return evidence


def _analyze_shipping_pages(base_url: str) -> tuple:
    """
    Strategy (c): Analyze shipping info pages.

    Returns:
        (evidence_list, shipping_options_list)
    """
    evidence = []
    shipping_options = []
    parsed = urlparse(base_url)
    base = f"{parsed.scheme}://{parsed.netloc}"

    for path in SHIPPING_INFO_PATHS:
        shipping_url = urljoin(base, path)
        result = scrape_website(shipping_url, timeout=10, parse_html=True)

        if not result['success']:
            continue

        html = result['data']['html']
        soup = result['data'].get('soup')
        html_lower = html.lower()

        # Check for provider references
        for provider, sig in PROVIDER_SIGNATURES.items():
            for pattern in sig['patterns']:
                if re.search(pattern, html_lower, re.IGNORECASE):
                    already_found = any(
                        e['provider'] == provider and e['source'] == 'shipping_page'
                        for e in evidence
                    )
                    if not already_found:
                        evidence.append({
                            'provider': provider,
                            'source': 'shipping_page',
                            'pattern': pattern,
                            'snippet': f'Found on {path}',
                            'market': sig['market'],
                            'match_count': 1
                        })

        # Extract shipping option text
        if soup:
            text = soup.get_text(separator=' ', strip=True)
            # Look for shipping-related sentences
            shipping_patterns = [
                r'(?:envío|envio|shipping|entrega|delivery)\s+(?:gratis|gratuito|free|estándar|standard|express|normal)',
                r'(?:\d+[-–]\d+)\s*(?:días|dias|days)\s*(?:hábiles|habiles|business)?',
                r'(?:costo|cost|precio)\s+(?:de\s+)?(?:envío|envio|shipping)[:\s]+\$?\s*[\d,\.]+',
            ]
            for sp in shipping_patterns:
                matches = re.findall(sp, text, re.IGNORECASE)
                for match in matches:
                    if match.strip() and match.strip() not in shipping_options:
                        shipping_options.append(match.strip())

    return evidence, shipping_options


def _checkout_investigation(url: str) -> List[Dict[str, Any]]:
    """
    Strategy (d): Light checkout via Playwright.

    Adds cheapest product to cart and inspects shipping options.
    Falls back gracefully if Playwright is unavailable.
    """
    evidence = []

    try:
        from core.browser_scraper import browser_scrape, interact_with_page, _is_playwright_available
    except ImportError:
        return evidence

    if not _is_playwright_available():
        return evidence

    try:
        # Step 1: Navigate to the site and find a product link
        scrape_result = browser_scrape(url, wait_for='networkidle', timeout=20000)
        if not scrape_result['success']:
            return evidence

        soup = scrape_result['data'].get('soup')
        if not soup:
            return evidence

        # Find product links
        product_link = None
        product_selectors = [
            'a[href*="/products/"]',
            'a[href*="/producto/"]',
            'a[href*="/product/"]',
            'a.product-card',
            'a.product-link',
            '.product-item a',
            '.product a[href]',
        ]

        for sel_text in product_selectors:
            links = soup.select(sel_text)
            for link in links:
                href = link.get('href', '')
                if href and not href.startswith('#') and not href.startswith('javascript'):
                    product_link = urljoin(url, href)
                    break
            if product_link:
                break

        if not product_link:
            return evidence

        # Step 2: Go to product page and try to add to cart
        add_to_cart_selectors = (
            "button[type='submit'][name='add'], "
            ".add-to-cart, "
            "#AddToCart, "
            ".product-form__submit, "
            "button.btn-add-cart, "
            "[data-action='add-to-cart'], "
            "button[data-add-to-cart], "
            ".agregar-carrito, "
            "button.add-to-cart-button"
        )

        actions = [
            {"type": "click", "selector": add_to_cart_selectors, "timeout": 5000},
            {"type": "wait", "timeout": 3000},
        ]

        cart_result = interact_with_page(product_link, actions, timeout=30000)
        if not cart_result['success']:
            return evidence

        # Step 3: Try to go to cart/checkout and look for shipping info
        parsed = urlparse(url)
        base = f"{parsed.scheme}://{parsed.netloc}"
        checkout_urls = [
            urljoin(base, '/cart'),
            urljoin(base, '/checkout'),
            urljoin(base, '/carrito'),
        ]

        for checkout_url in checkout_urls:
            checkout_result = browser_scrape(checkout_url, wait_for='networkidle', timeout=20000)
            if not checkout_result['success']:
                continue

            checkout_html = checkout_result['data']['html']

            # Scan checkout HTML for provider signatures
            checkout_evidence = _scan_source_code(checkout_html, checkout_url)
            for ev in checkout_evidence:
                ev['source'] = 'checkout'
            evidence.extend(checkout_evidence)

    except Exception:
        pass

    return evidence


def _determine_primary_provider(evidence: List[Dict]) -> tuple:
    """
    From all evidence, determine the most likely primary fulfillment provider.

    Returns:
        (primary_provider_name, confidence)
    """
    if not evidence:
        return (None, 0.0)

    # Score each provider based on evidence source weights
    provider_scores = {}
    for ev in evidence:
        provider = ev['provider']
        source = ev['source']
        weight = SCORE_WEIGHTS.get(source, 1)
        provider_scores[provider] = provider_scores.get(provider, 0) + weight

    # Get the top provider
    sorted_providers = sorted(provider_scores.items(), key=lambda x: x[1], reverse=True)
    primary = sorted_providers[0]

    # Confidence: normalize score. Max realistic score ~40 (found in all 4 sources)
    confidence = min(primary[1] / 40.0, 1.0)

    return (primary[0], round(confidence, 2))


def detect_fulfillment_from_html(
    html_content: str,
    url: str
) -> Dict[str, Any]:
    """
    Passive detection: scan HTML source code for fulfillment provider signatures.

    Args:
        html_content: HTML content of the page
        url: Original URL

    Returns:
        Dict with:
            - success: bool
            - data: dict with providers_detected, primary_provider, confidence, evidence, etc.
            - error: str or None
    """
    try:
        evidence = _scan_source_code(html_content, url)
        providers_detected = list(set(ev['provider'] for ev in evidence))
        primary_provider, confidence = _determine_primary_provider(evidence)

        return {
            'success': True,
            'data': {
                'providers_detected': providers_detected,
                'primary_provider': primary_provider,
                'confidence': confidence,
                'evidence': evidence[:15],
                'shipping_options': [],
                'detection_method': 'passive',
            },
            'error': None
        }

    except Exception as e:
        return {
            'success': False,
            'data': {},
            'error': f'Fulfillment detection error: {str(e)}'
        }


def detect_fulfillment(url: str) -> Dict[str, Any]:
    """
    Full investigation: passive + tracking pages + shipping pages + Playwright checkout.

    Args:
        url: E-commerce website URL

    Returns:
        Dict with:
            - success: bool
            - data: dict with providers_detected, primary_provider, confidence,
                     evidence, shipping_options, detection_method, etc.
            - error: str or None
    """
    try:
        all_evidence = []
        shipping_options = []
        tracking_pages_checked = []
        shipping_pages_checked = []
        checkout_attempted = False

        # Step 1: Scrape main page and do passive detection
        scrape_result = scrape_website(url, parse_html=False)
        if not scrape_result['success']:
            return {
                'success': False,
                'data': {},
                'error': f"Failed to scrape URL: {scrape_result['error']}"
            }

        html_content = scrape_result['data']['html']

        # Strategy (a): Source code analysis
        source_evidence = _scan_source_code(html_content, url)
        all_evidence.extend(source_evidence)

        # Strategy (b): Tracking pages
        tracking_evidence = _check_tracking_pages(url)
        all_evidence.extend(tracking_evidence)
        tracking_pages_checked = TRACKING_PATHS.copy()

        # Strategy (c): Shipping info pages
        shipping_evidence, shipping_opts = _analyze_shipping_pages(url)
        all_evidence.extend(shipping_evidence)
        shipping_options.extend(shipping_opts)
        shipping_pages_checked = SHIPPING_INFO_PATHS.copy()

        # Strategy (d): Checkout investigation via Playwright
        # Only if passive detection found few/no providers or confidence is low
        detection_method = 'full'
        try:
            from core.browser_scraper import _is_playwright_available
            if _is_playwright_available():
                checkout_evidence = _checkout_investigation(url)
                all_evidence.extend(checkout_evidence)
                checkout_attempted = True
            else:
                detection_method = 'passive_only'
        except ImportError:
            detection_method = 'passive_only'

        # Deduplicate evidence by (provider, source)
        seen = set()
        unique_evidence = []
        for ev in all_evidence:
            key = (ev['provider'], ev['source'])
            if key not in seen:
                seen.add(key)
                unique_evidence.append(ev)

        providers_detected = list(set(ev['provider'] for ev in unique_evidence))
        primary_provider, confidence = _determine_primary_provider(unique_evidence)

        return {
            'success': True,
            'data': {
                'providers_detected': providers_detected,
                'primary_provider': primary_provider,
                'confidence': confidence,
                'evidence': unique_evidence[:20],
                'shipping_options': shipping_options,
                'detection_method': detection_method,
                'checkout_attempted': checkout_attempted,
                'tracking_pages_checked': tracking_pages_checked,
                'shipping_pages_checked': shipping_pages_checked,
            },
            'error': None
        }

    except Exception as e:
        return {
            'success': False,
            'data': {},
            'error': f'Fulfillment detection error: {str(e)}'
        }


if __name__ == '__main__':
    test_url = sys.argv[1] if len(sys.argv) > 1 else 'https://www.example.com'
    passive_only = '--passive' in sys.argv

    print("Fulfillment Provider Detection")
    print("=" * 60)
    print(f"URL: {test_url}")
    print(f"Mode: {'Passive only' if passive_only else 'Full investigation'}")

    if passive_only:
        scrape_result = scrape_website(test_url, parse_html=False)
        if scrape_result['success']:
            result = detect_fulfillment_from_html(scrape_result['data']['html'], test_url)
        else:
            result = {'success': False, 'data': {}, 'error': f"Scrape failed: {scrape_result['error']}"}
    else:
        result = detect_fulfillment(test_url)

    print(f"\nSuccess: {result['success']}")

    if result['success']:
        data = result['data']
        print(f"  Detection Method: {data.get('detection_method')}")
        print(f"  Providers: {', '.join(data.get('providers_detected', [])) or 'None detected'}")
        print(f"  Primary: {data.get('primary_provider', 'None')}")
        print(f"  Confidence: {data.get('confidence', 0)*100:.0f}%")

        if data.get('shipping_options'):
            print(f"\n  Shipping Options:")
            for opt in data['shipping_options']:
                print(f"    - {opt}")

        if data.get('evidence'):
            print(f"\n  Evidence ({len(data['evidence'])} items):")
            for ev in data['evidence'][:10]:
                print(f"    - [{ev['source']}] {ev['provider']} ({ev['market']}): {ev.get('pattern', '')}")

        if data.get('checkout_attempted') is not None:
            print(f"\n  Checkout attempted: {data['checkout_attempted']}")
    else:
        print(f"  Error: {result['error']}")

    print("\n" + "=" * 60)
