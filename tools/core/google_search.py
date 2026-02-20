"""
Google Search Tool (via Serper API)

Purpose: Search Google programmatically using the Serper API
Inputs: Query string, optional parameters (num results, country, language, search type)
Outputs: Search results with titles, links, snippets, and metadata
Dependencies: requests, python-dotenv

API Docs: https://serper.dev/
Rate limits: Depends on plan (free tier: 2,500 queries/month)
"""

import os
import json
from typing import Dict, Any, Optional, List
import requests
from dotenv import load_dotenv

load_dotenv()

SERPER_API_URL = "https://google.serper.dev"


def google_search(
    query: str,
    num_results: int = 10,
    search_type: str = "search",
    country: Optional[str] = None,
    language: Optional[str] = None,
    page: int = 1,
) -> Dict[str, Any]:
    """
    Perform a Google search using the Serper API.

    Args:
        query: Search query string
        num_results: Number of results to return (default: 10, max: 100)
        search_type: Type of search - "search", "news", "images", "places", "maps"
        country: Country code for localized results (e.g., "us", "mx", "es")
        language: Language code (e.g., "en", "es")
        page: Page number for pagination (default: 1)

    Returns:
        Dict with:
            - success: bool
            - data: dict with search results and metadata
            - error: str or None
    """
    api_key = os.getenv("SERPER_API_KEY")
    if not api_key:
        return {
            "success": False,
            "data": {},
            "error": "SERPER_API_KEY not found in environment variables. Add it to .env",
        }

    # Build endpoint URL based on search type
    valid_types = ["search", "news", "images", "places", "maps"]
    if search_type not in valid_types:
        return {
            "success": False,
            "data": {},
            "error": f"Invalid search_type '{search_type}'. Must be one of: {valid_types}",
        }

    url = f"{SERPER_API_URL}/{search_type}"

    headers = {
        "X-API-KEY": api_key,
        "Content-Type": "application/json",
    }

    payload = {
        "q": query,
        "num": num_results,
        "page": page,
    }

    if country:
        payload["gl"] = country
    if language:
        payload["hl"] = language

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)

        if response.status_code == 401:
            return {
                "success": False,
                "data": {},
                "error": "Invalid SERPER_API_KEY. Check your API key in .env",
            }

        if response.status_code == 429:
            return {
                "success": False,
                "data": {},
                "error": "Serper API rate limit reached. Check your plan quota.",
            }

        if response.status_code >= 400:
            return {
                "success": False,
                "data": {},
                "error": f"Serper API error: HTTP {response.status_code} - {response.text}",
            }

        results = response.json()

        # Normalize the response into a cleaner structure
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
            "error": "Serper API request timed out after 30 seconds",
        }
    except requests.exceptions.ConnectionError as e:
        return {
            "success": False,
            "data": {},
            "error": f"Connection error to Serper API: {str(e)}",
        }
    except Exception as e:
        return {
            "success": False,
            "data": {},
            "error": f"Unexpected error: {str(e)}",
        }


def _parse_results(raw: Dict[str, Any], search_type: str) -> Dict[str, Any]:
    """Parse raw Serper response into a clean structure."""
    parsed = {
        "query": raw.get("searchParameters", {}).get("q", ""),
        "search_type": search_type,
        "credits_used": raw.get("credits", 1),
    }

    # Search information (total results estimate, search time)
    if "searchInformation" in raw:
        si = raw["searchInformation"]
        parsed["search_information"] = {
            "total_results": int(si.get("totalResults", 0)),
            "search_time": si.get("searchTime", 0),
        }

    # Organic results (standard search)
    if "organic" in raw:
        parsed["organic"] = [
            {
                "title": r.get("title", ""),
                "link": r.get("link", ""),
                "snippet": r.get("snippet", ""),
                "position": r.get("position"),
            }
            for r in raw["organic"]
        ]

    # Knowledge graph
    if "knowledgeGraph" in raw:
        kg = raw["knowledgeGraph"]
        parsed["knowledge_graph"] = {
            "title": kg.get("title", ""),
            "type": kg.get("type", ""),
            "description": kg.get("description", ""),
            "website": kg.get("website", ""),
            "attributes": kg.get("attributes", {}),
        }

    # Answer box
    if "answerBox" in raw:
        ab = raw["answerBox"]
        parsed["answer_box"] = {
            "title": ab.get("title", ""),
            "answer": ab.get("answer", ab.get("snippet", "")),
            "link": ab.get("link", ""),
        }

    # People also ask
    if "peopleAlsoAsk" in raw:
        parsed["people_also_ask"] = [
            {
                "question": r.get("question", ""),
                "snippet": r.get("snippet", ""),
                "link": r.get("link", ""),
            }
            for r in raw["peopleAlsoAsk"]
        ]

    # Related searches
    if "relatedSearches" in raw:
        parsed["related_searches"] = [
            r.get("query", "") for r in raw["relatedSearches"]
        ]

    # News results
    if "news" in raw:
        parsed["news"] = [
            {
                "title": r.get("title", ""),
                "link": r.get("link", ""),
                "snippet": r.get("snippet", ""),
                "date": r.get("date", ""),
                "source": r.get("source", ""),
            }
            for r in raw["news"]
        ]

    # Image results
    if "images" in raw:
        parsed["images"] = [
            {
                "title": r.get("title", ""),
                "link": r.get("link", ""),
                "image_url": r.get("imageUrl", ""),
                "source": r.get("source", ""),
            }
            for r in raw["images"]
        ]

    # Places results
    if "places" in raw:
        parsed["places"] = [
            {
                "title": r.get("title", ""),
                "address": r.get("address", ""),
                "rating": r.get("rating"),
                "reviews": r.get("ratingCount"),
                "category": r.get("category", ""),
            }
            for r in raw["places"]
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
    print("Google Search Tool (Serper API) - Test")
    print("=" * 60)

    # Test basic search
    test_query = "Python web scraping best practices"
    print(f"\nSearching: '{test_query}'")

    result = google_search(test_query, num_results=3)

    print(f"Success: {result['success']}")
    if result["success"]:
        data = result["data"]
        print(f"Credits used: {data.get('credits_used', 'N/A')}")

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
