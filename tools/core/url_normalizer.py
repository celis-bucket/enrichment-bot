"""
URL Normalizer Tool

Purpose: Clean and validate e-commerce URLs
Inputs: Raw URL string
Outputs: Normalized URL or error
Dependencies: urllib, validators
"""

import re
from urllib.parse import urlparse, urlunparse
from typing import Dict, Any
import validators


def normalize_url(raw_url: str) -> Dict[str, Any]:
    """
    Normalize and validate a URL.

    Args:
        raw_url: Raw URL string from user input

    Returns:
        Dict with:
            - success: bool
            - data: dict with 'url' (normalized) and 'original'
            - error: str or None
    """
    try:
        # Strip whitespace
        url = raw_url.strip()

        # Add protocol if missing
        if not re.match(r'^https?://', url, re.IGNORECASE):
            url = 'https://' + url

        # Parse URL
        parsed = urlparse(url)

        # Validate domain exists
        if not parsed.netloc:
            return {
                'success': False,
                'data': {},
                'error': 'Invalid URL: No domain found'
            }

        # Keep www. prefix — many sites don't resolve correctly without it
        netloc = parsed.netloc

        # Rebuild URL with normalized components
        normalized = urlunparse((
            parsed.scheme,
            netloc,
            parsed.path.rstrip('/') or '/',  # Remove trailing slash except for root
            parsed.params,
            parsed.query,
            ''  # Remove fragment
        ))

        # Validate URL format
        if not validators.url(normalized):
            return {
                'success': False,
                'data': {},
                'error': f'Invalid URL format: {normalized}'
            }

        return {
            'success': True,
            'data': {
                'url': normalized,
                'original': raw_url,
                'domain': netloc,
                'scheme': parsed.scheme,
                'path': parsed.path or '/'
            },
            'error': None
        }

    except Exception as e:
        return {
            'success': False,
            'data': {},
            'error': f'URL normalization error: {str(e)}'
        }


def extract_domain(url: str) -> str:
    """
    Extract domain from URL.

    Args:
        url: URL string

    Returns:
        Domain string (without www.)
    """
    try:
        parsed = urlparse(url)
        domain = parsed.netloc
        if domain.startswith('www.'):
            domain = domain[4:]
        return domain
    except:
        return ''


if __name__ == '__main__':
    # Test cases
    test_urls = [
        'https://www.example.com/products',
        'example.com',
        'http://shop.example.com/category/items/',
        'www.store.com',
        'invalid-url',
        '',
    ]

    print("URL Normalizer Test Cases:")
    print("=" * 60)

    for test_url in test_urls:
        result = normalize_url(test_url)
        print(f"\nInput: {test_url!r}")
        print(f"Success: {result['success']}")
        if result['success']:
            print(f"Normalized: {result['data']['url']}")
            print(f"Domain: {result['data']['domain']}")
        else:
            print(f"Error: {result['error']}")
