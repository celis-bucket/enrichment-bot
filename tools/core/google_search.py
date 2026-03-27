"""
Google Search Tool (via SearchAPI.io)

Purpose: Search Google programmatically using the SearchAPI.io API
Inputs: Query string, optional parameters (num results, country, language, search type)
Outputs: Search results with titles, links, snippets, and metadata
Dependencies: requests, python-dotenv

API Docs: https://www.searchapi.io/docs/google
"""

import os
import json
from typing import Dict, Any, Optional, List
import requests
from dotenv import load_dotenv

load_dotenv()

SEARCHAPI_BASE_URL = "https://www.searchapi.io/api/v1/search"

# Map search_type to SearchAPI engine
_ENGINE_MAP = {
    "search": "google",
    "news": "google_news",
    "images": "google_images",
    "places": "google_maps",
    "maps": "google_maps",
}


def google_search(
    query: str,
    num_results: int = 10,
    search_type: str = "search",
    country: Optional[str] = None,
    language: Optional[str] = None,
    page: int = 1,
) -> Dict[str, Any]:
    """
    Perform a Google search using the SearchAPI.io API.

    Args:
        query: Search query string
        num_results: Number of results to return (default: 10, max: 100)
        search_type: Type of search - "search", "news", "images", "places", "maps"
        country: Country code for localized results (e.g., "co", "mx", "us")
        language: Language code (e.g., "en", "es")
        page: Page number for pagination (default: 1)

    Returns:
        Dict with:
            - success: bool
            - data: dict with search results and metadata
            - error: str or None
    """
    api_key = os.getenv("SEARCHAPI_API_KEY")
    if not api_key:
        return {
            "success": False,
            "data": {},
            "error": "SEARCHAPI_API_KEY not found in environment variables. Add it to .env",
        }

    engine = _ENGINE_MAP.get(search_type)
    if not engine:
        return {
            "success": False,
            "data": {},
            "error": f"Invalid search_type '{search_type}'. Must be one of: {list(_ENGINE_MAP.keys())}",
        }

    params = {
        "engine": engine,
        "q": query,
        "api_key": api_key,
    }

    # Google Maps engine doesn't support num parameter
    if engine != "google_maps":
        params["num"] = num_results
        if page > 1:
            params["page"] = page

    if country:
        params["gl"] = country
    if language:
        params["hl"] = language

    try:
        response = requests.get(SEARCHAPI_BASE_URL, params=params, timeout=30)

        if response.status_code == 401:
            return {
                "success": False,
                "data": {},
                "error": "Invalid SEARCHAPI_API_KEY. Check your API key in .env",
            }

        if response.status_code == 429:
            return {
                "success": False,
                "data": {},
                "error": "SearchAPI rate limit reached. Check your plan quota.",
            }

        if response.status_code >= 400:
            return {
                "success": False,
                "data": {},
                "error": f"SearchAPI error: HTTP {response.status_code} - {response.text[:300]}",
            }

        results = response.json()

        parsed = _parse_results(results, search_type)

        return {
            "success": True,
            "data": parsed,
            "error": None,
        }

    except requests.exceptions.Timeout:
        return {
            "success": False,
            "data": {},
            "error": "SearchAPI request timed out after 30 seconds",
        }
    except requests.exceptions.ConnectionError as e:
        return {
            "success": False,
            "data": {},
            "error": f"Connection error to SearchAPI: {str(e)}",
        }
    except Exception as e:
        return {
            "success": False,
            "data": {},
            "error": f"Unexpected error: {str(e)}",
        }


def _parse_results(raw: Dict[str, Any], search_type: str) -> Dict[str, Any]:
    """Parse raw SearchAPI response into a clean structure matching the existing interface."""
    parsed = {
        "query": raw.get("search_parameters", {}).get("q", ""),
        "search_type": search_type,
        "credits_used": 1,
    }

    # Search information
    if "search_information" in raw:
        si = raw["search_information"]
        parsed["search_information"] = {
            "total_results": int(si.get("total_results", 0)),
            "search_time": si.get("time_taken_displayed", 0),
        }

    # Organic results (SearchAPI uses "organic_results")
    if "organic_results" in raw:
        parsed["organic"] = [
            {
                "title": r.get("title", ""),
                "link": r.get("link", ""),
                "snippet": r.get("snippet", ""),
                "position": r.get("position"),
            }
            for r in raw["organic_results"]
        ]

    # Knowledge graph
    if "knowledge_graph" in raw:
        kg = raw["knowledge_graph"]
        parsed["knowledge_graph"] = {
            "title": kg.get("title", ""),
            "type": kg.get("type", ""),
            "description": kg.get("description", ""),
            "website": kg.get("website", ""),
            "attributes": kg.get("attributes", {}),
        }

    # Answer box
    if "answer_box" in raw:
        ab = raw["answer_box"]
        parsed["answer_box"] = {
            "title": ab.get("title", ""),
            "answer": ab.get("answer", ab.get("snippet", "")),
            "link": ab.get("link", ""),
        }

    # People also ask (SearchAPI uses "related_questions")
    if "related_questions" in raw:
        parsed["people_also_ask"] = [
            {
                "question": r.get("question", ""),
                "snippet": r.get("snippet", ""),
                "link": r.get("link", ""),
            }
            for r in raw["related_questions"]
        ]

    # Related searches
    if "related_searches" in raw:
        parsed["related_searches"] = [
            r.get("query", "") for r in raw["related_searches"]
        ]

    # News results
    if "news_results" in raw:
        parsed["news"] = [
            {
                "title": r.get("title", ""),
                "link": r.get("link", ""),
                "snippet": r.get("snippet", ""),
                "date": r.get("date", ""),
                "source": r.get("source", {}).get("name", "") if isinstance(r.get("source"), dict) else r.get("source", ""),
            }
            for r in raw["news_results"]
        ]

    # Image results
    if "images" in raw:
        parsed["images"] = [
            {
                "title": r.get("title", ""),
                "link": r.get("link", ""),
                "image_url": r.get("original", r.get("thumbnail", "")),
                "source": r.get("source", ""),
            }
            for r in raw.get("images", {}).get("images", [])
            if isinstance(r, dict)
        ]
    if "image_results" in raw:
        parsed["images"] = [
            {
                "title": r.get("title", ""),
                "link": r.get("link", ""),
                "image_url": r.get("original", {}).get("link", "") if isinstance(r.get("original"), dict) else r.get("original", ""),
                "source": r.get("source", ""),
            }
            for r in raw["image_results"]
        ]

    # Places / Maps results (SearchAPI uses "local_results")
    if "local_results" in raw:
        parsed["places"] = [
            {
                "title": r.get("title", ""),
                "address": r.get("address", ""),
                "rating": r.get("rating"),
                "reviews": r.get("reviews"),
                "category": r.get("type", ""),
            }
            for r in raw["local_results"]
        ]

    return parsed


def google_search_batch(
    queries: List[str],
    **kwargs,
) -> Dict[str, Any]:
    """
    Run multiple Google searches sequentially.

    Args:
        queries: List of search query strings
        **kwargs: Additional arguments passed to google_search()

    Returns:
        Dict with:
            - success: bool
            - data: list of {query, result} dicts
            - error: str or None
    """
    results = []
    errors = []

    for query in queries:
        result = google_search(query, **kwargs)
        results.append({"query": query, "result": result})

        if not result["success"]:
            errors.append(f"{query}: {result['error']}")

    return {
        "success": len(errors) == 0,
        "data": results,
        "error": "; ".join(errors) if errors else None,
        "stats": {
            "total": len(queries),
            "successful": len(queries) - len(errors),
            "failed": len(errors),
        },
    }


if __name__ == "__main__":
    print("Google Search Tool (SearchAPI.io) - Test")
    print("=" * 60)

    test_query = "Python web scraping best practices"
    print(f"\nSearching: '{test_query}'")

    result = google_search(test_query, num_results=3)

    print(f"Success: {result['success']}")
    if result["success"]:
        data = result["data"]

        if "organic" in data:
            print(f"\nOrganic results ({len(data['organic'])}):")
            for r in data["organic"]:
                print(f"  [{r['position']}] {r['title']}")
                print(f"      {r['link']}")
                print(f"      {r['snippet'][:100]}...")

        if "related_searches" in data:
            print(f"\nRelated searches: {', '.join(data['related_searches'][:5])}")
    else:
        print(f"Error: {result['error']}")
