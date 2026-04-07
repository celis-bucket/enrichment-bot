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
from concurrent.futures import ThreadPoolExecutor
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
    query_details = {}

    # --- Run all 3 queries in parallel ---
    def _run_q1():
        """Q1: Brand presence"""
        try:
            q1 = google_search(brand_name, num_results=10, country=country)
            if q1["success"]:
                data = q1["data"]
                organic = data.get("organic", [])
                kg = data.get("knowledge_graph")
                kg_bonus = 0.3 if kg else 0.0
                brand_in_top10 = sum(
                    1 for r in organic if domain.lower() in r.get("link", "").lower()
                )
                domain_ratio = min(1.0, brand_in_top10 / 5)
                has_results = 0.2 if len(organic) >= 5 else 0.1 if len(organic) > 0 else 0.0
                score = min(1.0, kg_bonus + 0.5 * domain_ratio + has_results)
                return True, score, {
                    "query": brand_name,
                    "knowledge_graph": bool(kg),
                    "brand_in_top10": brand_in_top10,
                    "organic_count": len(organic),
                    "score": round(score, 3),
                }
            return False, 0.0, {"error": q1.get("error", "unknown")}
        except Exception as e:
            return False, 0.0, {"error": str(e)}

    def _run_q2():
        """Q2: Social proof"""
        try:
            review_query = f"{brand_name} reviews opiniones"
            q2 = google_search(review_query, num_results=10, country=country)
            if q2["success"]:
                data = q2["data"]
                organic = data.get("organic", [])
                paa = data.get("people_also_ask", [])
                answer_box = data.get("answer_box")
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
                review_ratio = min(1.0, review_hits / 3)
                paa_bonus = 0.2 if paa else 0.0
                ab_bonus = 0.1 if answer_box else 0.0
                has_results = 0.2 if len(organic) >= 3 else 0.1 if len(organic) > 0 else 0.0
                score = min(1.0, 0.5 * review_ratio + paa_bonus + ab_bonus + has_results)
                return True, score, {
                    "query": review_query,
                    "review_hits": review_hits,
                    "people_also_ask": len(paa) if paa else 0,
                    "answer_box": bool(answer_box),
                    "organic_count": len(organic),
                    "score": round(score, 3),
                }
            return False, 0.0, {"error": q2.get("error", "unknown")}
        except Exception as e:
            return False, 0.0, {"error": str(e)}

    def _run_q3():
        """Q3: Site coverage (indexed pages)"""
        try:
            site_query = f"site:{domain}"
            q3 = google_search(site_query, num_results=10, country=country)
            if q3["success"]:
                data = q3["data"]
                organic = data.get("organic", [])
                search_info = data.get("search_information", {})
                total_results = search_info.get("total_results", 0)
                if total_results == 0 and organic:
                    total_results = len(organic)
                if total_results <= 0:
                    score = 0.0
                elif total_results < 500:
                    score = min(1.0, math.log(total_results + 1) / math.log(501))
                else:
                    score = 1.0
                return True, score, {
                    "query": site_query,
                    "total_indexed_pages": total_results,
                    "organic_sample": len(organic),
                    "score": round(score, 3),
                }
            return False, 0.0, {"error": q3.get("error", "unknown")}
        except Exception as e:
            return False, 0.0, {"error": str(e)}

    with ThreadPoolExecutor(max_workers=3) as pool:
        f1 = pool.submit(_run_q1)
        f2 = pool.submit(_run_q2)
        f3 = pool.submit(_run_q3)

    ok1, brand_presence_score, query_details["q1_brand"] = f1.result()
    ok2, social_proof_score, query_details["q2_reviews"] = f2.result()
    ok3, site_coverage_score, query_details["q3_site"] = f3.result()
    queries_succeeded = sum([ok1, ok2, ok3])

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
