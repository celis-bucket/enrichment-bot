"""
TikTok Ads Library – Active Ads Count

Purpose: Get count of active TikTok ads for a brand
Inputs: Brand name, TikTok username, or advertiser name
Outputs: Active ads count (filtered by advertiser name match) + Ads Library URL
Dependencies: requests, os

Methods:
  SearchAPI.io – GET https://www.searchapi.io/api/v1/search?engine=tiktok_ads_library
                 Returns ads array; we filter by advertiser name similarity.

Note: TikTok Ads Library keyword search is broad (matches partial names).
      total_results is unreliable (often capped at 1000).
      We count only ads whose advertiser name fuzzy-matches the search term.
"""

import os
import re
import urllib.parse
from typing import Dict, Any, Optional, List
from datetime import datetime
import requests
from dotenv import load_dotenv

load_dotenv()


def _normalize(text: str) -> str:
    """Lowercase, strip, remove non-alphanumeric for comparison."""
    return re.sub(r"[^a-z0-9]", "", text.lower())


def _advertiser_matches(advertiser: str, search_term: str) -> bool:
    """Check if an advertiser name is a plausible match for the search term.

    Strategy:
    - Multi-word search terms: all tokens must appear in the advertiser name.
    - Single-word search terms: must match as a standalone word boundary
      (e.g., "rappi" matches "Rappi Foods" but not "therappi").
    - The advertiser name can also be a substring of the search term.
    """
    if not advertiser or not search_term:
        return False

    norm_adv = _normalize(advertiser)
    norm_search = _normalize(search_term)

    # Exact match
    if norm_adv == norm_search:
        return True

    # Advertiser is contained in search term (rare but valid)
    if norm_adv and norm_adv in norm_search:
        return True

    # Multi-word: all tokens must appear in advertiser
    search_tokens = [_normalize(t) for t in search_term.strip().split() if t]
    if len(search_tokens) > 1:
        return all(token in norm_adv for token in search_tokens)

    # Single-word: require word-boundary match in the original advertiser name
    # "rappi" matches "Rappi Foods Galicia" but NOT "therappi", "nikegiu2", or "raul_falabella"
    # Treat underscores as word characters (TikTok usernames use _ as glue)
    pattern = r"(?<![a-zA-Z0-9_])" + re.escape(search_term.strip().lower()) + r"(?![a-zA-Z0-9_])"
    return bool(re.search(pattern, advertiser.lower()))


def _build_ads_library_url(search_term: str) -> str:
    """Build a TikTok Ads Library search URL for the given search term."""
    encoded = urllib.parse.quote(search_term)
    return (
        f"https://library.tiktok.com/ads"
        f"?region=all&adv_name={encoded}&sort_by=last_shown_date"
    )


def _searchapi_tiktok_ads(
    search_term: str,
) -> Optional[Dict[str, Any]]:
    """
    Get active ads count via SearchAPI.io TikTok Ads Library engine.
    Filters ads by advertiser name match for accuracy.
    Returns result dict on success, None on failure.
    """
    api_key = os.getenv("SEARCHAPI_API_KEY")
    if not api_key:
        return None

    try:
        resp = requests.get(
            "https://www.searchapi.io/api/v1/search",
            params={
                "engine": "tiktok_ads_library",
                "q": search_term,
                "api_key": api_key,
            },
            timeout=15,
        )
        if resp.status_code != 200:
            return None

        data = resp.json()
        ads = data.get("ads", [])
        if not ads:
            return None

        # Filter: only count ads whose advertiser name matches the brand
        matched_ads = [a for a in ads if _advertiser_matches(a.get("advertiser", ""), search_term)]
        matched_count = len(matched_ads)

        # Collect unique matched advertiser names for debugging
        matched_advertisers = list(set(a.get("advertiser", "") for a in matched_ads))

        ads_library_url = _build_ads_library_url(search_term)
        return {
            "success": True,
            "data": {
                "active_ads_count": matched_count,
                "total_results_raw": data.get("search_information", {}).get("total_results"),
                "ads_in_page": len(ads),
                "matched_advertisers": matched_advertisers,
                "ads_library_url": ads_library_url,
                "search_term": search_term,
                "scraped_at": datetime.now(tz=None).isoformat(),
            },
            "error": None,
        }
    except Exception:
        return None


def get_tiktok_ads_count(
    identifier: str,
) -> Dict[str, Any]:
    """
    Get count of active TikTok ads for a brand via SearchAPI.

    Args:
        identifier: Brand name, TikTok username, or advertiser name.

    Returns:
        Dict with:
            - success: bool
            - data: dict with active_ads_count, ads_library_url, scraped_at
            - error: str or None
    """
    try:
        search_term = identifier.strip()
        result = _searchapi_tiktok_ads(search_term)
        if result:
            return result

        return {
            "success": False,
            "data": {},
            "error": f"SearchAPI tiktok_ads_library returned no results for '{search_term}'",
        }

    except requests.exceptions.Timeout:
        return {
            "success": False,
            "data": {},
            "error": "TikTok ads API request timed out",
        }

    except requests.exceptions.RequestException as e:
        return {
            "success": False,
            "data": {},
            "error": f"TikTok ads API request failed: {str(e)}",
        }

    except Exception as e:
        return {
            "success": False,
            "data": {},
            "error": f"TikTok ads error: {str(e)}",
        }


def get_tiktok_ads_multi_search(
    search_terms: List[str],
) -> Dict[str, Any]:
    """
    Search TikTok Ads Library with multiple terms, return the best result.

    Useful when a brand may advertise under different names.
    Tries each term and returns the one with the highest active_ads_count.

    Args:
        search_terms: List of search terms to try (e.g., [tiktok_username, brand_name])

    Returns:
        Best result dict (same format as get_tiktok_ads_count)
    """
    best_result = None
    best_count = -1

    for term in search_terms:
        if not term:
            continue
        result = _searchapi_tiktok_ads(term.strip())
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
        "error": f"No TikTok ads found for any of: {search_terms}",
    }


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        test_input = sys.argv[1]
    else:
        test_input = "arturo calle"

    print("TikTok Ads Library Search Test (SearchAPI)")
    print("=" * 60)
    print(f"Input: {test_input}\n")

    result = get_tiktok_ads_count(test_input)

    print(f"Success: {result['success']}")
    if result["success"]:
        data = result["data"]
        print(f"Active Ads Count (matched): {data['active_ads_count']}")
        print(f"Total Results (raw API):    {data.get('total_results_raw')}")
        print(f"Ads in Page:                {data.get('ads_in_page')}")
        print(f"Matched Advertisers:        {data.get('matched_advertisers')}")
        print(f"Search Term Used:           {data['search_term']}")
        print(f"Ads Library URL:            {data['ads_library_url']}")
        print(f"Scraped At:                 {data['scraped_at']}")
    else:
        print(f"Error: {result['error']}")

    print("\n" + "=" * 60)
    print("Test complete!")
