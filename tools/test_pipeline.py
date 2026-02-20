"""
Pipeline Test Script for E-Commerce Enrichment Agent

Purpose: Test all tools individually and as a full pipeline
Usage: python test_pipeline.py [url]
Default URL: armatura.com.co
"""

import sys
import os
import json
from typing import Dict, Any

# Add tool paths
BASE_PATH = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_PATH)
sys.path.insert(0, os.path.join(BASE_PATH, 'core'))
sys.path.insert(0, os.path.join(BASE_PATH, 'detection'))
sys.path.insert(0, os.path.join(BASE_PATH, 'social'))
sys.path.insert(0, os.path.join(BASE_PATH, 'ecommerce'))
sys.path.insert(0, os.path.join(BASE_PATH, 'traffic'))
sys.path.insert(0, os.path.join(BASE_PATH, 'contacts'))
sys.path.insert(0, os.path.join(BASE_PATH, 'export'))

# Import tools
from core.url_normalizer import normalize_url, extract_domain
from core.web_scraper import scrape_website
from core.cache_manager import cache_get, cache_set, cache_clear, get_cache_stats
from core.google_search import google_search
from core.resolve_brand_url import resolve_brand_url
from core.input_reader import read_input_list
from core.browser_scraper import browser_scrape, _is_playwright_available
from detection.detect_ecommerce_platform import detect_platform, detect_platform_from_html
from detection.detect_geography import detect_geography, detect_geography_from_html
from detection.detect_fulfillment_provider import detect_fulfillment, detect_fulfillment_from_html
from social.extract_social_links import extract_social_links, extract_social_links_from_html
from social.apify_instagram import get_instagram_metrics, extract_instagram_username
from ecommerce.scrape_product_catalog import scrape_product_catalog
from traffic.estimate_traffic import estimate_traffic, estimate_traffic_from_html
from contacts.apollo_enrichment import apollo_enrich
from export.google_sheets_writer import get_gspread_client, create_or_open_spreadsheet, append_rows, enrichment_result_to_row


def print_header(title: str):
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def print_result(label: str, value: Any, indent: int = 2):
    prefix = " " * indent
    if isinstance(value, dict):
        print(f"{prefix}{label}:")
        for k, v in value.items():
            print(f"{prefix}  {k}: {v}")
    elif isinstance(value, list):
        print(f"{prefix}{label}: {', '.join(str(v) for v in value) if value else 'None'}")
    else:
        print(f"{prefix}{label}: {value}")


def test_url_normalizer(raw_url: str) -> Dict[str, Any]:
    """Test 1: URL Normalization"""
    print_header("TEST 1: URL Normalizer")
    print(f"  Input: {raw_url}")

    result = normalize_url(raw_url)

    if result['success']:
        print(f"  Status: PASS")
        print_result("Normalized URL", result['data'].get('url'))
        print_result("Domain", result['data'].get('domain'))
        print_result("Scheme", result['data'].get('scheme'))
    else:
        print(f"  Status: FAIL")
        print_result("Error", result.get('error'))

    return result


def test_web_scraper(url: str) -> Dict[str, Any]:
    """Test 2: Web Scraper"""
    print_header("TEST 2: Web Scraper")
    print(f"  URL: {url}")

    result = scrape_website(url)

    if result['success']:
        data = result['data']
        print(f"  Status: PASS")
        print_result("HTTP Status", data.get('status_code'))
        print_result("Final URL", data.get('url'))
        print_result("Content Size", f"{data.get('size', 0):,} bytes")
        print_result("Has BeautifulSoup", data.get('soup') is not None)
        if data.get('soup') and data['soup'].title:
            print_result("Page Title", data['soup'].title.string[:60] if data['soup'].title.string else 'N/A')
    else:
        print(f"  Status: FAIL")
        print_result("Error", result.get('error'))

    return result


def test_platform_detection(url: str, html_content: str = None, headers: dict = None) -> Dict[str, Any]:
    """Test 3: Platform Detection"""
    print_header("TEST 3: Platform Detection")
    print(f"  URL: {url}")

    if html_content:
        result = detect_platform_from_html(html_content, url, headers or {})
    else:
        result = detect_platform(url)

    if result['success']:
        data = result['data']
        print(f"  Status: PASS")
        print_result("Platform", data.get('platform'))
        print_result("Confidence", f"{data.get('confidence', 0) * 100:.0f}%")
        print_result("Version", data.get('version', 'Unknown'))

        evidence = data.get('evidence', [])[:5]
        if evidence:
            print("  Evidence (top 5):")
            for ev in evidence:
                print(f"    - {ev}")

        scores = data.get('scores', {})
        if scores:
            print("  Platform Scores:")
            for platform, score in list(scores.items())[:5]:
                print(f"    - {platform}: {score}")
    else:
        print(f"  Status: FAIL")
        print_result("Error", result.get('error'))

    return result


def test_geography_detection(url: str, html_content: str = None) -> Dict[str, Any]:
    """Test 4: Geography Detection"""
    print_header("TEST 4: Geography Detection")
    print(f"  URL: {url}")

    if html_content:
        result = detect_geography_from_html(html_content, url)
    else:
        result = detect_geography(url)

    if result['success']:
        data = result['data']
        print(f"  Status: PASS")
        print_result("Countries", data.get('countries', []))
        print_result("Primary Country", data.get('primary_country'))
        print_result("Confidence", f"{data.get('confidence', 0) * 100:.0f}%")

        evidence = data.get('evidence', {})
        if evidence:
            print("  Evidence by Country:")
            for country, evidences in evidence.items():
                print(f"    {country}:")
                for ev in evidences[:3]:
                    print(f"      - {ev}")

        scores = data.get('scores', {})
        if scores:
            print("  Country Scores:")
            for country, score in scores.items():
                print(f"    - {country}: {score}")
    else:
        print(f"  Status: FAIL")
        print_result("Error", result.get('error'))

    return result


def test_social_links(url: str, html_content: str = None) -> Dict[str, Any]:
    """Test 5: Social Media Link Extraction"""
    print_header("TEST 5: Social Media Links")
    print(f"  URL: {url}")

    if html_content:
        result = extract_social_links_from_html(html_content, url)
    else:
        result = extract_social_links(url)

    if result['success']:
        data = result['data']
        if data:
            print(f"  Status: PASS")
            print(f"  Found {len(data)} social media links:")
            for platform, link in data.items():
                print(f"    - {platform.capitalize()}: {link}")
        else:
            print(f"  Status: PASS (no social links found)")
    else:
        print(f"  Status: FAIL")
        print_result("Error", result.get('error'))

    return result


def test_instagram_metrics(instagram_url: str) -> Dict[str, Any]:
    """Test 5b: Instagram Metrics via Apify"""
    print_header("TEST 5b: Instagram Metrics (Apify)")

    username = extract_instagram_username(instagram_url)
    print(f"  Instagram URL: {instagram_url}")
    print(f"  Username: @{username}")

    result = get_instagram_metrics(instagram_url, include_posts=True, posts_limit=20)

    if result['success']:
        data = result['data']
        print(f"  Status: PASS")
        print_result("Followers", f"{data.get('followers', 0):,}")
        print_result("Following", f"{data.get('following', 0):,}")
        print_result("Total Posts", f"{data.get('posts_count', 0):,}")
        print_result("Posts (30 days)", data.get('posts_last_30d', 0))
        print_result("Engagement Rate", f"{data.get('engagement_rate', 0):.2f}%")
        print_result("Verified", data.get('is_verified', False))
        print_result("Private", data.get('is_private', False))

        if data.get('full_name'):
            print_result("Full Name", data['full_name'])
        if data.get('biography'):
            bio = data['biography'][:80] + '...' if len(data.get('biography', '')) > 80 else data.get('biography', '')
            # Encode to handle unicode/emoji characters on Windows console
            bio_safe = bio.encode('ascii', 'replace').decode('ascii')
            print_result("Bio", bio_safe)
    else:
        print(f"  Status: FAIL")
        print_result("Error", result.get('error'))

    return result


def test_product_catalog(url: str) -> Dict[str, Any]:
    """Test 6: Product Catalog Scraper"""
    print_header("TEST 6: Product Catalog")
    print(f"  URL: {url}")

    result = scrape_product_catalog(url)

    if result['success']:
        data = result['data']
        print(f"  Status: PASS")
        print_result("Product Count", f"{data.get('product_count', 0):,}")
        print_result("Currency", data.get('currency'))
        print_result("Average Price", f"{data.get('currency', '')} {data.get('avg_price', 0):,.2f}")

        price_range = data.get('price_range', {})
        print_result("Price Range", f"{data.get('currency', '')} {price_range.get('min', 0):,.2f} - {price_range.get('max', 0):,.2f}")
        print_result("Products on Page", data.get('products_on_page', 0))

        samples = data.get('sample_products', [])[:5]
        if samples:
            print("  Sample Products:")
            for p in samples:
                name = p.get('name', 'Unknown')[:40]
                price = p.get('price', 0)
                print(f"    - {name}: {data.get('currency', '')} {price:,.2f}")
    else:
        print(f"  Status: FAIL")
        print_result("Error", result.get('error'))

    return result


def test_cache_manager() -> Dict[str, Any]:
    """Test 7: Cache Manager"""
    print_header("TEST 7: Cache Manager")

    # Test set/get cycle
    set_result = cache_set('test.pipeline.com', 'test_tool', {'test': True, 'value': 42})
    print(f"  SET: {'PASS' if set_result['success'] else 'FAIL'}")

    get_result = cache_get('test.pipeline.com', 'test_tool')
    print(f"  GET: {'PASS (cache hit)' if get_result['success'] else 'FAIL (cache miss)'}")

    if get_result['success']:
        print_result("Cached data", get_result['data'])

    # Clean up
    cache_clear('test.pipeline.com')

    stats = get_cache_stats()
    if stats['success']:
        print_result("Cache stats", f"{stats['data']['total_entries']} entries, {stats['data']['total_size_bytes']} bytes")

    result = {'success': set_result['success'] and get_result['success'], 'data': get_result.get('data', {}), 'error': None}
    print(f"  Status: {'PASS' if result['success'] else 'FAIL'}")
    return result


def test_traffic_estimation(url: str, html_content: str = None, social_data: dict = None) -> Dict[str, Any]:
    """Test 8: Traffic Estimation"""
    print_header("TEST 8: Traffic Estimation")
    print(f"  URL: {url}")

    if html_content:
        result = estimate_traffic_from_html(html_content, url, social_data)
    else:
        result = estimate_traffic(url, social_data)

    if result['success']:
        data = result['data']
        print(f"  Status: PASS")
        print_result("Est. Monthly Visits", f"{data.get('estimated_monthly_visits', 0):,}")
        print_result("Confidence", f"{data.get('traffic_confidence', 0)*100:.0f}%")
        print_result("Sitemap Size", data.get('sitemap_size', 'Not found'))
        print_result("Review Count", data.get('review_count', 0))
        print_result("Social Followers", f"{data.get('social_followers_total', 0):,}")
        print_result("Signals Used", ', '.join(data.get('signals_used', [])) or 'None')
    else:
        print(f"  Status: FAIL")
        print_result("Error", result.get('error'))

    return result


def test_apollo_enrichment(domain: str) -> Dict[str, Any]:
    """Test 9: Apollo.io Enrichment"""
    print_header("TEST 9: Apollo.io Enrichment")
    print(f"  Domain: {domain}")

    result = apollo_enrich(domain)

    if result['success']:
        data = result['data']
        source = data.get('source', 'unknown')
        print(f"  Status: PASS ({source} mode)")

        company = data.get('company', {})
        if company.get('company_name'):
            print_result("Company", company['company_name'])
            print_result("Industry", company.get('industry', 'N/A'))
            print_result("Employees", company.get('employee_range', 'N/A'))
        else:
            print(f"  Company: No data (source: {source})")

        contacts = data.get('contacts', [])
        print_result("Contacts found", len(contacts))
        for c in contacts[:3]:
            print(f"    - {c['name']} ({c['title']}): {c.get('email', 'N/A')}")
    else:
        print(f"  Status: FAIL")
        print_result("Error", result.get('error'))

    return result


def test_fulfillment_detection(url: str, html_content: str = None) -> Dict[str, Any]:
    """Test 10: Fulfillment Provider Detection"""
    print_header("TEST 10: Fulfillment Provider Detection")
    print(f"  URL: {url}")

    if html_content:
        result = detect_fulfillment_from_html(html_content, url)
    else:
        result = detect_fulfillment(url)

    if result['success']:
        data = result['data']
        print(f"  Status: PASS")
        print_result("Detection Method", data.get('detection_method'))
        print_result("Providers", ', '.join(data.get('providers_detected', [])) or 'None detected')
        print_result("Primary Provider", data.get('primary_provider', 'None'))
        print_result("Confidence", f"{data.get('confidence', 0)*100:.0f}%")

        if data.get('shipping_options'):
            print("  Shipping Options:")
            for opt in data['shipping_options'][:5]:
                print(f"    - {opt}")

        evidence = data.get('evidence', [])
        if evidence:
            print(f"  Evidence ({len(evidence)} items):")
            for ev in evidence[:5]:
                print(f"    - [{ev['source']}] {ev['provider']} ({ev['market']})")
    else:
        print(f"  Status: FAIL")
        print_result("Error", result.get('error'))

    return result


def test_google_search() -> Dict[str, Any]:
    """Test 11: Google Search (Serper API)"""
    print_header("TEST 11: Google Search (Serper API)")
    query = "Armatura Colombia ecommerce"
    print(f"  Query: {query}")

    result = google_search(query, num_results=3)

    if result['success']:
        data = result['data']
        print(f"  Status: PASS")
        print_result("Credits Used", data.get('credits_used', 'N/A'))
        organic = data.get('organic', [])
        print_result("Organic Results", len(organic))
        for r in organic[:3]:
            print(f"    [{r.get('position')}] {r.get('title', '')[:60]}")
            print(f"        {r.get('link', '')}")
        related = data.get('related_searches', [])
        if related:
            print_result("Related Searches", ', '.join(related[:3]))
    else:
        print(f"  Status: FAIL")
        print_result("Error", result.get('error'))

    return result


def test_resolve_brand_url() -> Dict[str, Any]:
    """Test 12: Resolve Brand URL"""
    print_header("TEST 12: Resolve Brand URL")

    # Test 1: URL pass-through
    url_input = "armatura.com.co"
    print(f"  Test A - URL input: {url_input}")
    result_url = resolve_brand_url(url_input)
    if result_url['success']:
        print(f"    PASS: URL={result_url['data']['url']}, Searched={result_url['data']['was_searched']}")
    else:
        print(f"    FAIL: {result_url.get('error')}")

    # Test 2: Brand name search (consumes 1 Serper credit)
    brand_input = "Armatura Colombia"
    print(f"  Test B - Brand name: {brand_input}")
    result_brand = resolve_brand_url(brand_input)
    if result_brand['success']:
        print(f"    PASS: URL={result_brand['data']['url']}, Searched={result_brand['data']['was_searched']}")
    else:
        print(f"    FAIL: {result_brand.get('error')}")

    # Overall result
    overall_success = result_url['success'] and result_brand['success']
    print(f"  Status: {'PASS' if overall_success else 'FAIL'}")

    return {
        'success': overall_success,
        'data': {'url_passthrough': result_url, 'brand_search': result_brand},
        'error': None if overall_success else 'One or more sub-tests failed'
    }


def test_input_reader() -> Dict[str, Any]:
    """Test 13: Input Reader"""
    print_header("TEST 13: Input Reader")

    # Create a temporary test file
    tmp_dir = os.path.join(BASE_PATH, '..', '.tmp')
    os.makedirs(tmp_dir, exist_ok=True)
    test_file = os.path.join(tmp_dir, 'test_input.txt')

    test_content = """# Test input file for pipeline
armatura.com.co
https://www.trueshop.co
armatura.com.co
Bronzini Colombia

# Another comment
https://www.ejemplo.mx
"""
    with open(test_file, 'w', encoding='utf-8') as f:
        f.write(test_content)

    print(f"  File: {test_file}")
    result = read_input_list(test_file)

    if result['success']:
        data = result['data']
        print(f"  Status: PASS")
        print_result("Total Lines", data.get('total_lines'))
        print_result("Valid Entries", data.get('valid_entries'))
        print_result("Duplicates Removed", data.get('duplicates_removed'))
        print_result("Comments Skipped", data.get('comments_skipped'))
        print("  Entries:")
        for entry in data.get('entries', []):
            print(f"    [{entry['type']}] {entry['cleaned']} (domain: {entry['domain']})")
    else:
        print(f"  Status: FAIL")
        print_result("Error", result.get('error'))

    # Clean up
    try:
        os.remove(test_file)
    except Exception:
        pass

    return result


def test_browser_scraper(url: str) -> Dict[str, Any]:
    """Test 14: Browser Scraper (Playwright)"""
    print_header("TEST 14: Browser Scraper (Playwright)")
    print(f"  URL: {url}")
    print(f"  Playwright Available: {_is_playwright_available()}")

    if not _is_playwright_available():
        print("  Status: SKIPPED (Playwright not installed)")
        print("  Install with: pip install playwright && playwright install chromium")
        return {'success': True, 'data': {'skipped': True}, 'error': None}

    result = browser_scrape(url, wait_for='networkidle', timeout=30000)

    if result['success']:
        data = result['data']
        print(f"  Status: PASS")
        print_result("HTTP Status", data.get('status_code'))
        print_result("Final URL", data.get('url'))
        print_result("Content Size", f"{data.get('size', 0):,} bytes")
        print_result("Has BeautifulSoup", data.get('soup') is not None)
        if data.get('soup') and data['soup'].title:
            print_result("Page Title", data['soup'].title.string[:60] if data['soup'].title.string else 'N/A')
    else:
        print(f"  Status: FAIL")
        print_result("Error", result.get('error'))

    return result


def test_google_sheets_writer() -> Dict[str, Any]:
    """Test 15: Google Sheets Writer"""
    print_header("TEST 15: Google Sheets Writer")

    try:
        # Step 1: Authenticate
        client = get_gspread_client()
        print("  Auth: PASS")

        # Step 2: Open existing spreadsheet
        test_sheet_url = "https://docs.google.com/spreadsheets/d/1o3cO55kjEtOX6sbmmWE9Gno0eetJyX1B-fANGo6gGu4/edit"
        sheet_result = create_or_open_spreadsheet(client, spreadsheet_url=test_sheet_url)
        if not sheet_result['success']:
            print(f"  Status: FAIL")
            print_result("Error", sheet_result.get('error'))
            return sheet_result

        sheet_url = sheet_result['data']['sheet_url']
        ws = sheet_result['data']['worksheet']
        print(f"  Open Sheet: PASS")
        print_result("Sheet URL", sheet_url)

        # Step 3: Write a test row
        test_data = {
            "url": "https://test-pipeline.example.com",
            "cms": "Shopify",
            "cms_confidence": 0.95,
            "geography": "Colombia",
            "geography_confidence": 0.87,
            "workflow_log": "Pipeline test row - safe to delete",
        }
        row = enrichment_result_to_row(test_data)
        write_result = append_rows(ws, [row])

        if write_result['success']:
            print(f"  Write Row: PASS ({write_result['data']['rows_written']} row)")
        else:
            print(f"  Write Row: FAIL - {write_result.get('error')}")

        overall = sheet_result['success'] and write_result['success']
        print(f"  Status: {'PASS' if overall else 'FAIL'}")

        return {
            'success': overall,
            'data': {'sheet_url': sheet_url, 'rows_written': write_result['data']['rows_written']},
            'error': None
        }

    except Exception as e:
        print(f"  Status: FAIL")
        print_result("Error", str(e))
        return {'success': False, 'data': {}, 'error': str(e)}


def run_full_pipeline(raw_url: str) -> Dict[str, Any]:
    """Run all tests in sequence, reusing scraped content where possible"""
    print_header("FULL PIPELINE TEST")
    print(f"  Target: {raw_url}")

    results = {
        'url_normalization': None,
        'web_scraper': None,
        'platform_detection': None,
        'geography_detection': None,
        'social_links': None,
        'instagram_metrics': None,
        'product_catalog': None,
        'cache_manager': None,
        'traffic_estimation': None,
        'apollo_enrichment': None,
        'fulfillment_detection': None,
        'google_search': None,
        'resolve_brand_url': None,
        'input_reader': None,
        'browser_scraper': None,
        'google_sheets_writer': None,
        'summary': {
            'passed': 0,
            'failed': 0,
            'errors': []
        }
    }

    # Test 1: URL Normalization
    norm_result = test_url_normalizer(raw_url)
    results['url_normalization'] = norm_result
    if norm_result['success']:
        results['summary']['passed'] += 1
        url = norm_result['data']['url']
    else:
        results['summary']['failed'] += 1
        results['summary']['errors'].append(f"URL Normalization: {norm_result.get('error')}")
        return results

    # Test 2: Web Scraper
    scrape_result = test_web_scraper(url)
    results['web_scraper'] = {
        'success': scrape_result['success'],
        'error': scrape_result.get('error'),
        'status_code': scrape_result.get('data', {}).get('status_code'),
        'size': scrape_result.get('data', {}).get('size')
    }

    if scrape_result['success']:
        results['summary']['passed'] += 1
        html_content = scrape_result['data']['html']
        headers = scrape_result['data']['headers']
    else:
        results['summary']['failed'] += 1
        results['summary']['errors'].append(f"Web Scraper: {scrape_result.get('error')}")
        return results

    # Test 3: Platform Detection (using cached HTML)
    platform_result = test_platform_detection(url, html_content, headers)
    results['platform_detection'] = platform_result
    if platform_result['success']:
        results['summary']['passed'] += 1
    else:
        results['summary']['failed'] += 1
        results['summary']['errors'].append(f"Platform Detection: {platform_result.get('error')}")

    # Test 4: Geography Detection (using cached HTML)
    geo_result = test_geography_detection(url, html_content)
    results['geography_detection'] = geo_result
    if geo_result['success']:
        results['summary']['passed'] += 1
    else:
        results['summary']['failed'] += 1
        results['summary']['errors'].append(f"Geography Detection: {geo_result.get('error')}")

    # Test 5: Social Links (using cached HTML)
    social_result = test_social_links(url, html_content)
    results['social_links'] = social_result
    if social_result['success']:
        results['summary']['passed'] += 1
    else:
        results['summary']['failed'] += 1
        results['summary']['errors'].append(f"Social Links: {social_result.get('error')}")

    # Test 5b: Instagram Metrics (if Instagram link found)
    if social_result['success'] and social_result.get('data', {}).get('instagram'):
        instagram_url = social_result['data']['instagram']
        instagram_result = test_instagram_metrics(instagram_url)
        results['instagram_metrics'] = instagram_result
        if instagram_result['success']:
            results['summary']['passed'] += 1
        else:
            results['summary']['failed'] += 1
            results['summary']['errors'].append(f"Instagram Metrics: {instagram_result.get('error')}")
    else:
        print_header("TEST 5b: Instagram Metrics (Apify)")
        print("  Status: SKIPPED (no Instagram link found)")

    # Test 6: Product Catalog (requires new scrapes for product pages)
    catalog_result = test_product_catalog(url)
    results['product_catalog'] = catalog_result
    if catalog_result['success']:
        results['summary']['passed'] += 1
    else:
        results['summary']['failed'] += 1
        results['summary']['errors'].append(f"Product Catalog: {catalog_result.get('error')}")

    # Test 7: Cache Manager (standalone)
    cache_result = test_cache_manager()
    results['cache_manager'] = cache_result
    if cache_result['success']:
        results['summary']['passed'] += 1
    else:
        results['summary']['failed'] += 1
        results['summary']['errors'].append(f"Cache Manager: {cache_result.get('error')}")

    # Test 8: Traffic Estimation (using cached HTML + social data from test 5)
    social_data_for_traffic = None
    if results.get('instagram_metrics') and results['instagram_metrics'].get('success'):
        ig_data = results['instagram_metrics'].get('data', {})
        social_data_for_traffic = {'instagram_followers': ig_data.get('followers', 0)}

    traffic_result = test_traffic_estimation(url, html_content, social_data_for_traffic)
    results['traffic_estimation'] = traffic_result
    if traffic_result['success']:
        results['summary']['passed'] += 1
    else:
        results['summary']['failed'] += 1
        results['summary']['errors'].append(f"Traffic Estimation: {traffic_result.get('error')}")

    # Test 9: Apollo Enrichment (using domain from test 1)
    domain = extract_domain(url)
    apollo_result = test_apollo_enrichment(domain)
    results['apollo_enrichment'] = apollo_result
    if apollo_result['success']:
        results['summary']['passed'] += 1
    else:
        results['summary']['failed'] += 1
        results['summary']['errors'].append(f"Apollo Enrichment: {apollo_result.get('error')}")

    # Test 10: Fulfillment Detection (passive mode using cached HTML)
    fulfillment_result = test_fulfillment_detection(url, html_content)
    results['fulfillment_detection'] = fulfillment_result
    if fulfillment_result['success']:
        results['summary']['passed'] += 1
    else:
        results['summary']['failed'] += 1
        results['summary']['errors'].append(f"Fulfillment Detection: {fulfillment_result.get('error')}")

    # Test 11: Google Search (Serper API - consumes 1 credit)
    search_result = test_google_search()
    results['google_search'] = search_result
    if search_result['success']:
        results['summary']['passed'] += 1
    else:
        results['summary']['failed'] += 1
        results['summary']['errors'].append(f"Google Search: {search_result.get('error')}")

    # Test 12: Resolve Brand URL (consumes 1 Serper credit for brand name test)
    resolve_result = test_resolve_brand_url()
    results['resolve_brand_url'] = resolve_result
    if resolve_result['success']:
        results['summary']['passed'] += 1
    else:
        results['summary']['failed'] += 1
        results['summary']['errors'].append(f"Resolve Brand URL: {resolve_result.get('error')}")

    # Test 13: Input Reader (standalone, no API calls)
    input_result = test_input_reader()
    results['input_reader'] = input_result
    if input_result['success']:
        results['summary']['passed'] += 1
    else:
        results['summary']['failed'] += 1
        results['summary']['errors'].append(f"Input Reader: {input_result.get('error')}")

    # Test 14: Browser Scraper (Playwright - skips if not installed)
    browser_result = test_browser_scraper(url)
    results['browser_scraper'] = browser_result
    if browser_result['success']:
        results['summary']['passed'] += 1
    else:
        results['summary']['failed'] += 1
        results['summary']['errors'].append(f"Browser Scraper: {browser_result.get('error')}")

    # Test 15: Google Sheets Writer (creates a test spreadsheet)
    sheets_result = test_google_sheets_writer()
    results['google_sheets_writer'] = sheets_result
    if sheets_result['success']:
        results['summary']['passed'] += 1
    else:
        results['summary']['failed'] += 1
        results['summary']['errors'].append(f"Google Sheets Writer: {sheets_result.get('error')}")

    # Print Summary
    print_header("PIPELINE SUMMARY")
    total = results['summary']['passed'] + results['summary']['failed']
    print(f"  Total Tests: {total}")
    print(f"  Passed: {results['summary']['passed']}")
    print(f"  Failed: {results['summary']['failed']}")

    if results['summary']['errors']:
        print("\n  Errors:")
        for error in results['summary']['errors']:
            print(f"    - {error}")

    # Print enrichment summary
    if results['summary']['passed'] >= 4:
        print_header("ENRICHMENT RESULTS")

        if results['platform_detection'] and results['platform_detection']['success']:
            pd = results['platform_detection']['data']
            print(f"  Platform: {pd.get('platform')} ({pd.get('confidence', 0)*100:.0f}% confidence)")

        if results['geography_detection'] and results['geography_detection']['success']:
            gd = results['geography_detection']['data']
            print(f"  Geography: {gd.get('primary_country')} (Countries: {', '.join(gd.get('countries', []))})")

        if results['social_links'] and results['social_links']['success']:
            sl = results['social_links']['data']
            if sl:
                print(f"  Social: {', '.join(sl.keys())}")
            else:
                print(f"  Social: None found")

        if results['instagram_metrics'] and results['instagram_metrics']['success']:
            ig = results['instagram_metrics']['data']
            print(f"  Instagram: @{ig.get('username')} | {ig.get('followers', 0):,} followers | {ig.get('engagement_rate', 0):.2f}% engagement")

        if results['product_catalog'] and results['product_catalog']['success']:
            pc = results['product_catalog']['data']
            print(f"  Catalog: {pc.get('product_count'):,} products, avg {pc.get('currency')} {pc.get('avg_price'):,.2f}")

        if results['traffic_estimation'] and results['traffic_estimation']['success']:
            te = results['traffic_estimation']['data']
            print(f"  Traffic: ~{te.get('estimated_monthly_visits', 0):,} visits/mo ({te.get('traffic_confidence', 0)*100:.0f}% confidence)")

        if results['apollo_enrichment'] and results['apollo_enrichment']['success']:
            ae = results['apollo_enrichment']['data']
            source = ae.get('source', 'unknown')
            contacts = ae.get('contacts', [])
            print(f"  Contacts: {len(contacts)} found ({source} mode)")

        if results['fulfillment_detection'] and results['fulfillment_detection']['success']:
            fd = results['fulfillment_detection']['data']
            providers = fd.get('providers_detected', [])
            print(f"  Fulfillment: {', '.join(providers) if providers else 'None detected'} ({fd.get('detection_method')})")

        if results['google_search'] and results['google_search']['success']:
            gs = results['google_search']['data']
            print(f"  Google Search: {len(gs.get('organic', []))} results, {gs.get('credits_used', 'N/A')} credit(s)")

        if results['resolve_brand_url'] and results['resolve_brand_url']['success']:
            print(f"  Brand Resolver: URL passthrough + brand search OK")

        if results['input_reader'] and results['input_reader']['success']:
            ir = results['input_reader']['data']
            print(f"  Input Reader: {ir.get('valid_entries')} entries, {ir.get('duplicates_removed')} duplicates removed")

        if results['browser_scraper'] and results['browser_scraper']['success']:
            bs = results['browser_scraper']['data']
            if bs.get('skipped'):
                print(f"  Browser Scraper: SKIPPED (Playwright not installed)")
            else:
                print(f"  Browser Scraper: {bs.get('size', 0):,} bytes rendered")

        if results['google_sheets_writer'] and results['google_sheets_writer']['success']:
            sw = results['google_sheets_writer']['data']
            print(f"  Sheets Writer: {sw.get('sheet_url', 'N/A')}")

    return results


if __name__ == '__main__':
    # Get URL from command line or use default
    if len(sys.argv) > 1:
        test_url = sys.argv[1]
    else:
        test_url = 'armatura.com.co'

    print("\n" + "=" * 70)
    print("  E-COMMERCE ENRICHMENT AGENT - PIPELINE TEST")
    print("=" * 70)
    print(f"\n  Target URL: {test_url}")
    print(f"  Test Mode: Full Pipeline")

    # Run all tests
    results = run_full_pipeline(test_url)

    print("\n" + "=" * 70)
    print("  TEST COMPLETE")
    print("=" * 70 + "\n")
