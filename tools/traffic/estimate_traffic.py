"""
Traffic Estimation Tool

Purpose: Estimate website traffic using free signals + SimilarWeb API (stub)
Inputs: URL, HTML content, social data (optional)
Outputs: Estimated monthly visits, confidence, signal details
Dependencies: requests, beautifulsoup4, xml.etree.ElementTree

Signals used:
1. Sitemap size (URL count from sitemap.xml / robots.txt)
2. Social follower counts (Instagram, Facebook, etc. - passed as input)
3. Review/rating counts on product pages
4. SimilarWeb API (STUB - requires SIMILARWEB_API_KEY)
"""

import os
import re
import sys
import requests
import xml.etree.ElementTree as ET
from typing import Dict, Any, Optional
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from core.web_scraper import scrape_website


def _count_sitemap_urls(url: str) -> Optional[int]:
    """
    Count URLs in sitemap.xml.

    Strategy:
    1. Try {url}/sitemap.xml directly
    2. Parse robots.txt for Sitemap: directives
    3. Try common sitemap variations
    4. Parse sitemap index files (one level deep)

    Returns:
        Total URL count or None if no sitemap found
    """
    parsed = urlparse(url)
    base_url = f"{parsed.scheme}://{parsed.netloc}"
    total_urls = 0
    found_sitemap = False

    # Sitemap URLs to try
    sitemap_urls = [
        urljoin(base_url, '/sitemap.xml'),
        urljoin(base_url, '/sitemap_index.xml'),
        urljoin(base_url, '/sitemap1.xml'),
    ]

    # Check robots.txt for sitemap directives
    try:
        robots_result = scrape_website(urljoin(base_url, '/robots.txt'), timeout=10, parse_html=False)
        if robots_result['success']:
            for line in robots_result['data']['html'].splitlines():
                line = line.strip()
                if line.lower().startswith('sitemap:'):
                    sitemap_url = line.split(':', 1)[1].strip()
                    if sitemap_url and sitemap_url not in sitemap_urls:
                        sitemap_urls.insert(0, sitemap_url)
    except Exception:
        pass

    for sitemap_url in sitemap_urls:
        try:
            result = scrape_website(sitemap_url, timeout=15, parse_html=False)
            if not result['success']:
                continue

            xml_content = result['data']['html']

            # Remove XML namespace for easier parsing
            xml_content = re.sub(r'\sxmlns="[^"]+"', '', xml_content, count=1)

            root = ET.fromstring(xml_content)

            # Check if this is a sitemap index
            sitemap_entries = root.findall('.//sitemap')
            if sitemap_entries:
                # It's a sitemap index — count URLs from child sitemaps (one level deep)
                found_sitemap = True
                for sitemap_entry in sitemap_entries[:10]:  # Limit to 10 child sitemaps
                    loc = sitemap_entry.find('loc')
                    if loc is not None and loc.text:
                        try:
                            child_result = scrape_website(loc.text.strip(), timeout=15, parse_html=False)
                            if child_result['success']:
                                child_xml = re.sub(r'\sxmlns="[^"]+"', '', child_result['data']['html'], count=1)
                                child_root = ET.fromstring(child_xml)
                                child_urls = child_root.findall('.//url')
                                total_urls += len(child_urls)
                        except Exception:
                            continue
                break

            # Check for regular sitemap with <url> entries
            url_entries = root.findall('.//url')
            if url_entries:
                found_sitemap = True
                total_urls += len(url_entries)
                break

        except ET.ParseError:
            continue
        except Exception:
            continue

    return total_urls if found_sitemap else None


def _count_reviews(html_content: str, soup: BeautifulSoup) -> int:
    """
    Count review/rating indicators in HTML.

    Looks for:
    - Schema.org Review/AggregateRating markup
    - Common review count patterns ("123 reviews", "123 opiniones")
    - Star rating widgets
    """
    review_count = 0

    # Strategy 1: Schema.org AggregateRating
    # Look for reviewCount or ratingCount in JSON-LD
    scripts = soup.find_all('script', type='application/ld+json')
    for script in scripts:
        try:
            import json
            data = json.loads(script.string)
            # Handle both single object and list
            items = data if isinstance(data, list) else [data]
            for item in items:
                agg = item.get('aggregateRating', {})
                rc = agg.get('reviewCount') or agg.get('ratingCount')
                if rc:
                    review_count = max(review_count, int(rc))
        except (json.JSONDecodeError, ValueError, TypeError, AttributeError):
            continue

    # Strategy 2: HTML meta/itemprop
    for meta in soup.find_all(attrs={'itemprop': 'reviewCount'}):
        try:
            val = meta.get('content') or meta.get_text(strip=True)
            if val:
                review_count = max(review_count, int(re.sub(r'[^\d]', '', val)))
        except (ValueError, TypeError):
            continue

    # Strategy 3: Text patterns
    patterns = [
        r'(\d[\d,\.]*)\s*(?:reviews?|reseñas?|opiniones|valoraciones|calificaciones)',
        r'(?:reviews?|reseñas?|opiniones)\s*\((\d[\d,\.]*)\)',
        r'\((\d[\d,\.]*)\s*(?:reviews?|reseñas?)\)',
    ]
    text = soup.get_text()
    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for match in matches:
            try:
                val = int(re.sub(r'[,\.]', '', match))
                review_count = max(review_count, val)
            except ValueError:
                continue

    return review_count


def _estimate_from_similarweb(domain: str) -> Optional[Dict[str, Any]]:
    """
    SimilarWeb API integration (STUB).

    Returns None when SIMILARWEB_API_KEY is missing.
    When key is present, calls SimilarWeb API for traffic data.

    Returns:
        Dict with monthly_visits, bounce_rate, pages_per_visit or None
    """
    api_key = os.getenv('SIMILARWEB_API_KEY')
    if not api_key:
        return None

    try:
        response = requests.get(
            f"https://api.similarweb.com/v1/website/{domain}/total-traffic-and-engagement/visits",
            params={'api_key': api_key, 'granularity': 'monthly'},
            timeout=30
        )

        if response.status_code == 401:
            print("[estimate_traffic] Invalid SIMILARWEB_API_KEY")
            return None

        if response.status_code == 429:
            print("[estimate_traffic] SimilarWeb rate limit reached")
            return None

        if response.status_code >= 400:
            return None

        data = response.json()
        visits = data.get('visits', [])

        if visits:
            latest = visits[-1]
            return {
                'monthly_visits': int(latest.get('visits', 0)),
                'source': 'similarweb'
            }

        return None

    except Exception:
        return None


def _calculate_traffic_estimate(
    sitemap_size: Optional[int],
    social_followers: int,
    review_count: int,
    similarweb_data: Optional[Dict]
) -> tuple:
    """
    Combine signals into a single traffic estimate.

    Returns:
        (estimated_monthly_visits, confidence, signals_used)
    """
    estimate = 0
    signals = 0
    signals_used = []

    # SimilarWeb overrides everything if available
    if similarweb_data and similarweb_data.get('monthly_visits'):
        return (
            similarweb_data['monthly_visits'],
            0.8,
            ['similarweb']
        )

    # Sitemap: ~10 visits per indexed URL per month
    if sitemap_size and sitemap_size > 0:
        sitemap_estimate = sitemap_size * 10
        estimate += sitemap_estimate
        signals += 1
        signals_used.append('sitemap')

    # Social followers: ~2% daily visit rate * 30 days
    if social_followers > 0:
        social_estimate = int(social_followers * 0.02 * 30)
        estimate += social_estimate
        signals += 1
        signals_used.append('social_followers')

    # Reviews: ~50 visits per review
    if review_count > 0:
        review_estimate = review_count * 50
        estimate += review_estimate
        signals += 1
        signals_used.append('review_count')

    # Average across available signals to avoid double-counting
    if signals > 1:
        estimate = estimate // signals

    # Confidence based on number of signals
    confidence_map = {0: 0.0, 1: 0.2, 2: 0.4, 3: 0.6}
    confidence = confidence_map.get(signals, 0.6)

    return (estimate, confidence, signals_used)


def estimate_traffic_from_html(
    html_content: str,
    url: str,
    social_data: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Estimate traffic from pre-scraped HTML and optional social data.

    Args:
        html_content: HTML content of the main page
        url: Website URL
        social_data: Optional dict with social metrics, e.g.:
            {'instagram_followers': 15000, 'facebook_followers': 5000}

    Returns:
        Dict with:
            - success: bool
            - data: dict with estimated_monthly_visits, traffic_confidence, etc.
            - error: str or None
    """
    try:
        soup = BeautifulSoup(html_content, 'lxml')
    except Exception:
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
        except Exception as e:
            return {
                'success': False,
                'data': {},
                'error': f'HTML parsing error: {str(e)}'
            }

    try:
        # Signal 1: Sitemap size
        sitemap_size = _count_sitemap_urls(url)

        # Signal 2: Social followers (from passed-in data)
        social_followers_total = 0
        if social_data:
            for key, value in social_data.items():
                if 'followers' in key.lower() and isinstance(value, (int, float)):
                    social_followers_total += int(value)

        # Signal 3: Review counts
        review_count = _count_reviews(html_content, soup)

        # Signal 4: SimilarWeb (stub)
        domain = urlparse(url).netloc.replace('www.', '')
        similarweb_data = _estimate_from_similarweb(domain)

        # Calculate estimate
        estimated_visits, confidence, signals_used = _calculate_traffic_estimate(
            sitemap_size, social_followers_total, review_count, similarweb_data
        )

        # Build signal details
        signal_details = {}
        if sitemap_size is not None:
            signal_details['sitemap'] = {
                'url_count': sitemap_size,
                'estimated_visits': sitemap_size * 10
            }
        if social_followers_total > 0:
            signal_details['social'] = {
                'total_followers': social_followers_total,
                'estimated_visits': int(social_followers_total * 0.02 * 30)
            }
        if review_count > 0:
            signal_details['reviews'] = {
                'count': review_count,
                'estimated_visits': review_count * 50
            }
        if similarweb_data:
            signal_details['similarweb'] = similarweb_data

        return {
            'success': True,
            'data': {
                'estimated_monthly_visits': estimated_visits,
                'traffic_confidence': confidence,
                'sitemap_size': sitemap_size,
                'review_count': review_count,
                'social_followers_total': social_followers_total,
                'signals_used': signals_used,
                'signal_details': signal_details,
                'similarweb_data': similarweb_data
            },
            'error': None
        }

    except Exception as e:
        return {
            'success': False,
            'data': {},
            'error': f'Traffic estimation error: {str(e)}'
        }


def estimate_traffic(
    url: str,
    social_data: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Estimate traffic for a URL (scrapes first, then analyzes).

    Args:
        url: Website URL
        social_data: Optional dict with social metrics

    Returns:
        Same as estimate_traffic_from_html
    """
    scrape_result = scrape_website(url, timeout=20, parse_html=False)

    if not scrape_result['success']:
        return {
            'success': False,
            'data': {},
            'error': f'Failed to scrape URL: {scrape_result["error"]}'
        }

    return estimate_traffic_from_html(
        scrape_result['data']['html'],
        url,
        social_data
    )


if __name__ == '__main__':
    test_url = sys.argv[1] if len(sys.argv) > 1 else 'https://www.example.com'

    print("Traffic Estimation")
    print("=" * 60)
    print(f"URL: {test_url}")

    # Example social data (in real pipeline, this comes from extract_social_links + apify_instagram)
    test_social = None
    if '--social' in sys.argv:
        test_social = {'instagram_followers': 10000}
        print(f"Social data: {test_social}")

    result = estimate_traffic(test_url, social_data=test_social)
    print(f"\nSuccess: {result['success']}")

    if result['success']:
        data = result['data']
        print(f"  Estimated monthly visits: {data['estimated_monthly_visits']:,}")
        print(f"  Confidence: {data['traffic_confidence']:.1%}")
        print(f"  Sitemap size: {data['sitemap_size'] or 'Not found'}")
        print(f"  Review count: {data['review_count']}")
        print(f"  Social followers total: {data['social_followers_total']:,}")
        print(f"  Signals used: {', '.join(data['signals_used']) or 'None'}")
        if data.get('similarweb_data'):
            print(f"  SimilarWeb: {data['similarweb_data']}")
        else:
            print(f"  SimilarWeb: N/A (set SIMILARWEB_API_KEY)")
        if data.get('signal_details'):
            print(f"\n  Signal details:")
            for signal, details in data['signal_details'].items():
                print(f"    {signal}: {details}")
    else:
        print(f"  Error: {result['error']}")
