"""
Run Instagram logistics complaints analysis for a single company by IG username.

Purpose: Bypass the website→Instagram resolution step and go straight to analysis.
         Used by the Supabase cron runner for weekly batch scans.
Inputs: Instagram username (str)
Outputs: Full analysis dict (same schema as analyze_ig_complaints)
Dependencies: anthropic, requests, dotenv

Reuses internal functions from analyze_ig_complaints.py.
"""

import math
import os
import sys
import time
from typing import Dict, Any, List

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from social.apify_instagram import get_instagram_posts
from social.apify_instagram_comments import get_comments_for_posts
from logistics.analyze_ig_complaints import (
    _filter_brand_replies,
    _classify_comments_with_claude,
    _compute_risk_score,
    COMPLAINT_CATEGORIES,
    SEVERITY_WEIGHTS,
)


def run_single_by_username(username: str) -> Dict[str, Any]:
    """
    Run full logistics complaints analysis for an Instagram username.

    Skips the website→Instagram resolution step. Calls SearchAPI for posts,
    Apify for comments, Claude for classification, then computes risk score.

    Args:
        username: Instagram username (without @)

    Returns:
        Dict with: status, username, instagram, analysis, timings, error
    """
    start = time.time()
    result: Dict[str, Any] = {
        "username": username,
        "status": None,
        "error": None,
        "timings": {},
        "instagram": {},
        "analysis": None,
    }

    # --- Step 1: Fetch posts ---
    t0 = time.time()
    posts_result = get_instagram_posts(username, limit=12)
    result["timings"]["fetch_posts_sec"] = round(time.time() - t0, 1)

    if not posts_result["success"]:
        result["status"] = "error"
        result["error"] = f"Posts fetch failed: {posts_result['error']}"
        result["timings"]["total_sec"] = round(time.time() - start, 1)
        return result

    posts_data = posts_result["data"]
    posts = posts_data.get("posts", [])
    result["instagram"] = {
        "username": username,
        "url": f"https://instagram.com/{username}",
        "followers": posts_data.get("followers"),
        "is_private": posts_data.get("is_private", False),
        "posts_found": len(posts),
    }

    if posts_data.get("is_private"):
        result["status"] = "not_available"
        result["error"] = "Private account"
        result["timings"]["total_sec"] = round(time.time() - start, 1)
        return result

    if not posts:
        result["status"] = "not_available"
        result["error"] = "No posts found"
        result["timings"]["total_sec"] = round(time.time() - start, 1)
        return result

    # --- Step 2: Scrape comments ---
    post_urls = [p["url"] for p in posts]
    t0 = time.time()
    comments_result = get_comments_for_posts(post_urls, results_limit_per_post=50)
    result["timings"]["fetch_comments_sec"] = round(time.time() - t0, 1)

    if not comments_result["success"]:
        result["status"] = "error"
        result["error"] = f"Comments fetch failed: {comments_result['error']}"
        result["timings"]["total_sec"] = round(time.time() - start, 1)
        return result

    all_comments = comments_result["data"]["comments"]

    if not all_comments:
        result["status"] = "not_available"
        result["error"] = "No comments found"
        result["timings"]["total_sec"] = round(time.time() - start, 1)
        return result

    # --- Step 3: Filter brand replies ---
    filtered = _filter_brand_replies(all_comments, username)
    brand_excluded = len(all_comments) - len(filtered)

    if not filtered:
        result["status"] = "completed"
        result["analysis"] = {
            "risk_score": 0,
            "risk_level": "none",
            "summary": "Todos los comentarios son respuestas de la marca.",
            "posts_analyzed": len(posts),
            "total_comments_scraped": len(all_comments),
            "brand_replies_excluded": brand_excluded,
            "comments_analyzed": 0,
            "complaints_found": 0,
            "complaint_rate_pct": 0,
            "category_breakdown": {cat: 0 for cat in COMPLAINT_CATEGORIES},
            "top_flagged_comments": [],
            "recency_trend": "stable",
            "recent_complaint_rate": 0,
            "older_complaint_rate": 0,
            "claude_tokens_used": 0,
        }
        result["timings"]["total_sec"] = round(time.time() - start, 1)
        return result

    # --- Step 4: Claude classification ---
    ig_url = f"https://instagram.com/{username}"
    t0 = time.time()
    claude_result = _classify_comments_with_claude(filtered, username, ig_url)
    result["timings"]["claude_classify_sec"] = round(time.time() - t0, 1)

    if not claude_result["success"]:
        result["status"] = "error"
        result["error"] = f"Claude failed: {claude_result['error']}"
        result["timings"]["total_sec"] = round(time.time() - start, 1)
        return result

    flagged = claude_result["data"]["flagged_comments"]
    summary = claude_result["data"]["summary"]
    tokens = claude_result["data"].get("tokens_used", 0)

    # Enrich flagged with postUrl for recency weighting
    comments_by_id = {c["id"]: c for c in filtered}
    for fc in flagged:
        original = comments_by_id.get(fc["comment_id"], {})
        fc["_postUrl"] = original.get("postUrl", "")

    # --- Step 5: Risk score ---
    score_result = _compute_risk_score(flagged, len(filtered), posts)

    # Build category breakdown (flat counts)
    category_breakdown = {}
    for cat in COMPLAINT_CATEGORIES:
        category_breakdown[cat] = sum(1 for f in flagged if f["category"] == cat)

    # Build top flagged comments (enriched)
    top_flagged = []
    for fc in flagged:
        original = comments_by_id.get(fc["comment_id"], {})
        top_flagged.append({
            "comment_id": fc["comment_id"],
            "text": original.get("text", fc["excerpt"]),
            "category": fc["category"],
            "severity": fc["severity"],
            "owner": f"@{original.get('ownerUsername', '?')}",
            "timestamp": original.get("timestamp", ""),
            "likes": original.get("likesCount", 0),
            "post_url": original.get("postUrl", ""),
        })

    complaint_rate = round(len(flagged) / len(filtered) * 100, 2) if filtered else 0
    trend_data = score_result.get("recency_trend", {})

    result["status"] = "completed"
    result["analysis"] = {
        "risk_score": score_result["risk_score"],
        "risk_level": score_result["risk_level"],
        "summary": summary,
        "posts_analyzed": len(posts),
        "total_comments_scraped": len(all_comments),
        "brand_replies_excluded": brand_excluded,
        "comments_analyzed": len(filtered),
        "complaints_found": len(flagged),
        "complaint_rate_pct": complaint_rate,
        "category_breakdown": category_breakdown,
        "top_flagged_comments": top_flagged,
        "recency_trend": trend_data.get("trend", "stable"),
        "recent_complaint_rate": trend_data.get("recent_6_posts_complaint_rate", 0),
        "older_complaint_rate": trend_data.get("older_6_posts_complaint_rate", 0),
        "claude_tokens_used": tokens,
    }
    result["timings"]["total_sec"] = round(time.time() - start, 1)
    return result


if __name__ == "__main__":
    import json
    from dotenv import load_dotenv
    load_dotenv()

    username = sys.argv[1] if len(sys.argv) > 1 else "armaturaco"
    print(f"Running analysis for @{username}...")
    result = run_single_by_username(username)
    print(json.dumps(result, indent=2, ensure_ascii=False))
