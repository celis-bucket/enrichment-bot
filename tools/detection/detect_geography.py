"""
Geography Detection Tool

Purpose: Detect if a website operates in Colombia or Mexico
Inputs: URL, HTML content (optional)
Outputs: List of countries, primary country, confidence score, evidence
Dependencies: requests, beautifulsoup4, re

Detection Strategy:
1. Currency symbols and codes (COP, MXN, $)
2. Language codes (es-CO, es-MX)
3. Shipping page analysis
4. Phone numbers (+57, +52)
5. Footer/contact address information
6. Country mentions in text
"""

import re
from typing import Dict, Any, List, Optional
from bs4 import BeautifulSoup
from urllib.parse import urljoin

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from core.web_scraper import scrape_website


# Country detection patterns
COUNTRY_PATTERNS = {
    'Colombia': {
        'currency_codes': ['COP', 'COL$'],
        'currency_symbols': ['$', 'COP'],  # $ is ambiguous but we check context
        'phone_codes': ['+57', '57'],
        'language_codes': ['es-CO', 'es_CO'],
        'keywords': [
            'Colombia', 'colombiano', 'colombiana',
            'Bogotá', 'Medellín', 'Cali', 'Barranquilla',
            'envío a Colombia', 'envíos Colombia',
            'despachos Colombia', 'domicilio Colombia'
        ],
        'tld': '.co',
    },
    'Mexico': {
        'currency_codes': ['MXN', 'MEX$'],
        'currency_symbols': ['$', 'MXN'],
        'phone_codes': ['+52', '52'],
        'language_codes': ['es-MX', 'es_MX'],
        'keywords': [
            'México', 'Mexico', 'mexicano', 'mexicana',
            'Ciudad de México', 'CDMX', 'Guadalajara', 'Monterrey',
            'envío a México', 'envíos México',
            'envío en México', 'despachos México'
        ],
        'tld': '.mx',
    },
}


def analyze_text_for_countries(text: str) -> Dict[str, int]:
    """
    Analyze text content for country mentions.

    Args:
        text: Text content to analyze

    Returns:
        Dict mapping country names to mention counts
    """
    scores = {country: 0 for country in COUNTRY_PATTERNS.keys()}

    text_lower = text.lower()

    for country, patterns in COUNTRY_PATTERNS.items():
        # Check for keywords
        for keyword in patterns['keywords']:
            # Use word boundaries to avoid partial matches
            pattern = r'\b' + re.escape(keyword.lower()) + r'\b'
            matches = re.findall(pattern, text_lower)
            scores[country] += len(matches)

    return scores


def detect_geography_from_html(
    html_content: str,
    url: str
) -> Dict[str, Any]:
    """
    Detect geographic operations from HTML content.

    Args:
        html_content: HTML content of the page
        url: Original URL

    Returns:
        Dict with:
            - success: bool
            - data: dict with 'countries', 'primary_country', 'confidence', 'evidence'
            - error: str or None
    """
    try:
        soup = BeautifulSoup(html_content, 'lxml')
        evidence = {}
        country_scores = {country: 0 for country in COUNTRY_PATTERNS.keys()}

        # 1. Check HTML lang attribute
        html_tag = soup.find('html')
        if html_tag and html_tag.get('lang'):
            lang = html_tag.get('lang')
            for country, patterns in COUNTRY_PATTERNS.items():
                if any(code in lang for code in patterns['language_codes']):
                    country_scores[country] += 15
                    evidence.setdefault(country, []).append(f"HTML lang attribute: {lang}")

        # 2. Check domain TLD
        # Extract domain from URL for TLD check (handles trailing slashes and paths)
        from urllib.parse import urlparse
        parsed_url = urlparse(url)
        domain = parsed_url.netloc or parsed_url.path.split('/')[0]
        for country, patterns in COUNTRY_PATTERNS.items():
            if domain.endswith(patterns['tld']):
                country_scores[country] += 15  # TLD is strong evidence
                evidence.setdefault(country, []).append(f"Domain TLD: {patterns['tld']}")

        # 3. Check for currency codes
        text_content = soup.get_text()
        for country, patterns in COUNTRY_PATTERNS.items():
            for currency in patterns['currency_codes']:
                if currency in text_content:
                    # Count occurrences
                    count = text_content.count(currency)
                    country_scores[country] += min(count * 2, 20)
                    evidence.setdefault(country, []).append(f"Currency code: {currency} ({count} times)")

        # 4. Check for phone numbers
        # Look for phone numbers in links and text
        phone_links = soup.find_all('a', href=re.compile(r'tel:'))
        for link in phone_links:
            href = link.get('href', '')
            for country, patterns in COUNTRY_PATTERNS.items():
                for code in patterns['phone_codes']:
                    if code in href:
                        country_scores[country] += 10
                        evidence.setdefault(country, []).append(f"Phone number: {href}")

        # 5. Check footer for addresses
        footer = soup.find('footer')
        if footer:
            footer_text = footer.get_text()
            footer_scores = analyze_text_for_countries(footer_text)
            for country, score in footer_scores.items():
                if score > 0:
                    country_scores[country] += min(score * 3, 30)
                    evidence.setdefault(country, []).append(f"Footer mentions: {score} times")

        # 6. Analyze full page text
        page_scores = analyze_text_for_countries(text_content)
        for country, score in page_scores.items():
            if score > 0:
                country_scores[country] += min(score, 25)
                evidence.setdefault(country, []).append(f"Page mentions: {score} times")

        # 7. Look for shipping/envios pages
        shipping_links = soup.find_all('a', href=True, string=re.compile(r'(envío|envio|shipping|entrega)', re.IGNORECASE))
        if shipping_links:
            # Try to scrape shipping page
            for link in shipping_links[:1]:  # Just check first shipping link
                shipping_url = urljoin(url, link.get('href'))
                try:
                    shipping_result = scrape_website(shipping_url, timeout=10)
                    if shipping_result['success']:
                        shipping_text = shipping_result['data']['text']
                        shipping_scores = analyze_text_for_countries(shipping_text)
                        for country, score in shipping_scores.items():
                            if score > 0:
                                country_scores[country] += min(score * 5, 40)
                                evidence.setdefault(country, []).append(f"Shipping page mentions: {score} times")
                except Exception as e:
                    print(f"Warning: Failed to scrape shipping page {shipping_url}: {e}")

        # Determine detected countries
        detected_countries = [
            country for country, score in country_scores.items()
            if score > 10  # Minimum threshold
        ]

        # Calculate confidence
        max_score = max(country_scores.values()) if country_scores.values() else 0
        confidence = min(max_score / 100.0, 1.0) if max_score > 0 else 0.0

        # Determine primary country (highest score)
        primary_country = None
        if detected_countries:
            primary_country = max(country_scores.items(), key=lambda x: x[1])[0]

        return {
            'success': True,
            'data': {
                'countries': detected_countries,
                'primary_country': primary_country,
                'confidence': round(confidence, 2),
                'evidence': {k: v[:5] for k, v in evidence.items()},  # Top 5 per country
                'scores': {k: v for k, v in sorted(country_scores.items(), key=lambda x: x[1], reverse=True) if v > 0}
            },
            'error': None
        }

    except Exception as e:
        return {
            'success': False,
            'data': {},
            'error': f'Geography detection error: {str(e)}'
        }


def detect_geography(url: str) -> Dict[str, Any]:
    """
    Detect geographic operations from a URL.

    Args:
        url: Website URL

    Returns:
        Dict with:
            - success: bool
            - data: dict with 'countries', 'primary_country', 'confidence', 'evidence'
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

    # Get HTML content
    html_content = scrape_result['data']['html']

    # Detect geography
    return detect_geography_from_html(html_content, url)


if __name__ == '__main__':
    # Test cases
    import sys

    if len(sys.argv) > 1:
        test_urls = [sys.argv[1]]
    else:
        test_urls = [
            'https://www.example.com',  # Replace with actual test URLs
        ]

    print("Geography Detection Test")
    print("=" * 60)

    for test_url in test_urls:
        print(f"\nTesting: {test_url}")
        print("-" * 60)

        result = detect_geography(test_url)

        if result['success']:
            data = result['data']
            print(f"✓ Countries: {', '.join(data['countries']) if data['countries'] else 'None detected'}")
            if data['primary_country']:
                print(f"  Primary: {data['primary_country']}")
            print(f"  Confidence: {data['confidence']*100:.0f}%")

            if data['evidence']:
                print(f"\n  Evidence by Country:")
                for country, evidences in data['evidence'].items():
                    print(f"\n    {country}:")
                    for ev in evidences:
                        print(f"      - {ev}")

            if data['scores']:
                print(f"\n  Scores:")
                for country, score in data['scores'].items():
                    print(f"    {country}: {score}")
        else:
            print(f"✗ Error: {result['error']}")

    print("\n" + "=" * 60)
