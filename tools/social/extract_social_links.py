"""
Social Media Link Extraction Tool

Purpose: Extract social media profile URLs from a website
Inputs: URL, HTML content (optional)
Outputs: Dictionary of social media platform URLs
Dependencies: requests, beautifulsoup4, re

Supported Platforms:
- Instagram
- Facebook
- TikTok
- YouTube
- LinkedIn
- Twitter/X
- Pinterest
- WhatsApp
"""

import re
from collections import Counter
from typing import Dict, Any, Optional
from bs4 import BeautifulSoup
from urllib.parse import urlparse

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from core.web_scraper import scrape_website


# Social media platform patterns
SOCIAL_PLATFORMS = {
    'instagram': {
        'domains': ['instagram.com', 'instagr.am'],
        'pattern': r'(?:https?://)?(?:www\.)?(?:instagram\.com|instagr\.am)/([a-zA-Z0-9._]+)',
        'validate': lambda username: username not in ['p', 'tv', 'reel', 'explore', 'accounts', 'direct'],
    },
    'facebook': {
        'domains': ['facebook.com', 'fb.com', 'fb.me'],
        'pattern': r'(?:https?://)?(?:www\.)?(?:facebook\.com|fb\.com)/([a-zA-Z0-9.]+)',
        'validate': lambda username: username not in ['sharer', 'share', 'login', 'groups', 'events'],
    },
    'tiktok': {
        'domains': ['tiktok.com'],
        'pattern': r'(?:https?://)?(?:www\.)?tiktok\.com/@([a-zA-Z0-9._]+)',
        'validate': lambda username: True,
    },
    'youtube': {
        'domains': ['youtube.com', 'youtu.be'],
        'pattern': r'(?:https?://)?(?:www\.)?youtube\.com/(?:c/|channel/|user/|@)?([a-zA-Z0-9_.-]+)',
        'validate': lambda username: username not in ['watch', 'playlist', 'feed', 'shorts'],
    },
    'linkedin': {
        'domains': ['linkedin.com'],
        'pattern': r'(?:https?://)?(?:www\.)?linkedin\.com/(?:company|in)/([a-zA-Z0-9-]+)',
        'validate': lambda username: True,
    },
    'twitter': {
        'domains': ['twitter.com', 'x.com'],
        'pattern': r'(?:https?://)?(?:www\.)?(?:twitter\.com|x\.com)/([a-zA-Z0-9_]+)',
        'validate': lambda username: username not in ['share', 'intent', 'i', 'home', 'explore'],
    },
    'pinterest': {
        'domains': ['pinterest.com', 'pin.it'],
        'pattern': r'(?:https?://)?(?:www\.)?pinterest\.com/([a-zA-Z0-9_]+)',
        'validate': lambda username: username not in ['pin', 'search'],
    },
    'whatsapp': {
        'domains': ['wa.me', 'api.whatsapp.com'],
        'pattern': r'(?:https?://)?(?:wa\.me|api\.whatsapp\.com/send\?phone=)(\d+)',
        'validate': lambda username: True,
    },
}


def extract_social_links_from_raw_html(html_content: str) -> Dict[str, str]:
    """
    Extract social media links directly from raw HTML using regex.
    This works even with obfuscated/minified HTML where BeautifulSoup fails.

    Args:
        html_content: Raw HTML string

    Returns:
        Dict mapping platform names to URLs
    """
    found_links = {}

    # Decode Unicode escapes (e.g. VTEX stores use \u002F for /)
    html_content = html_content.replace('\\u002F', '/').replace('\\u003A', ':')

    # Direct regex patterns for each platform
    raw_patterns = {
        'instagram': (r'instagram\.com/([a-zA-Z0-9_.]+)', 'https://instagram.com/{}'),
        'facebook': (r'facebook\.com/([a-zA-Z0-9_.]+)', 'https://facebook.com/{}'),
        'tiktok': (r'tiktok\.com/@?([a-zA-Z0-9_.]+)', 'https://tiktok.com/@{}'),
        'youtube': (r'youtube\.com/(?:c/|channel/|user/|@)?([a-zA-Z0-9_.-]+)', 'https://youtube.com/@{}'),
        'twitter': (r'(?:twitter|x)\.com/([a-zA-Z0-9_]+)', 'https://twitter.com/{}'),
        'linkedin': (r'linkedin\.com/(?:company|in)/([a-zA-Z0-9-]+)', 'https://linkedin.com/company/{}'),
        'pinterest': (r'pinterest\.com/([a-zA-Z0-9_]+)', 'https://pinterest.com/{}'),
        'whatsapp': (r'wa\.me/(\d+)', 'https://wa.me/{}'),
    }

    # Exclusion lists for invalid usernames
    exclusions = {
        'instagram': {'p', 'tv', 'reel', 'explore', 'accounts', 'direct', 'stories'},
        'facebook': {'sharer', 'share', 'login', 'groups', 'events', 'pages', 'watch'},
        'tiktok': {'i18n', 'embed', 'business', 'ads', 'developers', 'tag', 'discover'},
        'youtube': {'watch', 'playlist', 'feed', 'shorts', 'results', 'channel'},
        'twitter': {'share', 'intent', 'i', 'home', 'explore', 'search', 'hashtag'},
        'pinterest': {'pin', 'search'},
    }

    for platform, (pattern, url_template) in raw_patterns.items():
        matches = re.findall(pattern, html_content, re.IGNORECASE)
        if matches:
            # Count frequency to identify primary account
            match_counts = Counter(m.lower() for m in matches)

            # Build ordered unique list (first appearance order)
            seen = set()
            ordered_unique = []
            for m in matches:
                key = m.lower()
                if key not in seen:
                    seen.add(key)
                    ordered_unique.append(m)

            # Filter invalid matches
            valid_matches = [
                m for m in ordered_unique
                if m.lower() not in exclusions.get(platform, set())
                and len(m) > 1
                and not m.isdigit()
            ]

            # For whatsapp, we want numeric
            if platform == 'whatsapp':
                valid_matches = [m for m in ordered_unique if m.isdigit() and len(m) >= 10]

            if valid_matches:
                # Pick most frequently mentioned account (primary), first-appearance breaks ties
                valid_matches.sort(key=lambda m: -match_counts[m.lower()])
                found_links[platform] = url_template.format(valid_matches[0])

    return found_links


def extract_social_links_from_html(
    html_content: str,
    url: str
) -> Dict[str, Any]:
    """
    Extract social media links from HTML content.

    Args:
        html_content: HTML content of the page
        url: Original URL

    Returns:
        Dict with:
            - success: bool
            - data: dict mapping platform names to URLs
            - error: str or None
    """
    try:
        # First try raw HTML regex (works with obfuscated HTML)
        found_links = extract_social_links_from_raw_html(html_content)

        # If we found links via regex, return them
        if found_links:
            return {
                'success': True,
                'data': found_links,
                'error': None
            }

        # Fall back to BeautifulSoup parsing for standard HTML
        soup = BeautifulSoup(html_content, 'lxml')

        # 1. Find all links in the page
        all_links = soup.find_all('a', href=True)

        for link in all_links:
            href = link.get('href', '')

            # Check each social platform
            for platform, config in SOCIAL_PLATFORMS.items():
                # Skip if we already found this platform
                if platform in found_links:
                    continue

                # Check if domain matches
                domain_match = any(domain in href.lower() for domain in config['domains'])

                if domain_match:
                    # Extract username using pattern
                    match = re.search(config['pattern'], href, re.IGNORECASE)
                    if match:
                        username = match.group(1)

                        # Validate username
                        if config['validate'](username):
                            # Normalize URL
                            if platform == 'instagram':
                                normalized_url = f"https://instagram.com/{username}"
                            elif platform == 'facebook':
                                normalized_url = f"https://facebook.com/{username}"
                            elif platform == 'tiktok':
                                normalized_url = f"https://tiktok.com/@{username}"
                            elif platform == 'youtube':
                                normalized_url = f"https://youtube.com/@{username}"
                            elif platform == 'linkedin':
                                if '/company/' in href:
                                    normalized_url = f"https://linkedin.com/company/{username}"
                                else:
                                    normalized_url = f"https://linkedin.com/in/{username}"
                            elif platform == 'twitter':
                                normalized_url = f"https://twitter.com/{username}"
                            elif platform == 'pinterest':
                                normalized_url = f"https://pinterest.com/{username}"
                            elif platform == 'whatsapp':
                                normalized_url = f"https://wa.me/{username}"
                            else:
                                normalized_url = href

                            found_links[platform] = normalized_url

        # 2. Check for common locations (footer, header)
        # Focus on footer and header for social links
        footer = soup.find('footer')
        header = soup.find('header')

        for section in [footer, header]:
            if section and len(found_links) < len(SOCIAL_PLATFORMS):
                section_links = section.find_all('a', href=True)
                for link in section_links:
                    href = link.get('href', '')
                    for platform, config in SOCIAL_PLATFORMS.items():
                        if platform not in found_links:
                            if any(domain in href.lower() for domain in config['domains']):
                                match = re.search(config['pattern'], href, re.IGNORECASE)
                                if match:
                                    username = match.group(1)
                                    if config['validate'](username):
                                        if platform == 'instagram':
                                            found_links[platform] = f"https://instagram.com/{username}"
                                        elif platform == 'facebook':
                                            found_links[platform] = f"https://facebook.com/{username}"
                                        elif platform == 'tiktok':
                                            found_links[platform] = f"https://tiktok.com/@{username}"
                                        elif platform == 'youtube':
                                            found_links[platform] = f"https://youtube.com/@{username}"
                                        elif platform == 'linkedin':
                                            if '/company/' in href:
                                                found_links[platform] = f"https://linkedin.com/company/{username}"
                                            else:
                                                found_links[platform] = f"https://linkedin.com/in/{username}"
                                        elif platform == 'twitter':
                                            found_links[platform] = f"https://twitter.com/{username}"
                                        elif platform == 'pinterest':
                                            found_links[platform] = f"https://pinterest.com/{username}"
                                        elif platform == 'whatsapp':
                                            found_links[platform] = f"https://wa.me/{username}"

        return {
            'success': True,
            'data': found_links,
            'error': None
        }

    except Exception as e:
        return {
            'success': False,
            'data': {},
            'error': f'Social link extraction error: {str(e)}'
        }


def search_instagram_via_serper(brand_name: str, domain: Optional[str] = None) -> Optional[str]:
    """
    Search for a brand's Instagram URL using Serper (Google Search).
    Fallback when HTML extraction doesn't find an Instagram link.

    Uses domain-based search when available (more precise), falls back to
    brand name search otherwise.

    Args:
        brand_name: The brand/company name to search for
        domain: Optional domain (e.g. 'armatura.com.co') for more precise search

    Returns:
        Instagram URL string or None if not found
    """
    try:
        from core.google_search import google_search
    except ImportError:
        try:
            sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
            from core.google_search import google_search
        except ImportError:
            return None

    # Domain-based query is more precise; fall back to brand name
    if domain:
        query = f'{domain} instagram'
    else:
        query = f'{brand_name} instagram'

    result = google_search(query, num_results=5)
    if not result.get('success'):
        return None

    organic = result.get('data', {}).get('organic', [])
    for item in organic:
        link = item.get('link', '')
        # Match instagram.com profile URLs, skip /p/ /reel/ /explore/ etc.
        match = re.match(
            r'https?://(?:www\.)?instagram\.com/([a-zA-Z0-9_.]+)/?$',
            link
        )
        if match:
            username = match.group(1)
            if username.lower() not in {'p', 'tv', 'reel', 'explore', 'accounts', 'direct', 'stories'}:
                return f'https://instagram.com/{username}'

    return None


def extract_social_links(url: str) -> Dict[str, Any]:
    """
    Extract social media links from a URL.

    Args:
        url: Website URL

    Returns:
        Dict with:
            - success: bool
            - data: dict mapping platform names to URLs
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

    # Extract social links
    return extract_social_links_from_html(html_content, url)


if __name__ == '__main__':
    # Test cases
    import sys

    if len(sys.argv) > 1:
        test_urls = [sys.argv[1]]
    else:
        test_urls = [
            'https://www.allbirds.com',  # Has social links
        ]

    print("Social Media Link Extraction Test")
    print("=" * 60)

    for test_url in test_urls:
        print(f"\nTesting: {test_url}")
        print("-" * 60)

        result = extract_social_links(test_url)

        if result['success']:
            data = result['data']
            if data:
                print(f"✓ Found {len(data)} social media links:")
                for platform, link in data.items():
                    print(f"  {platform.capitalize()}: {link}")
            else:
                print("  No social media links found")
        else:
            print(f"✗ Error: {result['error']}")

    print("\n" + "=" * 60)
