"""
Brand-to-URL Resolver Tool

Purpose: Detect if user input is a URL or a brand name, and resolve brand names to URLs via Google Search (Serper)
Inputs: Raw user input string (URL or brand name + country)
Outputs: Resolved URL
Dependencies: tools/core/google_search.py
"""

from typing import Dict, Any, Optional
from core.google_search import google_search


def _looks_like_url(text: str) -> bool:
    """
    Simple heuristic: if it contains a dot and no spaces, it's probably a URL.
    Examples that return True:  "armatura.com.co", "https://trueshop.co"
    Examples that return False: "Armatura Colombia", "trueshop mexico"
    """
    stripped = text.strip()
    return "." in stripped and " " not in stripped


def resolve_brand_url(raw_input: str, country: Optional[str] = None) -> Dict[str, Any]:
    """
    Resolve user input to an e-commerce URL.

    If the input looks like a URL, returns it as-is.
    If it looks like a brand name (with optional country), searches Google
    via the Serper API to find the brand's e-commerce website.

    Args:
        raw_input: Raw user input — either a URL or brand name (e.g., "Armatura Colombia")
        country: Optional country context to improve search accuracy (e.g., "Colombia")

    Returns:
        Dict with:
            - success: bool
            - data: dict with 'url', 'was_searched', 'original_input', 'search_query'
            - error: str or None
    """
    text = raw_input.strip()

    if not text:
        return {
            "success": False,
            "data": {},
            "error": "Empty input",
        }

    # If it looks like a URL, return as-is (let normalize_url handle validation)
    if _looks_like_url(text):
        return {
            "success": True,
            "data": {
                "url": text,
                "was_searched": False,
                "original_input": text,
                "search_query": None,
            },
            "error": None,
        }

    # Treat as brand name — search Google for the e-commerce site
    country_suffix = f" {country}" if country else ""
    search_query = f"{text}{country_suffix} ecommerce official site"

    result = google_search(search_query, num_results=5)

    if not result["success"]:
        return {
            "success": False,
            "data": {"original_input": text, "search_query": search_query},
            "error": f"Google search failed: {result['error']}",
        }

    organic = result["data"].get("organic", [])
    if not organic:
        return {
            "success": False,
            "data": {"original_input": text, "search_query": search_query},
            "error": f"No results found for '{text}'. Try entering the URL directly.",
        }

    # Return the first organic result's URL
    resolved_url = organic[0]["link"]

    return {
        "success": True,
        "data": {
            "url": resolved_url,
            "was_searched": True,
            "original_input": text,
            "search_query": search_query,
        },
        "error": None,
    }


if __name__ == "__main__":
    print("Brand-to-URL Resolver - Test")
    print("=" * 60)

    test_inputs = [
        "armatura.com.co",           # URL — should pass through
        "https://trueshop.co",       # URL with protocol — should pass through
        "Armatura Colombia",         # Brand name — should search
        "Trueshop Mexico",           # Brand name — should search
    ]

    for test in test_inputs:
        print(f"\nInput: '{test}'")
        result = resolve_brand_url(test)
        print(f"  Success: {result['success']}")
        if result["success"]:
            print(f"  URL: {result['data']['url']}")
            print(f"  Searched: {result['data']['was_searched']}")
        else:
            print(f"  Error: {result['error']}")
