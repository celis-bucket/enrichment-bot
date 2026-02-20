"""
E-commerce Platform Detection Tool

Purpose: Identify the e-commerce platform (Shopify, VTEX, WooCommerce, Magento, custom)
Inputs: URL, HTML content (optional)
Outputs: Platform name, confidence score, version, evidence
Dependencies: requests, beautifulsoup4, re

Detection Strategy:
1. Check meta generator tags
2. Look for platform-specific CDN URLs
3. Check file paths and directory structure
4. Analyze HTTP headers
5. Look for API endpoint patterns
"""

import re
from typing import Dict, Any, List, Optional
from bs4 import BeautifulSoup

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from core.web_scraper import scrape_website


# Platform detection patterns
PLATFORM_SIGNATURES = {
    'Shopify': {
        'meta_generator': ['Shopify'],
        'cdn_patterns': [
            r'cdn\.shopify\.com',
            r'shopifycdn\.com',
            r'shopify-analytics',
        ],
        'script_patterns': [
            r'/wpm@',
            r'Shopify\.theme',
            r'Shopify\.routes',
        ],
        'headers': ['X-Shopify-Stage', 'X-ShopId'],
        'html_patterns': [
            r'shopify-section',
            r'shopify-payment-button',
        ],
        'path_patterns': [
            r'/cart\.js',
            r'/products\.json',
            r'/collections/',
        ],
    },
    'VTEX': {
        'meta_generator': ['VTEX'],
        'cdn_patterns': [
            r'vteximg\.com\.br',
            r'vtexassets\.com',
            r'vtex\.com\.br',
        ],
        'script_patterns': [
            r'vtex\.js',
            r'checkout\.vtex',
            r'io\.vtex',
        ],
        'headers': ['X-VTEX-', 'X-Track'],
        'html_patterns': [
            r'vtex-',
            r'data-vtex',
        ],
        'path_patterns': [
            r'/api/catalog/',
            r'/api/io/',
        ],
    },
    'WooCommerce': {
        'meta_generator': ['WooCommerce'],
        'cdn_patterns': [],
        'script_patterns': [
            r'woocommerce',
            r'wc-',
        ],
        'headers': [],
        'html_patterns': [
            r'woocommerce',
            r'wc-',
            r'product_cat',
        ],
        'path_patterns': [
            r'/wp-content/plugins/woocommerce/',
            r'/wp-json/wc/',
            r'\?wc-ajax=',
        ],
    },
    'Magento': {
        'meta_generator': ['Magento'],
        'cdn_patterns': [],
        'script_patterns': [
            r'Mage\.Cookies',
            r'mage/cookies',
            r'magento',
        ],
        'headers': ['X-Magento-'],
        'html_patterns': [
            r'product-item-info',
            r'magento',
        ],
        'path_patterns': [
            r'/skin/frontend/',
            r'/js/mage/',
            r'/static/_requirejs/',
            r'/pub/static/',
        ],
    },
    'PrestaShop': {
        'meta_generator': ['PrestaShop'],
        'cdn_patterns': [],
        'script_patterns': [
            r'prestashop',
        ],
        'headers': [],
        'html_patterns': [
            r'prestashop',
        ],
        'path_patterns': [
            r'/modules/ps_',
            r'/themes/',
        ],
    },
    'BigCommerce': {
        'meta_generator': ['BigCommerce'],
        'cdn_patterns': [
            r'bigcommerce\.com',
            r'cdn\d+\.bigcommerce\.com',
        ],
        'script_patterns': [
            r'bigcommerce',
        ],
        'headers': [],
        'html_patterns': [
            r'bigcommerce',
        ],
        'path_patterns': [],
    },
}


def detect_platform_from_html(
    html_content: str,
    url: str,
    headers: Optional[Dict[str, str]] = None
) -> Dict[str, Any]:
    """
    Detect e-commerce platform from HTML content and headers.

    Args:
        html_content: HTML content of the page
        url: Original URL
        headers: HTTP response headers

    Returns:
        Dict with:
            - success: bool
            - data: dict with 'platform', 'confidence', 'version', 'evidence'
            - error: str or None
    """
    try:
        soup = BeautifulSoup(html_content, 'lxml')
        evidence = []
        platform_scores = {platform: 0 for platform in PLATFORM_SIGNATURES.keys()}
        platform_scores['Custom'] = 0

        # 1. Check meta generator tag (highest confidence)
        meta_generator = soup.find('meta', {'name': 'generator'})
        if meta_generator:
            content = meta_generator.get('content', '')
            for platform, signatures in PLATFORM_SIGNATURES.items():
                for generator in signatures['meta_generator']:
                    if generator.lower() in content.lower():
                        platform_scores[platform] += 30
                        evidence.append(f"Meta generator: {content}")

                        # Try to extract version
                        version_match = re.search(r'(\d+\.\d+\.?\d*)', content)
                        version = version_match.group(1) if version_match else None
                        break

        # 2. Check CDN patterns in HTML
        html_lower = html_content.lower()
        for platform, signatures in PLATFORM_SIGNATURES.items():
            for pattern in signatures['cdn_patterns']:
                if re.search(pattern, html_lower, re.IGNORECASE):
                    platform_scores[platform] += 15
                    evidence.append(f"CDN pattern found: {pattern}")

        # 3. Check script patterns
        scripts = soup.find_all('script', src=True)
        for script in scripts:
            src = script.get('src', '').lower()
            for platform, signatures in PLATFORM_SIGNATURES.items():
                for pattern in signatures['script_patterns']:
                    if re.search(pattern, src, re.IGNORECASE):
                        platform_scores[platform] += 10
                        evidence.append(f"Script pattern: {pattern} in {src[:50]}")

        # 4. Check inline scripts
        inline_scripts = soup.find_all('script', src=False)
        for script in inline_scripts:
            script_text = script.string or ''
            for platform, signatures in PLATFORM_SIGNATURES.items():
                for pattern in signatures['script_patterns']:
                    if re.search(pattern, script_text, re.IGNORECASE):
                        platform_scores[platform] += 5
                        evidence.append(f"Inline script pattern: {pattern}")

        # 5. Check HTML class/id patterns
        html_text = str(soup)
        for platform, signatures in PLATFORM_SIGNATURES.items():
            for pattern in signatures['html_patterns']:
                matches = re.findall(pattern, html_text, re.IGNORECASE)
                if matches:
                    platform_scores[platform] += min(len(matches), 10)
                    evidence.append(f"HTML pattern: {pattern} ({len(matches)} occurrences)")

        # 6. Check URL path patterns
        for platform, signatures in PLATFORM_SIGNATURES.items():
            for pattern in signatures['path_patterns']:
                if re.search(pattern, url, re.IGNORECASE):
                    platform_scores[platform] += 10
                    evidence.append(f"URL path pattern: {pattern}")

        # 7. Check HTTP headers (if provided)
        if headers:
            for platform, signatures in PLATFORM_SIGNATURES.items():
                for header_pattern in signatures['headers']:
                    for header_key in headers.keys():
                        if header_pattern.lower() in header_key.lower():
                            platform_scores[platform] += 20
                            evidence.append(f"HTTP header: {header_key}")

        # Determine the detected platform
        max_score = max(platform_scores.values())

        if max_score == 0:
            # No platform detected
            detected_platform = 'Custom'
            confidence = 0.3
            version = None
        else:
            detected_platform = max(platform_scores.items(), key=lambda x: x[1])[0]
            # Normalize confidence to 0-1 scale (max possible score is ~100)
            confidence = min(max_score / 100.0, 1.0)

            # Try to extract version from meta tag if not already found
            version = None
            meta_generator = soup.find('meta', {'name': 'generator'})
            if meta_generator:
                content = meta_generator.get('content', '')
                version_match = re.search(r'(\d+\.\d+\.?\d*)', content)
                if version_match:
                    version = version_match.group(1)

        return {
            'success': True,
            'data': {
                'platform': detected_platform,
                'confidence': round(confidence, 2),
                'version': version,
                'evidence': evidence[:10],  # Top 10 pieces of evidence
                'scores': {k: v for k, v in sorted(platform_scores.items(), key=lambda x: x[1], reverse=True) if v > 0}
            },
            'error': None
        }

    except Exception as e:
        return {
            'success': False,
            'data': {},
            'error': f'Platform detection error: {str(e)}'
        }


def detect_platform(url: str) -> Dict[str, Any]:
    """
    Detect e-commerce platform from a URL.

    Args:
        url: E-commerce website URL

    Returns:
        Dict with:
            - success: bool
            - data: dict with 'platform', 'confidence', 'version', 'evidence'
            - error: str or None
    """
    # Scrape the website
    scrape_result = scrape_website(url, parse_html=False)

    if not scrape_result['success']:
        return {
            'success': False,
            'data': {},
            'error': f"Failed to scrape URL: {scrape_result['error']}"
        }

    # Get HTML and headers
    html_content = scrape_result['data']['html']
    headers = scrape_result['data']['headers']

    # Detect platform
    return detect_platform_from_html(html_content, url, headers)


if __name__ == '__main__':
    # Test cases
    import sys

    test_urls = [
        'https://www.allbirds.com',  # Shopify
        'https://www.gymshark.com',  # Shopify
        # Add more test URLs as needed
    ]

    if len(sys.argv) > 1:
        test_urls = [sys.argv[1]]

    print("E-commerce Platform Detection Test")
    print("=" * 60)

    for test_url in test_urls:
        print(f"\nTesting: {test_url}")
        print("-" * 60)

        result = detect_platform(test_url)

        if result['success']:
            data = result['data']
            print(f"✓ Platform: {data['platform']}")
            print(f"  Confidence: {data['confidence']*100:.0f}%")
            if data['version']:
                print(f"  Version: {data['version']}")

            print(f"\n  Evidence:")
            for evidence in data['evidence']:
                print(f"    - {evidence}")

            if data['scores']:
                print(f"\n  All Scores:")
                for platform, score in data['scores'].items():
                    print(f"    {platform}: {score}")
        else:
            print(f"✗ Error: {result['error']}")

    print("\n" + "=" * 60)
