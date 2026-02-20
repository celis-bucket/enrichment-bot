"""
Web Scraper Tool

Purpose: Generic website scraper with retry logic and rate limiting
Inputs: URL, headers (optional), timeout
Outputs: HTML content, status code, metadata
Dependencies: requests, urllib3, beautifulsoup4, time

Features:
- Exponential backoff retry (429, 500-504)
- User-agent rotation
- Respect Retry-After headers
- Configurable timeout
- Session management for cookies
"""

import time
import random
from typing import Dict, Any, Optional
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup


# List of user agents to rotate
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:121.0) Gecko/20100101 Firefox/121.0',
]


def create_session(max_retries: int = 3) -> requests.Session:
    """
    Create a requests session with retry logic.

    Args:
        max_retries: Maximum number of retry attempts

    Returns:
        Configured requests.Session object
    """
    session = requests.Session()

    # Configure retry strategy
    retry_strategy = Retry(
        total=max_retries,
        backoff_factor=2,  # Exponential backoff: 1s, 2s, 4s, 8s...
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "POST", "HEAD"],
        raise_on_status=False
    )

    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)

    return session


def scrape_website(
    url: str,
    headers: Optional[Dict[str, str]] = None,
    timeout: int = 30,
    follow_redirects: bool = True,
    parse_html: bool = True
) -> Dict[str, Any]:
    """
    Scrape a website and return HTML content with metadata.

    Args:
        url: URL to scrape
        headers: Optional custom headers dict
        timeout: Request timeout in seconds (default: 30)
        follow_redirects: Whether to follow redirects (default: True)
        parse_html: Whether to parse HTML with BeautifulSoup (default: True)

    Returns:
        Dict with:
            - success: bool
            - data: dict with 'html', 'text', 'soup' (if parsed), 'status_code', 'headers', 'url' (final)
            - error: str or None
    """
    session = None
    try:
        # Create session with retry logic
        session = create_session(max_retries=3)

        # Set headers
        if headers is None:
            headers = {}

        # Add user-agent if not provided
        if 'User-Agent' not in headers:
            headers['User-Agent'] = random.choice(USER_AGENTS)

        # Add accept headers
        # Note: Avoid Accept-Encoding with br (brotli) as some sites return obfuscated content
        headers.setdefault('Accept', 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8')
        headers.setdefault('Accept-Language', 'en-US,en;q=0.9,es;q=0.8')
        headers.setdefault('Connection', 'keep-alive')

        # Make request
        response = session.get(
            url,
            headers=headers,
            timeout=timeout,
            allow_redirects=follow_redirects
        )

        # Check for rate limiting with Retry-After header
        if response.status_code == 429:
            retry_after = response.headers.get('Retry-After')
            if retry_after:
                try:
                    wait_time = int(retry_after)
                    if wait_time > 0 and wait_time < 300:  # Max 5 minutes
                        time.sleep(wait_time)
                        # Retry once after waiting
                        response = session.get(
                            url,
                            headers=headers,
                            timeout=timeout,
                            allow_redirects=follow_redirects
                        )
                except ValueError:
                    pass

        # Check if request was successful
        if response.status_code >= 400:
            return {
                'success': False,
                'data': {
                    'status_code': response.status_code,
                    'url': response.url,
                    'headers': dict(response.headers)
                },
                'error': f'HTTP {response.status_code}: {response.reason}'
            }

        # Get content
        html_content = response.text

        # Parse HTML if requested
        soup = None
        if parse_html:
            try:
                soup = BeautifulSoup(html_content, 'lxml')
            except Exception as e:
                # Fall back to html.parser if lxml fails
                try:
                    soup = BeautifulSoup(html_content, 'html.parser')
                except Exception as parse_error:
                    print(f"Warning: HTML parser fallback also failed: {parse_error}")

        return {
            'success': True,
            'data': {
                'html': html_content,
                'text': soup.get_text(strip=True) if soup else response.text,
                'soup': soup,
                'status_code': response.status_code,
                'headers': dict(response.headers),
                'url': response.url,  # Final URL after redirects
                'encoding': response.encoding,
                'size': len(html_content)
            },
            'error': None
        }

    except requests.exceptions.Timeout:
        return {
            'success': False,
            'data': {},
            'error': f'Request timeout after {timeout} seconds'
        }

    except requests.exceptions.ConnectionError as e:
        return {
            'success': False,
            'data': {},
            'error': f'Connection error: {str(e)}'
        }

    except requests.exceptions.TooManyRedirects:
        return {
            'success': False,
            'data': {},
            'error': 'Too many redirects'
        }

    except Exception as e:
        return {
            'success': False,
            'data': {},
            'error': f'Scraping error: {str(e)}'
        }

    finally:
        if session:
            session.close()


def scrape_multiple_pages(
    urls: list[str],
    delay: float = 1.0,
    **kwargs
) -> Dict[str, Any]:
    """
    Scrape multiple URLs with rate limiting.

    Args:
        urls: List of URLs to scrape
        delay: Delay between requests in seconds (default: 1.0)
        **kwargs: Additional arguments to pass to scrape_website()

    Returns:
        Dict with:
            - success: bool
            - data: list of scrape results
            - error: str or None
    """
    results = []
    errors = []

    for i, url in enumerate(urls):
        # Add delay between requests (except for first request)
        if i > 0:
            time.sleep(delay)

        result = scrape_website(url, **kwargs)
        results.append({
            'url': url,
            'result': result
        })

        if not result['success']:
            errors.append(f"{url}: {result['error']}")

    return {
        'success': len(errors) == 0,
        'data': results,
        'error': '; '.join(errors) if errors else None,
        'stats': {
            'total': len(urls),
            'successful': len(urls) - len(errors),
            'failed': len(errors)
        }
    }


if __name__ == '__main__':
    # Test cases
    test_urls = [
        'https://www.example.com',
        'https://httpbin.org/html',
    ]

    print("Web Scraper Test Cases:")
    print("=" * 60)

    for test_url in test_urls:
        print(f"\nScraping: {test_url}")
        result = scrape_website(test_url)

        print(f"Success: {result['success']}")
        if result['success']:
            data = result['data']
            print(f"Status: {data['status_code']}")
            print(f"Final URL: {data['url']}")
            print(f"Content size: {data['size']} bytes")
            print(f"Encoding: {data['encoding']}")
            if data['soup']:
                print(f"Title: {data['soup'].title.string if data['soup'].title else 'No title'}")
        else:
            print(f"Error: {result['error']}")
