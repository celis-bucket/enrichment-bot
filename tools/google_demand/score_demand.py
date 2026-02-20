"""
Google Demand Scoring Tool

Purpose: Score brand organic presence and site coverage using Serper API.
Inputs: brand_name, domain, optional country code
Outputs: brand_demand_score (0-1), site_serp_coverage_score (0-1), google_confidence (0-1)
Dependencies: tools/core/google_search.py (Serper API)
Cost: 3 Serper API queries per company
"""

import os
import sys
import math
from typing import Dict, Any, Optional

# Allow imports from tools/ root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.google_search import google_search


def score_google_demand(
    brand_name: str,
    domain: str,
    country: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Run 3 Google queries to score brand demand and site coverage.

    Q1: "{brand_name}" -> brand organic presence
    Q2: "{brand_name} reviews opiniones" -> social proof
    Q3: "site:{domain}" -> indexed pages count

    Args:
        brand_name: Company/brand name (e.g., "Armatura")
        domain: Clean domain (e.g., "armatura.com.co")
        country: Optional country code for localized results ("co", "mx")

    Returns:
        {success, data: {brand_demand_score, site_serp_coverage_score,
                         google_confidence, query_details}, error}
    """
    queries_succeeded = 0
    brand_presence_score = 0.0
    social_proof_score = 0.0
    site_coverage_score = 0.0
    query_details = {}

    # --- Q1: Brand presence ---
    try:
        q1 = google_search(brand_name, num_results=10, country=country)
        if q1["success"]:
            queries_succeeded += 1
            data = q1["data"]
            organic = data.get("organic", [])
            kg = data.get("knowledge_graph")

            # Signal A: Knowledge graph exists (strong brand recognition)
            kg_bonus = 0.3 if kg else 0.0

            # Signal B: How many of top 10 results are from the brand's domain
            brand_in_top10 = sum(
                1 for r in organic if domain.lower() in r.get("link", "").lower()
            )
            domain_ratio = min(1.0, brand_in_top10 / 5)  # 5+ brand results = max

            # Signal C: Total organic results exist
            has_results = 0.2 if len(organic) >= 5 else 0.1 if len(organic) > 0 else 0.0

            brand_presence_score = min(1.0, kg_bonus + 0.5 * domain_ratio + has_results)
            query_details["q1_brand"] = {
                "query": brand_name,
                "knowledge_graph": bool(kg),
                "brand_in_top10": brand_in_top10,
                "organic_count": len(organic),
                "score": round(brand_presence_score, 3),
            }
        else:
            query_details["q1_brand"] = {"error": q1.get("error", "unknown")}
    except Exception as e:
        query_details["q1_brand"] = {"error": str(e)}

    # --- Q2: Social proof ---
    try:
        review_query = f"{brand_name} reviews opiniones"
        q2 = google_search(review_query, num_results=10, country=country)
        if q2["success"]:
            queries_succeeded += 1
            data = q2["data"]
            organic = data.get("organic", [])
            paa = data.get("people_also_ask", [])
            answer_box = data.get("answer_box")

            # Signal A: Review-site results
            review_domains = [
                "trustpilot", "google.com/maps", "yelp", "capterra",
                "opiniones", "reviews", "valoraciones", "resenas",
            ]
            review_hits = sum(
                1
                for r in organic
                if any(rd in r.get("link", "").lower() or rd in r.get("snippet", "").lower()
                       for rd in review_domains)
            )
            review_ratio = min(1.0, review_hits / 3)  # 3+ review results = max

            # Signal B: People Also Ask or Answer Box (brand is notable)
            paa_bonus = 0.2 if paa else 0.0
            ab_bonus = 0.1 if answer_box else 0.0

            # Signal C: Any results at all about the brand
            has_results = 0.2 if len(organic) >= 3 else 0.1 if len(organic) > 0 else 0.0

            social_proof_score = min(1.0, 0.5 * review_ratio + paa_bonus + ab_bonus + has_results)
            query_details["q2_reviews"] = {
                "query": review_query,
                "review_hits": review_hits,
                "people_also_ask": len(paa) if paa else 0,
                "answer_box": bool(answer_box),
                "organic_count": len(organic),
                "score": round(social_proof_score, 3),
            }
        else:
            query_details["q2_reviews"] = {"error": q2.get("error", "unknown")}
    except Exception as e:
        query_details["q2_reviews"] = {"error": str(e)}

    # --- Q3: Site coverage (indexed pages) ---
    try:
        site_query = f"site:{domain}"
        q3 = google_search(site_query, num_results=10, country=country)
        if q3["success"]:
            queries_succeeded += 1
            data = q3["data"]
            organic = data.get("organic", [])
            search_info = data.get("search_information", {})
            total_results = search_info.get("total_results", 0)

            # If search_information not available, estimate from organic count
            if total_results == 0 and organic:
                total_results = len(organic)

            # Normalize: 0 pages=0, 50 pages=0.5, 200+=0.8, 500+=1.0
            if total_results <= 0:
                site_coverage_score = 0.0
            elif total_results < 500:
                site_coverage_score = min(1.0, math.log(total_results + 1) / math.log(501))
            else:
                site_coverage_score = 1.0

            query_details["q3_site"] = {
                "query": site_query,
                "total_indexed_pages": total_results,
                "organic_sample": len(organic),
                "score": round(site_coverage_score, 3),
            }
        else:
            query_details["q3_site"] = {"error": q3.get("error", "unknown")}
    except Exception as e:
        query_details["q3_site"] = {"error": str(e)}

    # --- Composite scores ---
    if queries_succeeded == 0:
        return {
            "success": False,
            "data": {},
            "error": "All 3 Google demand queries failed",
        }

    brand_demand_score = 0.5 * brand_presence_score + 0.5 * social_proof_score
    google_confidence = round(queries_succeeded / 3, 2)

    return {
        "success": True,
        "data": {
            "brand_demand_score": round(brand_demand_score, 3),
            "site_serp_coverage_score": round(site_coverage_score, 3),
            "google_confidence": google_confidence,
            "query_details": query_details,
        },
        "error": None,
    }
