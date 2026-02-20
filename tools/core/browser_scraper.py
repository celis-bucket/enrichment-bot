"""
Browser Scraper Tool (Playwright)

Purpose: Headless browser scraper for JS-rendered pages and light interaction
Inputs: URL, optional interaction actions
Outputs: Rendered HTML content, metadata (same format as web_scraper)
Dependencies: playwright, beautifulsoup4

Setup: pip install playwright && playwright install chromium
"""

import os
import sys
import time
import random
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv

load_dotenv()

# Configuration
HEADLESS = os.getenv('PLAYWRIGHT_HEADLESS', 'true').lower() == 'true'
DEFAULT_TIMEOUT = 30000  # 30 seconds in milliseconds
NAVIGATION_TIMEOUT = 60000  # 60 seconds

# Reuse user-agent list from web_scraper
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:121.0) Gecko/20100101 Firefox/121.0',
]


def _is_playwright_available() -> bool:
    """Check if playwright and chromium are installed."""
    try:
        from playwright.sync_api import sync_playwright
        # Quick check — don't actually launch browser
        return True
    except ImportError:
        return False


def browser_scrape(
    url: str,
    wait_for: str = 'networkidle',
    timeout: int = DEFAULT_TIMEOUT,
    parse_html: bool = True,
    screenshot: bool = False
) -> Dict[str, Any]:
    """
    Scrape a page using headless Chromium with full JS rendering.

    Return format matches web_scraper.scrape_website() exactly.

    Args:
        url: URL to scrape
        wait_for: Wait strategy - 'networkidle', 'load', 'domcontentloaded', or CSS selector
        timeout: Page load timeout in milliseconds
        parse_html: Whether to parse HTML with BeautifulSoup
        screenshot: Whether to save a screenshot to .tmp/screenshots/

    Returns:
        Dict with:
            - success: bool
            - data: dict with 'html', 'text', 'soup', 'status_code', 'headers', 'url', 'encoding', 'size'
            - error: str or None
    """
    if not _is_playwright_available():
        return {
            'success': False,
            'data': {},
            'error': 'Playwright not installed. Run: pip install playwright && playwright install chromium'
        }

    browser = None
    try:
        from playwright.sync_api import sync_playwright

        pw = sync_playwright().start()
        browser = pw.chromium.launch(headless=HEADLESS)
        context = browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent=random.choice(USER_AGENTS),
            locale='en-US',
            timezone_id='America/New_York'
        )
        context.set_default_timeout(timeout)
        context.set_default_navigation_timeout(NAVIGATION_TIMEOUT)

        page = context.new_page()

        # Capture response status and headers
        response_status = None
        response_headers = {}

        def handle_response(response):
            nonlocal response_status, response_headers
            if response.url == page.url or response.url == url:
                response_status = response.status
                response_headers = dict(response.headers)

        page.on('response', handle_response)

        # Navigate to URL
        response = page.goto(url, wait_until='domcontentloaded')

        if response:
            response_status = response.status
            response_headers = dict(response.headers)

        # Wait for page to be ready
        if wait_for in ('networkidle', 'load', 'domcontentloaded'):
            try:
                page.wait_for_load_state(wait_for, timeout=timeout)
            except Exception:
                # Continue with what we have if wait times out
                pass
        else:
            # Treat as CSS selector
            try:
                page.wait_for_selector(wait_for, timeout=timeout)
            except Exception:
                pass

        # Check for anti-bot protection
        if response_status == 403:
            return {
                'success': False,
                'data': {
                    'status_code': 403,
                    'url': page.url,
                    'headers': response_headers
                },
                'error': 'Anti-bot protection detected (HTTP 403). Browser scraping blocked.'
            }

        if response_status and response_status >= 400:
            return {
                'success': False,
                'data': {
                    'status_code': response_status,
                    'url': page.url,
                    'headers': response_headers
                },
                'error': f'HTTP {response_status}'
            }

        # Get rendered HTML
        html_content = page.content()
        text_content = page.inner_text('body') if page.query_selector('body') else ''

        # Parse HTML if requested
        soup = None
        if parse_html:
            try:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(html_content, 'lxml')
            except Exception:
                try:
                    from bs4 import BeautifulSoup
                    soup = BeautifulSoup(html_content, 'html.parser')
                except Exception:
                    pass

        # Take screenshot if requested
        if screenshot:
            screenshot_dir = os.path.join(os.path.dirname(__file__), '..', '..', '.tmp', 'screenshots')
            os.makedirs(screenshot_dir, exist_ok=True)
            from urllib.parse import urlparse
            domain = urlparse(url).netloc.replace('www.', '')
            timestamp = int(time.time())
            screenshot_path = os.path.join(screenshot_dir, f"{domain}_{timestamp}.png")
            page.screenshot(path=screenshot_path, full_page=False)

        final_url = page.url

        context.close()
        browser.close()
        pw.stop()
        browser = None

        return {
            'success': True,
            'data': {
                'html': html_content,
                'text': text_content,
                'soup': soup,
                'status_code': response_status or 200,
                'headers': response_headers,
                'url': final_url,
                'encoding': 'utf-8',
                'size': len(html_content)
            },
            'error': None
        }

    except Exception as e:
        error_msg = str(e)
        if 'net::ERR_NAME_NOT_RESOLVED' in error_msg:
            error_msg = f'DNS resolution failed for URL: {url}'
        elif 'net::ERR_CONNECTION_REFUSED' in error_msg:
            error_msg = f'Connection refused: {url}'
        elif 'Timeout' in error_msg or 'timeout' in error_msg:
            error_msg = f'Page load timeout after {timeout}ms: {url}'

        return {
            'success': False,
            'data': {},
            'error': f'Browser scraping error: {error_msg}'
        }
    finally:
        if browser:
            try:
                browser.close()
            except Exception:
                pass


def interact_with_page(
    url: str,
    actions: List[Dict[str, Any]],
    timeout: int = DEFAULT_TIMEOUT
) -> Dict[str, Any]:
    """
    Navigate to URL and perform a sequence of interactions.

    Args:
        url: URL to navigate to
        actions: List of action dicts, each with:
            - type: 'click', 'fill', 'select', 'wait', 'scroll'
            - selector: CSS selector (for click, fill, select)
            - value: value to fill/select (for fill, select)
            - timeout: optional per-action timeout in ms
        timeout: Overall page timeout in milliseconds

    Returns:
        Dict with:
            - success: bool
            - data: dict with final page state plus actions_completed, actions_log
            - error: str or None
    """
    if not _is_playwright_available():
        return {
            'success': False,
            'data': {},
            'error': 'Playwright not installed. Run: pip install playwright && playwright install chromium'
        }

    browser = None
    try:
        from playwright.sync_api import sync_playwright
        from bs4 import BeautifulSoup

        pw = sync_playwright().start()
        browser = pw.chromium.launch(headless=HEADLESS)
        context = browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent=random.choice(USER_AGENTS),
            locale='en-US'
        )
        context.set_default_timeout(timeout)
        context.set_default_navigation_timeout(NAVIGATION_TIMEOUT)

        page = context.new_page()

        # Navigate to URL
        page.goto(url, wait_until='domcontentloaded')
        try:
            page.wait_for_load_state('networkidle', timeout=min(timeout, 15000))
        except Exception:
            pass

        # Execute actions
        actions_completed = 0
        actions_log = []

        for i, action in enumerate(actions):
            action_type = action.get('type', '')
            selector = action.get('selector', '')
            value = action.get('value', '')
            action_timeout = action.get('timeout', 5000)

            try:
                if action_type == 'click':
                    # Try multiple selectors if comma-separated
                    selectors = [s.strip() for s in selector.split(',')]
                    clicked = False
                    for sel in selectors:
                        try:
                            page.wait_for_selector(sel, timeout=action_timeout)
                            page.click(sel)
                            clicked = True
                            actions_log.append(f"[{i}] click '{sel}': OK")
                            break
                        except Exception:
                            continue
                    if not clicked:
                        actions_log.append(f"[{i}] click '{selector}': selector not found")
                        continue

                elif action_type == 'fill':
                    page.wait_for_selector(selector, timeout=action_timeout)
                    page.fill(selector, value)
                    actions_log.append(f"[{i}] fill '{selector}': OK")

                elif action_type == 'select':
                    page.wait_for_selector(selector, timeout=action_timeout)
                    page.select_option(selector, value)
                    actions_log.append(f"[{i}] select '{selector}': OK")

                elif action_type == 'wait':
                    wait_time = action_timeout
                    if selector:
                        page.wait_for_selector(selector, timeout=wait_time)
                        actions_log.append(f"[{i}] wait for '{selector}': OK")
                    else:
                        page.wait_for_timeout(wait_time)
                        actions_log.append(f"[{i}] wait {wait_time}ms: OK")

                elif action_type == 'scroll':
                    page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
                    page.wait_for_timeout(1000)
                    actions_log.append(f"[{i}] scroll to bottom: OK")

                else:
                    actions_log.append(f"[{i}] unknown action type '{action_type}': skipped")
                    continue

                actions_completed += 1

            except Exception as e:
                actions_log.append(f"[{i}] {action_type} '{selector}': failed - {str(e)[:100]}")

        # Get final page state
        html_content = page.content()
        text_content = page.inner_text('body') if page.query_selector('body') else ''

        soup = None
        try:
            soup = BeautifulSoup(html_content, 'lxml')
        except Exception:
            try:
                soup = BeautifulSoup(html_content, 'html.parser')
            except Exception:
                pass

        final_url = page.url

        context.close()
        browser.close()
        pw.stop()
        browser = None

        return {
            'success': True,
            'data': {
                'html': html_content,
                'text': text_content,
                'soup': soup,
                'status_code': 200,
                'headers': {},
                'url': final_url,
                'encoding': 'utf-8',
                'size': len(html_content),
                'actions_completed': actions_completed,
                'actions_log': actions_log
            },
            'error': None
        }

    except Exception as e:
        return {
            'success': False,
            'data': {},
            'error': f'Page interaction error: {str(e)}'
        }
    finally:
        if browser:
            try:
                browser.close()
            except Exception:
                pass


if __name__ == '__main__':
    test_url = sys.argv[1] if len(sys.argv) > 1 else 'https://www.example.com'

    print("Browser Scraper (Playwright)")
    print("=" * 60)
    print(f"URL: {test_url}")
    print(f"Headless: {HEADLESS}")
    print(f"Playwright available: {_is_playwright_available()}")

    result = browser_scrape(test_url)
    print(f"\nSuccess: {result['success']}")

    if result['success']:
        data = result['data']
        print(f"  Status: {data['status_code']}")
        print(f"  Final URL: {data['url']}")
        print(f"  Content size: {data['size']} bytes")
        print(f"  Encoding: {data['encoding']}")
        if data['soup']:
            title = data['soup'].title.string if data['soup'].title else 'No title'
            print(f"  Title: {title}")
        print(f"  Text preview: {data['text'][:200]}...")
    else:
        print(f"  Error: {result['error']}")
