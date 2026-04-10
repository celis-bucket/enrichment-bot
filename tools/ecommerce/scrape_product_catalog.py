"""
Product Catalog Scraper Tool

Purpose: Analyze product catalog for size, pricing, and statistics
Inputs: URL, platform type (optional)
Outputs: Product count, average price, price range, currency
Dependencies: requests, beautifulsoup4, re

Strategy:
1. Find product listing pages (/products, /shop, /collections)
2. Extract product information (name, price)
3. Count products or estimate from pagination
4. Calculate price statistics
"""

import re
from typing import Dict, Any, List, Optional
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import statistics

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from core.web_scraper import scrape_website


# Common product listing URL patterns
PRODUCT_LISTING_PATTERNS = [
    '/products',
    '/shop',
    '/store',
    '/collections',
    '/catalog',
    '/tienda',
    '/productos',
]

# Currency symbols and codes
CURRENCY_PATTERNS = {
    'USD': [r'\$', r'USD', r'US\$'],
    'COP': [r'COP', r'COL\$'],
    'MXN': [r'MXN', r'MEX\$', r'\$'],  # $ is ambiguous
    'EUR': [r'€', r'EUR'],
    'GBP': [r'£', r'GBP'],
}


def extract_price(text: str) -> Optional[float]:
    """
    Extract price from text string.

    Args:
        text: Text containing price

    Returns:
        Price as float or None
    """
    # Remove currency symbols and normalize
    text = text.replace(',', '').replace(' ', '')

    # Look for price patterns
    # Matches: $100, 100.00, $1,234.56, etc.
    patterns = [
        r'[\$€£]?\s*(\d+\.?\d*)',  # $100 or 100.00
        r'(\d+)[\.,](\d{2})',  # 100.50 or 100,50
    ]

    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            try:
                if len(match.groups()) == 1:
                    return float(match.group(1))
                else:
                    # Handle decimal separator
                    whole = match.group(1)
                    decimal = match.group(2)
                    return float(f"{whole}.{decimal}")
            except Exception as e:
                print(f"Warning: Price extraction failed for '{text[:50]}': {e}")
                continue

    return None


def detect_currency(html_content: str, url: str) -> str:
    """
    Detect currency used on the page.

    Args:
        html_content: HTML content
        url: Page URL

    Returns:
        Currency code (USD, COP, MXN, etc.)
    """
    # Check domain TLD
    if '.co' in url and 'colombia' in html_content.lower():
        return 'COP'
    elif '.mx' in url:
        return 'MXN'

    # Look for currency codes in HTML
    html_lower = html_content.lower()

    for currency, patterns in CURRENCY_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, html_content, re.IGNORECASE):
                # Prioritize explicit currency codes
                if len(pattern) == 3 and pattern.isupper():
                    return currency

    # Default to USD
    return 'USD'


def scrape_product_page(url: str, soup: BeautifulSoup) -> List[Dict[str, Any]]:
    """
    Extract products from a product listing page.

    Args:
        url: Page URL
        soup: BeautifulSoup object

    Returns:
        List of product dicts with 'name' and 'price'
    """
    products = []

    # Common product container selectors
    product_selectors = [
        {'class': re.compile(r'product-item|product-card|product-grid-item', re.I)},
        {'class': re.compile(r'item|card', re.I)},
        {'itemprop': 'itemListElement'},
    ]

    for selector in product_selectors:
        product_elements = soup.find_all(['div', 'article', 'li'], selector)

        if product_elements:
            for element in product_elements:
                product_data = {}

                # Extract product name
                name_elem = element.find(['h2', 'h3', 'h4', 'a'], class_=re.compile(r'title|name|product', re.I))
                if name_elem:
                    product_data['name'] = name_elem.get_text(strip=True)

                # Extract price
                price_elem = element.find(['span', 'div', 'p'], class_=re.compile(r'price', re.I))
                if price_elem:
                    price_text = price_elem.get_text(strip=True)
                    price = extract_price(price_text)
                    if price:
                        product_data['price'] = price

                # Only add if we found at least a name or price
                if product_data:
                    products.append(product_data)

            # If we found products, break
            if products:
                break

    return products


def estimate_total_products(soup: BeautifulSoup, products_per_page: int) -> Optional[int]:
    """
    Estimate total products from pagination.

    Args:
        soup: BeautifulSoup object
        products_per_page: Number of products on current page

    Returns:
        Estimated total products or None
    """
    # Look for pagination
    pagination = soup.find(['nav', 'div', 'ul'], class_=re.compile(r'paginat', re.I))

    if pagination:
        # Try to find last page number
        page_links = pagination.find_all('a')
        max_page = 1

        for link in page_links:
            text = link.get_text(strip=True)
            # Try to extract page number
            match = re.search(r'(\d+)', text)
            if match:
                page_num = int(match.group(1))
                max_page = max(max_page, page_num)

        if max_page > 1:
            return max_page * products_per_page

    # Look for "Showing X of Y" text
    showing_text = soup.find(string=re.compile(r'showing \d+ of \d+|mostrando \d+ de \d+', re.I))
    if showing_text:
        match = re.search(r'of (\d+)|de (\d+)', showing_text, re.I)
        if match:
            total = match.group(1) or match.group(2)
            return int(total)

    return None


def scrape_vtex_api(base_url: str) -> Dict[str, Any]:
    """
    Scrape products from VTEX's public catalog search API.

    Args:
        base_url: Base URL of the VTEX store

    Returns:
        Dict with success, data, error
    """
    import requests

    parsed = urlparse(base_url)
    store_base = f"{parsed.scheme}://{parsed.netloc}"

    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json',
        }

        all_products = []
        page_size = 50
        max_pages = 3  # cap to avoid timeouts

        for page in range(max_pages):
            _from = page * page_size
            _to = _from + page_size - 1
            api_url = f"{store_base}/api/catalog_system/pub/products/search?_from={_from}&_to={_to}"

            response = requests.get(api_url, headers=headers, timeout=20)
            # VTEX returns 206 (Partial Content) when more pages exist, 200 on the last page
            if response.status_code not in (200, 206):
                if page == 0:
                    return {'success': False, 'data': {}, 'error': f'VTEX API returned {response.status_code}'}
                break

            try:
                batch = response.json()
            except Exception:
                break

            if not batch:
                break

            all_products.extend(batch)

            # If fewer results than requested, we've hit the end
            if len(batch) < page_size:
                break

        if not all_products:
            return {'success': False, 'data': {}, 'error': 'No products in VTEX API response'}

        prices = []
        sample_products = []

        for product in all_products:
            # Skip inactive VTEX products
            if product.get('isActive') is False:
                continue

            title = product.get('productName', 'Unknown')
            try:
                price = product['items'][0]['sellers'][0]['commertialOffer']['Price']
                if price and price > 0:
                    prices.append(float(price))
                    sample_products.append({'name': title, 'price': float(price)})
                else:
                    sample_products.append({'name': title})
            except (KeyError, IndexError, TypeError):
                sample_products.append({'name': title})

        # Estimate total: if we got max_pages * page_size results, there are likely more
        product_count = len(all_products)
        if product_count == max_pages * page_size:
            # Conservatively indicate there are more — fetch one extra check
            try:
                check_url = f"{store_base}/api/catalog_system/pub/products/search?_from={product_count}&_to={product_count}"
                check_resp = requests.get(check_url, headers=headers, timeout=10)
                if check_resp.status_code == 200 and check_resp.json():
                    product_count = product_count  # still just our sample; mark as partial

            except Exception:
                pass

        if not prices:
            return {
                'success': True,
                'data': {
                    'product_count': product_count,
                    'avg_price': None,
                    'price_range': {'min': None, 'max': None},
                    'currency': 'COP' if parsed.netloc.endswith('.co') else 'USD',
                    'sample_products': sample_products[:10],
                    'products_on_page': len(all_products),
                    'source': 'vtex_api',
                },
                'error': None,
            }

        avg_price = statistics.mean(prices)
        currency = 'COP' if avg_price > 10000 or parsed.netloc.endswith('.co') else 'USD'
        if parsed.netloc.endswith('.mx'):
            currency = 'MXN'

        return {
            'success': True,
            'data': {
                'product_count': product_count,
                'avg_price': round(avg_price, 2),
                'price_range': {
                    'min': round(min(prices), 2),
                    'max': round(max(prices), 2),
                },
                'currency': currency,
                'sample_products': sample_products[:10],
                'products_on_page': len(all_products),
                'source': 'vtex_api',
            },
            'error': None,
        }

    except requests.exceptions.RequestException as e:
        return {'success': False, 'data': {}, 'error': f'VTEX API request failed: {str(e)}'}
    except Exception as e:
        return {'success': False, 'data': {}, 'error': f'VTEX API error: {str(e)}'}


def scrape_shopify_api(base_url: str) -> Dict[str, Any]:
    """
    Scrape products from Shopify's JSON API.

    Args:
        base_url: Base URL of the Shopify store

    Returns:
        Dict with success, data, error
    """
    import requests

    # Normalize URL to get base
    from urllib.parse import urlparse
    parsed = urlparse(base_url)
    api_url = f"{parsed.scheme}://{parsed.netloc}/products.json?limit=250"

    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json'
        }
        response = requests.get(api_url, headers=headers, timeout=30)

        if response.status_code != 200:
            return {'success': False, 'data': {}, 'error': f'Shopify API returned {response.status_code}'}

        data = response.json()
        products = data.get('products', [])

        if not products:
            return {'success': False, 'data': {}, 'error': 'No products in Shopify API response'}

        # Extract prices from variants
        prices = []
        sample_products = []

        for product in products:
            # Skip inactive/unpublished products
            if product.get('status') and product['status'] != 'active':
                continue
            if product.get('published_at') is None:
                continue

            title = product.get('title', 'Unknown')
            variants = product.get('variants', [])

            if variants:
                # Use first available (non-draft) variant price
                price_str = variants[0].get('price', '0')
                try:
                    price = float(price_str)
                    if price > 0:
                        prices.append(price)
                        sample_products.append({'name': title, 'price': price})
                except (ValueError, TypeError):
                    pass

        if not prices:
            return {'success': False, 'data': {}, 'error': 'No valid prices found'}

        # Detect currency from price magnitude (COP prices are typically > 10000)
        avg_price = statistics.mean(prices)
        if avg_price > 10000:
            currency = 'COP'
        elif parsed.netloc.endswith('.mx'):
            currency = 'MXN'
        else:
            currency = 'USD'

        return {
            'success': True,
            'data': {
                'product_count': len(products),
                'avg_price': round(avg_price, 2),
                'price_range': {
                    'min': round(min(prices), 2),
                    'max': round(max(prices), 2)
                },
                'currency': currency,
                'sample_products': sample_products[:10],
                'products_on_page': len(products),
                'source': 'shopify_api'
            },
            'error': None
        }

    except requests.exceptions.RequestException as e:
        return {'success': False, 'data': {}, 'error': f'Shopify API request failed: {str(e)}'}
    except Exception as e:
        return {'success': False, 'data': {}, 'error': f'Shopify API error: {str(e)}'}


def scrape_woocommerce_api(base_url: str) -> Dict[str, Any]:
    """
    Scrape products from WooCommerce's public Store API.

    Uses /wp-json/wc/store/v1/products (no auth required).

    Args:
        base_url: Base URL of the WooCommerce store

    Returns:
        Dict with success, data, error
    """
    import requests

    parsed = urlparse(base_url)
    store_base = f"{parsed.scheme}://{parsed.netloc}"
    api_url = f"{store_base}/wp-json/wc/store/v1/products"

    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json',
            'Accept-Language': 'es-CO,es;q=0.9,en-US;q=0.8,en;q=0.7',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin',
        }

        # First visit homepage to get cookies (some WAFs require this)
        session = requests.Session()
        try:
            homepage_headers = {**headers, 'Accept': 'text/html', 'Sec-Fetch-Dest': 'document', 'Sec-Fetch-Mode': 'navigate', 'Sec-Fetch-Site': 'none', 'Sec-Fetch-User': '?1'}
            session.get(store_base, headers=homepage_headers, timeout=10)
        except Exception:
            pass

        resp = session.get(
            api_url,
            params={'per_page': 100},
            headers=headers,
            timeout=20,
        )

        if resp.status_code != 200:
            return {'success': False, 'data': {}, 'error': f'WooCommerce API returned {resp.status_code}'}

        products = resp.json()
        if not isinstance(products, list) or not products:
            return {'success': False, 'data': {}, 'error': 'No products in WooCommerce API response'}

        # Get total from pagination header
        total_products = int(resp.headers.get('X-WP-Total', resp.headers.get('x-wp-total', len(products))))

        # Extract prices
        prices = []
        sample_products = []
        currency = None

        for product in products:
            title = product.get('name', 'Unknown')
            price_info = product.get('prices', {})
            price_str = price_info.get('price', '0')

            if not currency:
                currency = price_info.get('currency_code', 'USD')

            try:
                # WooCommerce Store API returns prices in minor units (cents)
                raw_price = int(price_str)
                decimals = int(price_info.get('currency_minor_unit', 2))
                price = raw_price / (10 ** decimals)
                if price > 0:
                    prices.append(price)
                    sample_products.append({'name': title, 'price': price})
                else:
                    sample_products.append({'name': title})
            except (ValueError, TypeError):
                sample_products.append({'name': title})

        if not prices:
            return {
                'success': True,
                'data': {
                    'product_count': total_products,
                    'avg_price': None,
                    'price_range': {'min': None, 'max': None},
                    'currency': currency or 'USD',
                    'sample_products': sample_products[:10],
                    'products_on_page': len(products),
                    'source': 'woocommerce_api',
                },
                'error': None,
            }

        avg_price = statistics.mean(prices)

        return {
            'success': True,
            'data': {
                'product_count': total_products,
                'avg_price': round(avg_price, 2),
                'price_range': {
                    'min': round(min(prices), 2),
                    'max': round(max(prices), 2),
                },
                'currency': currency or 'USD',
                'sample_products': sample_products[:10],
                'products_on_page': len(products),
                'source': 'woocommerce_api',
            },
            'error': None,
        }

    except requests.exceptions.RequestException as e:
        return {'success': False, 'data': {}, 'error': f'WooCommerce API request failed: {str(e)}'}
    except Exception as e:
        return {'success': False, 'data': {}, 'error': f'WooCommerce API error: {str(e)}'}


def scrape_product_catalog(url: str, platform: Optional[str] = None) -> Dict[str, Any]:
    """
    Scrape product catalog to get size, pricing, and statistics.

    Args:
        url: E-commerce website URL
        platform: Platform type (Shopify, VTEX, etc.) - optional

    Returns:
        Dict with:
            - success: bool
            - data: dict with 'product_count', 'avg_price', 'price_range', 'currency'
            - error: str or None
    """
    try:
        # If platform is known, try its API first
        if platform and platform.upper() == 'VTEX':
            vtex_result = scrape_vtex_api(url)
            if vtex_result['success']:
                return vtex_result

        if platform and platform.upper() == 'WOOCOMMERCE':
            woo_result = scrape_woocommerce_api(url)
            if woo_result['success']:
                return woo_result

        # Try Shopify API (works even with anti-bot protection)
        shopify_result = scrape_shopify_api(url)
        if shopify_result['success']:
            return shopify_result

        # Try WooCommerce Store API
        woo_result = scrape_woocommerce_api(url)
        if woo_result['success']:
            return woo_result

        # If platform unknown, also attempt VTEX opportunistically before HTML fallback
        if not (platform and platform.upper() == 'VTEX'):
            vtex_result = scrape_vtex_api(url)
            if vtex_result['success']:
                return vtex_result

        # Fall back to HTML scraping
        listing_url = url

        # Check if URL is already a product listing page
        if not any(pattern in url.lower() for pattern in PRODUCT_LISTING_PATTERNS):
            # Try to find product listing page
            scrape_result = scrape_website(url)
            if scrape_result['success']:
                soup = scrape_result['data']['soup']

                # Look for links to product pages
                for pattern in PRODUCT_LISTING_PATTERNS:
                    link = soup.find('a', href=re.compile(pattern, re.I))
                    if link:
                        listing_url = urljoin(url, link.get('href'))
                        break

        # Scrape the product listing page
        scrape_result = scrape_website(listing_url)

        if not scrape_result['success']:
            return {
                'success': False,
                'data': {},
                'error': f"Failed to scrape product listing: {scrape_result['error']}"
            }

        html_content = scrape_result['data']['html']
        soup = scrape_result['data']['soup']

        # Detect currency
        currency = detect_currency(html_content, url)

        # Extract products
        products = scrape_product_page(listing_url, soup)

        if not products:
            return {
                'success': False,
                'data': {},
                'error': 'No products found on page'
            }

        # Extract prices
        prices = [p['price'] for p in products if 'price' in p and p['price'] is not None]

        if not prices:
            return {
                'success': False,
                'data': {},
                'error': 'No prices found'
            }

        # Calculate statistics
        avg_price = statistics.mean(prices)
        min_price = min(prices)
        max_price = max(prices)

        # Estimate total products
        total_products = estimate_total_products(soup, len(products))

        if total_products is None:
            # Use number of products found as estimate
            total_products = len(products)

        return {
            'success': True,
            'data': {
                'product_count': total_products,
                'avg_price': round(avg_price, 2),
                'price_range': {
                    'min': round(min_price, 2),
                    'max': round(max_price, 2)
                },
                'currency': currency,
                'sample_products': products[:10],  # First 10 products
                'products_on_page': len(products)
            },
            'error': None
        }

    except Exception as e:
        return {
            'success': False,
            'data': {},
            'error': f'Product catalog scraping error: {str(e)}'
        }


if __name__ == '__main__':
    # Test cases
    import sys

    if len(sys.argv) > 1:
        test_urls = [sys.argv[1]]
    else:
        test_urls = [
            'https://www.allbirds.com/collections/all',  # Shopify
        ]

    print("Product Catalog Scraper Test")
    print("=" * 60)

    for test_url in test_urls:
        print(f"\nTesting: {test_url}")
        print("-" * 60)

        result = scrape_product_catalog(test_url)

        if result['success']:
            data = result['data']
            print(f"✓ Product Count: {data['product_count']:,}")
            print(f"  Average Price: {data['currency']} {data['avg_price']:.2f}")
            print(f"  Price Range: {data['currency']} {data['price_range']['min']:.2f} - {data['currency']} {data['price_range']['max']:.2f}")
            print(f"  Products on page: {data['products_on_page']}")

            if data['sample_products']:
                print(f"\n  Sample Products:")
                for i, product in enumerate(data['sample_products'][:5], 1):
                    name = product.get('name', 'Unknown')
                    price = product.get('price', 0)
                    print(f"    {i}. {name}: {data['currency']} {price:.2f}")
        else:
            print(f"✗ Error: {result['error']}")

    print("\n" + "=" * 60)
