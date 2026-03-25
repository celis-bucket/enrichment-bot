"""
Meta Ad Library – Active Ads Count

Purpose: Get count of active META ads for a brand
Inputs: Facebook page URL, Instagram username, or brand name
Outputs: Active ads count + Ad Library URL
Dependencies: requests, os

Methods:
  SearchAPI.io – GET https://www.searchapi.io/api/v1/search?engine=meta_ad_library
                 Fast (~2-5s), returns total_results directly.

Note: Meta Ad Library does NOT disclose spend/reach data for non-political ads.
      Only active ads count is reliably available for ecommerce brands.
"""

import os
import re
import urllib.parse
from typing import Dict, Any, Optional, List
from datetime import datetime
import requests
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
DEFAULT_COUNTRY = "CO"


def _extract_facebook_username(url: str) -> Optional[str]:
    """
    Extract Facebook page username from a URL.

    Handles:
        - https://facebook.com/mybrand
        - https://www.facebook.com/mybrand/
        - https://fb.com/mybrand
    """
    pattern = r'(?:facebook\.com|fb\.com)/([a-zA-Z0-9._-]+)/?'
    match = re.search(pattern, url)
    if match:
        username = match.group(1)
        # Filter out non-page URLs
        invalid = {'sharer', 'share', 'login', 'groups', 'events', 'pages',
                    'ads', 'watch', 'marketplace', 'gaming', 'help'}
        if username.lower() not in invalid:
            return username
    return None


def _build_ad_library_url(search_term: str, country: str = DEFAULT_COUNTRY) -> str:
    """Build a Meta Ad Library search URL for the given search term."""
    encoded = urllib.parse.quote(search_term)
    return (
        f"https://www.facebook.com/ads/library/"
        f"?active_status=active&ad_type=all&country={country}"
        f"&q={encoded}&search_type=keyword_unordered&media_type=all"
    )


def _searchapi_meta_ads(
    search_term: str,
    country: str = DEFAULT_COUNTRY,
) -> Optional[Dict[str, Any]]:
    """
    Get active ads count via SearchAPI.io Meta Ad Library engine.
    Returns result dict on success, None on failure.
    """
    api_key = os.getenv("SEARCHAPI_API_KEY")
    if not api_key:
        return None

    try:
        resp = requests.get(
            "https://www.searchapi.io/api/v1/search",
            params={
                "engine": "meta_ad_library",
                "q": search_term,
                "country": country,
                "active_status": "active",
                "ad_type": "all",
                "api_key": api_key,
            },
            timeout=15,
        )
        if resp.status_code != 200:
            return None

        data = resp.json()
        total = data.get("search_information", {}).get("total_results")
        if total is None:
            # Try counting ads array as fallback
            ads = data.get("ads", [])
            total = len(ads) if ads else None
        if total is None:
            return None

        ad_library_url = _build_ad_library_url(search_term, country)
        return {
            "success": True,
            "data": {
                "active_ads_count": total,
                "ad_library_url": ad_library_url,
                "search_term": search_term,
                "country": country,
                "scraped_at": datetime.now(tz=None).isoformat(),
            },
            "error": None,
        }
    except Exception:
        return None


def searchapi_facebook_page(identifier: str) -> Optional[Dict[str, Any]]:
    """
    Verify/discover a Facebook business page via SearchAPI.

    Args:
        identifier: Facebook page username or page ID.

    Returns:
        Dict with page_name, page_id, followers on success, None on failure.
    """
    api_key = os.getenv("SEARCHAPI_API_KEY")
    if not api_key:
        return None

    try:
        params = {"engine": "facebook_business_page", "api_key": api_key}
        # Detect if identifier is numeric (page_id) or string (username)
        if identifier.isdigit():
            params["page_id"] = identifier
        else:
            params["username"] = identifier

        resp = requests.get(
            "https://www.searchapi.io/api/v1/search",
            params=params,
            timeout=15,
        )
        if resp.status_code != 200:
            return None

        data = resp.json()
        if data.get("error"):
            return None

        page_info = data.get("page") or data.get("page_info") or data
        return {
            "page_name": page_info.get("name"),
            "page_id": page_info.get("id") or page_info.get("page_id"),
            "followers": page_info.get("followers") or page_info.get("follower_count"),
        }
    except Exception:
        return None


def get_meta_ads_count(
    identifier: str,
    country: str = DEFAULT_COUNTRY,
) -> Dict[str, Any]:
    """
    Get count of active META ads for a brand via SearchAPI.

    Args:
        identifier: Facebook page URL, Instagram username, or brand name.
        country: Two-letter country code for Ad Library filter (default: CO).

    Returns:
        Dict with:
            - success: bool
            - data: dict with active_ads_count, ad_library_url, scraped_at
            - error: str or None
    """
    try:
        # Determine search term from identifier
        search_term = identifier.strip()
        if "facebook.com" in identifier or "fb.com" in identifier:
            fb_username = _extract_facebook_username(identifier)
            if fb_username:
                search_term = fb_username

        result = _searchapi_meta_ads(search_term, country)
        if result:
            return result

        return {
            "success": False,
            "data": {},
            "error": f"SearchAPI meta_ad_library returned no results for '{search_term}'",
        }

    except requests.exceptions.Timeout:
        return {
            "success": False,
            "data": {},
            "error": "Meta ads API request timed out",
        }

    except requests.exceptions.RequestException as e:
        return {
            "success": False,
            "data": {},
            "error": f"Meta ads API request failed: {str(e)}",
        }

    except Exception as e:
        return {
            "success": False,
            "data": {},
            "error": f"Meta ads error: {str(e)}",
        }


def get_meta_ads_multi_search(
    search_terms: List[str],
    country: str = DEFAULT_COUNTRY,
) -> Dict[str, Any]:
    """
    Search Meta Ad Library with multiple terms, return the best result.

    Useful when a brand may advertise under different names (FB page vs IG account).
    Tries each term and returns the one with the highest active_ads_count.

    Args:
        search_terms: List of search terms to try (e.g., [fb_page_name, ig_username, brand_name])
        country: Two-letter country code

    Returns:
        Best result dict (same format as get_meta_ads_count)
    """
    best_result = None
    best_count = -1

    for term in search_terms:
        if not term:
            continue
        result = _searchapi_meta_ads(term.strip(), country)
        if result and result.get("success"):
            count = result["data"].get("active_ads_count", 0)
            if count > best_count:
                best_count = count
                best_result = result

    if best_result:
        return best_result

    return {
        "success": False,
        "data": {},
        "error": f"No Meta ads found for any of: {search_terms}",
    }


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        test_input = sys.argv[1]
    else:
        test_input = "arturo calle"

    country = sys.argv[2] if len(sys.argv) > 2 else "CO"

    print("Meta Ad Library Search Test (SearchAPI)")
    print("=" * 60)
    print(f"Input: {test_input}")
    print(f"Country: {country}\n")

    result = get_meta_ads_count(test_input, country)

    print(f"Success: {result['success']}")
    if result["success"]:
        data = result["data"]
        print(f"Active Ads Count: {data['active_ads_count']}")
        print(f"Search Term Used: {data['search_term']}")
        print(f"Ad Library URL: {data['ad_library_url']}")
        print(f"Scraped At: {data['scraped_at']}")
    else:
        print(f"Error: {result['error']}")

    print("\n" + "=" * 60)
    print("Test complete!")
