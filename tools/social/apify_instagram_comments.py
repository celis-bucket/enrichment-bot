"""
Apify Instagram Comment Scraper Integration

Purpose: Scrape comments from Instagram posts using Apify's instagram-comments-scraper
Inputs: List of Instagram post URLs (or shortcodes)
Outputs: List of comment objects (id, text, ownerUsername, timestamp, likesCount, postUrl)
Dependencies: requests, os, time, re

API Actor: apidojo/instagram-comments-scraper
Sync Endpoint: https://api.apify.com/v2/acts/apidojo~instagram-comments-scraper/run-sync-get-dataset-items
Input: {"postIds": ["SHORTCODE1", ...], "maxItems": N}
Output per comment: {id, message, user: {username}, createdAt, likeCount, replyCount, postId}

Why apidojo instead of official apify/instagram-comment-scraper:
  - 10s for 200 comments vs 20+ minutes (official never completed in testing)
  - $0.50/1K results vs $2.30/1K (4.6x cheaper)
  - Reliable sync endpoint (official kept timing out)
"""

import os
import re
import time
from typing import Dict, Any, List
from datetime import datetime
import requests
from dotenv import load_dotenv

load_dotenv()

SYNC_ENDPOINT = "https://api.apify.com/v2/acts/apidojo~instagram-comments-scraper/run-sync-get-dataset-items"
ASYNC_ENDPOINT = "https://api.apify.com/v2/acts/apidojo~instagram-comments-scraper/runs"
SYNC_TIMEOUT = 120
MAX_POLL_SECONDS = 300
POLL_INTERVAL_SECONDS = 5


def _extract_shortcode(post_url: str) -> str:
    """Extract shortcode from Instagram post URL."""
    match = re.search(r'instagram\.com/(?:p|reel)/([^/?]+)', post_url)
    if match:
        return match.group(1).rstrip('/')
    # Maybe it's already a shortcode
    return post_url.strip('/')


def get_comments_for_posts(
    post_urls: List[str],
    results_limit_per_post: int = 50,
) -> Dict[str, Any]:
    """
    Scrape comments from multiple Instagram posts via Apify.

    Sends all post shortcodes in a single Apify call. Tries the sync endpoint
    first; falls back to async (start run -> poll -> get dataset) if sync fails.

    Args:
        post_urls: List of Instagram post URLs
                   (e.g., ["https://www.instagram.com/p/ABC123/"])
        results_limit_per_post: Max comments per post (default: 50).
                                Total maxItems = len(post_urls) * results_limit_per_post

    Returns:
        Dict with:
            - success: bool
            - data: {comments: list, posts_scraped: int, total_comments: int}
            - error: str or None
    """
    if not post_urls:
        return {
            'success': True,
            'data': {'comments': [], 'posts_scraped': 0, 'total_comments': 0},
            'error': None
        }

    api_token = os.getenv('APIFY_API_TOKEN')
    if not api_token:
        return {
            'success': False,
            'data': {},
            'error': 'APIFY_API_TOKEN not found in environment variables'
        }

    # Extract shortcodes from URLs
    shortcodes = [_extract_shortcode(u) for u in post_urls]
    # Build shortcode -> original URL mapping for output
    shortcode_to_url = {}
    for url, sc in zip(post_urls, shortcodes):
        shortcode_to_url[sc] = url

    max_items = len(post_urls) * results_limit_per_post

    payload = {
        "postIds": shortcodes,
        "maxItems": max_items,
    }

    headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    }

    # Try sync endpoint first
    comments = _try_sync(api_token, payload, headers)
    if comments is not None:
        return _build_result(comments, post_urls, shortcode_to_url)

    # Fallback to async
    comments = _try_async(api_token, payload, headers)
    if comments is not None:
        return _build_result(comments, post_urls, shortcode_to_url)

    return {
        'success': False,
        'data': {},
        'error': 'Apify comment scraper failed on both sync and async attempts'
    }


def _try_sync(api_token: str, payload: dict, headers: dict):
    """Attempt sync endpoint. Returns comment list or None on failure."""
    url = f"{SYNC_ENDPOINT}?token={api_token}"
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=SYNC_TIMEOUT)

        if response.status_code not in [200, 201]:
            return None

        data = response.json()
        if not isinstance(data, list):
            return None

        # Check for Apify error
        if isinstance(data, dict) and data.get('error'):
            return None

        return data

    except (requests.exceptions.Timeout, requests.exceptions.RequestException):
        return None


def _try_async(api_token: str, payload: dict, headers: dict):
    """Async fallback: start run -> poll -> get dataset items."""
    try:
        run_url = f"{ASYNC_ENDPOINT}?token={api_token}"
        start_resp = requests.post(run_url, json=payload, headers=headers, timeout=30)

        if start_resp.status_code not in [200, 201]:
            return None

        run_data = start_resp.json().get('data', {})
        run_id = run_data.get('id')
        dataset_id = run_data.get('defaultDatasetId')

        if not run_id or not dataset_id:
            return None

        # Poll for completion
        status_url = f"https://api.apify.com/v2/actor-runs/{run_id}?token={api_token}"
        start_time = time.time()
        final_status = None

        while time.time() - start_time < MAX_POLL_SECONDS:
            time.sleep(POLL_INTERVAL_SECONDS)
            try:
                poll_resp = requests.get(status_url, timeout=10)
                final_status = poll_resp.json().get('data', {}).get('status')
            except requests.RequestException:
                continue

            if final_status in ('SUCCEEDED', 'FAILED', 'ABORTED', 'TIMED-OUT'):
                break

        if final_status != 'SUCCEEDED':
            return None

        # Get dataset items
        items_url = (
            f"https://api.apify.com/v2/datasets/{dataset_id}/items"
            f"?token={api_token}&limit=1000"
        )
        items_resp = requests.get(items_url, timeout=30)
        data = items_resp.json()

        if isinstance(data, list):
            return data
        return None

    except (requests.exceptions.RequestException, Exception):
        return None


def _build_result(comments: list, post_urls: list, shortcode_to_url: dict) -> Dict[str, Any]:
    """Build standardized result from apidojo comment data.

    Normalizes the apidojo output format to the standard format expected by
    the rest of the codebase.
    """
    normalized = []
    for comment in comments:
        if not isinstance(comment, dict):
            continue
        if comment.get('error'):
            continue

        # apidojo uses 'message' not 'text', 'user.username' not 'ownerUsername',
        # 'createdAt' not 'timestamp', 'likeCount' not 'likesCount'
        user = comment.get('user', {}) or {}
        shortcode = comment.get('postId', '')
        post_url = shortcode_to_url.get(shortcode, f'https://www.instagram.com/p/{shortcode}/')

        normalized.append({
            'id': str(comment.get('id', '')),
            'text': comment.get('message', ''),
            'ownerUsername': user.get('username', ''),
            'timestamp': comment.get('createdAt', ''),
            'likesCount': comment.get('likeCount', 0),
            'repliesCount': comment.get('replyCount', 0),
            'postUrl': post_url,
        })

    posts_with_comments = len(set(c['postUrl'] for c in normalized if c['postUrl']))

    return {
        'success': True,
        'data': {
            'comments': normalized,
            'posts_scraped': max(posts_with_comments, len(post_urls)),
            'total_comments': len(normalized),
        },
        'error': None
    }


if __name__ == '__main__':
    import sys
    import json

    if len(sys.argv) > 1:
        test_urls = sys.argv[1:]
    else:
        print("Usage: python apify_instagram_comments.py <post_url_1> [post_url_2] ...")
        print("Example: python apify_instagram_comments.py https://www.instagram.com/p/ABC123/")
        sys.exit(1)

    print("Instagram Comment Scraper Test")
    print("=" * 60)
    print(f"Scraping comments from {len(test_urls)} post(s)...\n")

    result = get_comments_for_posts(test_urls, results_limit_per_post=10)

    print(f"Success: {result['success']}")
    if result['success']:
        data = result['data']
        print(f"Total Comments: {data['total_comments']}")
        print(f"Posts Scraped: {data['posts_scraped']}")
        if data['comments']:
            print(f"\nFirst 5 comments:")
            for c in data['comments'][:5]:
                print(f"  @{c['ownerUsername']}: {c['text'][:80]}")
    else:
        print(f"Error: {result['error']}")

    print("\n" + "=" * 60)
    print("Test complete!")
