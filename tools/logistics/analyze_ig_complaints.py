"""
Instagram Logistics Complaints Analyzer

Purpose: Analyze a company's Instagram comments to detect logistics complaints
         and produce a weighted risk score (0-100) with evidence.
Inputs: Company website URL
Outputs: JSON with risk_score, risk_level, flagged comments, category breakdown
Dependencies: anthropic, requests, dotenv

Workflow: workflows/ig_logistics_complaints.md
"""

import math
import os
import re
import sys
import json
import time
from typing import Dict, Any, Optional, List
from datetime import datetime

from dotenv import load_dotenv

# Allow imports from parent tools/ directory
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from social.extract_social_links import extract_social_links, search_instagram_via_serper
from social.apify_instagram import get_instagram_posts, extract_instagram_username
from social.apify_instagram_comments import get_comments_for_posts

load_dotenv()

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
MODEL = "claude-sonnet-4-5-20250929"

SEVERITY_WEIGHTS = {"high": 3.0, "medium": 2.0, "low": 1.0}

RISK_LEVELS = [
    (0, "none"),
    (25, "low"),
    (50, "medium"),
    (75, "high"),
    (100, "critical"),
]

COMPLAINT_CATEGORIES = [
    "DELAY", "NON_DELIVERY", "DAMAGED", "WRONG_ITEM", "RETURN_REFUND", "POOR_SERVICE"
]

SYSTEM_PROMPT = """You are a logistics complaint analyst for Latin American e-commerce companies.
You will receive Instagram comments (in Spanish) from a company's recent posts.

Your task: identify comments that express logistics complaints related to
order delivery problems. Focus ONLY on these categories:

1. DELAY - Shipping delays, late deliveries ("lleva semanas", "no ha llegado", "tarda mucho")
2. NON_DELIVERY - Orders never arrived ("nunca llegó", "pedido perdido")
3. DAMAGED - Packages arrived damaged ("llegó roto", "caja dañada", "producto dañado")
4. WRONG_ITEM - Received wrong product ("me llegó otro", "producto equivocado")
5. RETURN_REFUND - Difficulty with returns or refunds ("no me devuelven", "reembolso", "devolución")
6. POOR_SERVICE - Bad customer service specifically about order issues ("no responden", "no dan solución", "pésimo servicio de envío")

IMPORTANT RULES:
- ONLY flag comments that are clearly about logistics/delivery problems
- IGNORE general product complaints, pricing complaints, or unrelated negativity
- IGNORE comments that are just questions ("¿cuánto tarda el envío?") unless they also express frustration about an actual order
- Each flagged comment must have a severity: "high" (explicit complaint with detail), "medium" (complaint but vague), or "low" (mild dissatisfaction or borderline)
- Work ONLY with the Spanish text as provided. Do not translate.

Call the analyze_logistics_complaints tool with your analysis."""

ANALYSIS_TOOL = {
    "name": "analyze_logistics_complaints",
    "description": "Submit the logistics complaint analysis for this company's Instagram comments.",
    "input_schema": {
        "type": "object",
        "properties": {
            "flagged_comments": {
                "type": "array",
                "description": "List of comments identified as logistics complaints. Empty array if none found.",
                "items": {
                    "type": "object",
                    "properties": {
                        "comment_id": {
                            "type": "string",
                            "description": "The id of the flagged comment."
                        },
                        "category": {
                            "type": "string",
                            "enum": COMPLAINT_CATEGORIES,
                            "description": "The logistics complaint category."
                        },
                        "severity": {
                            "type": "string",
                            "enum": ["high", "medium", "low"],
                            "description": "Severity of the complaint."
                        },
                        "excerpt": {
                            "type": "string",
                            "description": "Key phrase from the comment (max 120 chars)."
                        }
                    },
                    "required": ["comment_id", "category", "severity", "excerpt"]
                }
            },
            "summary": {
                "type": "string",
                "description": "2-3 sentence Spanish summary of the overall logistics sentiment. If no complaints found, state that clearly."
            }
        },
        "required": ["flagged_comments", "summary"]
    }
}


# ---------------------------------------------------------------------------
# Main public function
# ---------------------------------------------------------------------------
def analyze_logistics_complaints(company_url: str) -> Dict[str, Any]:
    """
    Analyze Instagram comments for logistics complaints.

    Takes a company website URL, finds their Instagram, scrapes comments
    from the last 12 posts, uses Claude to classify logistics complaints,
    and returns a weighted risk score with evidence.

    Args:
        company_url: Company website URL (e.g., "https://armadura.com.co")

    Returns:
        Full analysis dict. Always returns, never raises exceptions.
    """
    start_time = time.time()
    warnings: List[str] = []

    # --- Step 1: Resolve Instagram ---
    print("[1/7] Resolving Instagram from website...")
    ig_result = _resolve_instagram(company_url)
    if not ig_result['success']:
        return _not_available(company_url, ig_result['reason'], start_time,
                              warnings=[ig_result.get('detail', '')])

    username = ig_result['username']
    print(f"      Found: @{username}")

    # --- Step 2: Get recent posts ---
    print(f"[2/7] Fetching last 12 posts for @{username}...")
    posts_result = get_instagram_posts(username, limit=12)

    if not posts_result['success']:
        return _not_available(company_url, 'instagram_scrape_failed', start_time,
                              instagram={'username': username, 'url': f'https://instagram.com/{username}'},
                              warnings=[posts_result['error']])

    posts_data = posts_result['data']

    if posts_data.get('is_private'):
        return _not_available(company_url, 'private_account', start_time,
                              instagram={'username': username, 'url': f'https://instagram.com/{username}',
                                         'followers': posts_data.get('followers'), 'is_private': True})

    posts = posts_data.get('posts', [])
    if not posts:
        return _not_available(company_url, 'no_posts', start_time,
                              instagram={'username': username, 'url': f'https://instagram.com/{username}',
                                         'followers': posts_data.get('followers'), 'is_private': False})

    if len(posts) < 12:
        warnings.append(f"Only {len(posts)} posts available (requested 12)")

    print(f"      Got {len(posts)} posts")

    # --- Step 3: Scrape comments ---
    post_urls = [p['url'] for p in posts]
    print(f"[3/7] Scraping comments from {len(post_urls)} posts...")
    comments_result = get_comments_for_posts(post_urls, results_limit_per_post=50)

    if not comments_result['success']:
        return _not_available(company_url, 'comment_scrape_failed', start_time,
                              instagram={'username': username, 'url': f'https://instagram.com/{username}',
                                         'followers': posts_data.get('followers'), 'is_private': False},
                              warnings=[comments_result['error']])

    all_comments = comments_result['data']['comments']
    total_scraped = len(all_comments)

    if total_scraped == 0:
        return _not_available(company_url, 'no_comments', start_time,
                              instagram={'username': username, 'url': f'https://instagram.com/{username}',
                                         'followers': posts_data.get('followers'), 'is_private': False})

    print(f"      Scraped {total_scraped} comments")

    # --- Step 4: Filter brand replies ---
    print(f"[4/7] Filtering out brand replies (@{username})...")
    filtered_comments = _filter_brand_replies(all_comments, username)
    brand_replies_excluded = total_scraped - len(filtered_comments)
    print(f"      Excluded {brand_replies_excluded} brand replies, {len(filtered_comments)} remaining")

    if len(filtered_comments) == 0:
        return _build_output(
            company_url=company_url,
            instagram={'username': username, 'url': f'https://instagram.com/{username}',
                       'followers': posts_data.get('followers'), 'is_private': False},
            analysis={
                'risk_score': 0, 'risk_level': 'none',
                'summary': 'Todos los comentarios son respuestas de la marca. No hay comentarios de usuarios para analizar.',
                'posts_analyzed': len(posts), 'total_comments_scraped': total_scraped,
                'brand_replies_excluded': brand_replies_excluded, 'comments_analyzed': 0,
                'complaints_found': 0, 'complaint_rate_pct': 0,
                'category_breakdown': {cat: {'count': 0, 'avg_severity': None} for cat in COMPLAINT_CATEGORIES},
                'top_flagged_comments': [],
                'recency_trend': {'recent_6_posts_complaint_rate': 0, 'older_6_posts_complaint_rate': 0, 'trend': 'stable'}
            },
            start_time=start_time,
            warnings=warnings + ['All comments were brand replies'],
            claude_tokens=0,
        )

    # --- Step 5: Claude classification ---
    print(f"[5/7] Classifying {len(filtered_comments)} comments with Claude...")
    claude_result = _classify_comments_with_claude(filtered_comments, username, company_url)

    if not claude_result['success']:
        return {
            'success': False,
            'status': 'error',
            'company_url': company_url,
            'instagram': {'username': username, 'url': f'https://instagram.com/{username}',
                          'followers': posts_data.get('followers'), 'is_private': False},
            'analysis': None,
            'metadata': _build_metadata(start_time, warnings=[claude_result['error']]),
            'error': claude_result['error']
        }

    flagged = claude_result['data']['flagged_comments']
    summary = claude_result['data']['summary']
    claude_tokens = claude_result['data'].get('tokens_used', 0)
    print(f"      Found {len(flagged)} logistics complaints")

    # --- Step 6: Compute risk score ---
    print("[6/7] Computing risk score...")
    # Enrich flagged comments with postUrl from original comments for recency weighting
    comments_by_id = {c['id']: c for c in filtered_comments}
    for fc in flagged:
        original = comments_by_id.get(fc['comment_id'], {})
        fc['_postUrl'] = original.get('postUrl', '')
    score_result = _compute_risk_score(flagged, len(filtered_comments), posts)
    print(f"      Risk score: {score_result['risk_score']} ({score_result['risk_level']})")

    # --- Step 7: Build output ---
    print("[7/7] Building output...")

    # Build category breakdown
    category_breakdown = {}
    for cat in COMPLAINT_CATEGORIES:
        cat_comments = [f for f in flagged if f['category'] == cat]
        if cat_comments:
            severities = [c['severity'] for c in cat_comments]
            # Most common severity
            avg_sev = max(set(severities), key=severities.count)
        else:
            avg_sev = None
        category_breakdown[cat] = {'count': len(cat_comments), 'avg_severity': avg_sev}

    # Build top flagged comments (enriched with full text + weighted score)
    top_flagged = []
    for fc in flagged:
        original = comments_by_id.get(fc['comment_id'], {})
        post_url = original.get('postUrl', '')
        post_rank = _get_post_rank(post_url, posts)
        recency_weight = math.exp(-0.1 * (post_rank - 1))
        severity_weight = SEVERITY_WEIGHTS.get(fc['severity'], 1.0)
        weighted = round(severity_weight * recency_weight, 2)

        top_flagged.append({
            'comment_id': fc['comment_id'],
            'text': original.get('text', fc['excerpt']),
            'category': fc['category'],
            'severity': fc['severity'],
            'owner': f"@{original.get('ownerUsername', '?')}",
            'timestamp': original.get('timestamp', ''),
            'likes': original.get('likesCount', 0),
            'post_url': post_url,
            'weighted_score': weighted,
        })

    # Sort by weighted score descending, take top 10
    top_flagged.sort(key=lambda x: x['weighted_score'], reverse=True)
    top_flagged = top_flagged[:10]

    complaint_rate = round(len(flagged) / len(filtered_comments) * 100, 2) if filtered_comments else 0

    analysis = {
        'risk_score': score_result['risk_score'],
        'risk_level': score_result['risk_level'],
        'summary': summary,
        'posts_analyzed': len(posts),
        'total_comments_scraped': total_scraped,
        'brand_replies_excluded': brand_replies_excluded,
        'comments_analyzed': len(filtered_comments),
        'complaints_found': len(flagged),
        'complaint_rate_pct': complaint_rate,
        'category_breakdown': category_breakdown,
        'top_flagged_comments': top_flagged,
        'recency_trend': score_result['recency_trend'],
    }

    return _build_output(
        company_url=company_url,
        instagram={'username': username, 'url': f'https://instagram.com/{username}',
                   'followers': posts_data.get('followers'), 'is_private': False},
        analysis=analysis,
        start_time=start_time,
        warnings=warnings,
        claude_tokens=claude_tokens,
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------
def _resolve_instagram(company_url: str) -> Dict[str, Any]:
    """Extract Instagram username from a company's website (+ Serper fallback).

    Bug fixes applied:
    - Detects when company_url is already an Instagram URL and extracts username directly
    - Serper fallback validates that the found username is related to the brand/domain
    """
    from urllib.parse import urlparse

    # --- Fix 1: If the URL is already an Instagram URL, extract directly ---
    parsed = urlparse(company_url)
    if parsed.netloc and 'instagram.com' in parsed.netloc:
        username = extract_instagram_username(company_url)
        if username:
            return {'success': True, 'username': username}
        return {'success': False, 'reason': 'no_instagram_found',
                'detail': f'Could not parse username from IG URL: {company_url}'}

    try:
        from core.url_normalizer import normalize_url
        normalized = normalize_url(company_url)
        url_to_scrape = normalized.get('data', {}).get('clean_url', company_url)
    except Exception:
        url_to_scrape = company_url

    # Extract social links (this scrapes the website internally)
    social_result = extract_social_links(url_to_scrape)

    ig_url = None
    if social_result['success'] and social_result['data'].get('instagram'):
        ig_url = social_result['data']['instagram']

    # --- Fix 3: Cross-check IG username against domain ---
    # If the website links to an IG that doesn't match the brand, try Serper
    domain = urlparse(url_to_scrape).netloc or url_to_scrape
    domain = domain.replace('www.', '')
    brand_core = domain.split('.')[0].lower()

    if ig_url and len(brand_core) >= 3:
        found_username = extract_instagram_username(ig_url) or ''
        username_clean = re.sub(r'[^a-z0-9]', '', found_username.lower())
        if brand_core not in username_clean and username_clean not in brand_core:
            # IG from website doesn't match brand — try Serper for a better match
            serper_url = search_instagram_via_serper(domain, domain=domain)
            if serper_url:
                ig_url = serper_url  # Serper already validates brand match

    # Serper fallback (if no IG found at all)
    if not ig_url:
        ig_url = search_instagram_via_serper(domain, domain=domain)

    if not ig_url:
        return {'success': False, 'reason': 'no_instagram_found',
                'detail': f'No Instagram found for {company_url} (HTML + Serper)'}

    username = extract_instagram_username(ig_url)
    if not username:
        return {'success': False, 'reason': 'no_instagram_found',
                'detail': f'Could not parse username from: {ig_url}'}

    return {'success': True, 'username': username}


def _filter_brand_replies(comments: List[dict], brand_username: str) -> List[dict]:
    """Remove comments posted by the brand's own account."""
    brand_lower = brand_username.lower()
    return [c for c in comments if c.get('ownerUsername', '').lower() != brand_lower]


def _classify_comments_with_claude(
    comments: List[dict],
    username: str,
    company_url: str,
) -> Dict[str, Any]:
    """Send all comments to Claude for logistics complaint classification."""
    api_key = os.getenv('ANTHROPIC_API_KEY')
    if not api_key:
        return {'success': False, 'data': {}, 'error': 'ANTHROPIC_API_KEY not set in environment'}

    try:
        import anthropic
    except ImportError:
        return {'success': False, 'data': {}, 'error': 'anthropic package not installed (pip install anthropic)'}

    # Build user message
    parts = [f"Company: @{username} ({company_url})"]
    parts.append(f"Total comments to analyze: {len(comments)}")
    parts.append("")

    for comment in comments:
        parts.append(
            f"[id={comment['id']}] "
            f"[post={comment.get('postUrl', '')}] "
            f"[date={comment.get('timestamp', '')}] "
            f"[likes={comment.get('likesCount', 0)}] "
            f"@{comment.get('ownerUsername', '?')}: {comment.get('text', '')}"
        )

    user_message = "\n".join(parts)

    try:
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model=MODEL,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            tools=[ANALYSIS_TOOL],
            tool_choice={"type": "tool", "name": "analyze_logistics_complaints"},
            messages=[{"role": "user", "content": user_message}],
        )

        # Extract tool_use block
        for block in response.content:
            if block.type == "tool_use" and block.name == "analyze_logistics_complaints":
                result = block.input
                flagged = result.get('flagged_comments', [])
                summary = result.get('summary', '')

                # Validate categories
                for fc in flagged:
                    if fc.get('category') not in COMPLAINT_CATEGORIES:
                        fc['category'] = 'POOR_SERVICE'  # fallback
                    if fc.get('severity') not in SEVERITY_WEIGHTS:
                        fc['severity'] = 'medium'  # fallback

                tokens_used = (response.usage.input_tokens + response.usage.output_tokens
                               if response.usage else 0)

                return {
                    'success': True,
                    'data': {
                        'flagged_comments': flagged,
                        'summary': summary,
                        'tokens_used': tokens_used,
                    },
                    'error': None
                }

        return {'success': False, 'data': {}, 'error': 'No tool_use block in Claude response'}

    except Exception as e:
        return {'success': False, 'data': {}, 'error': f'Anthropic API error: {str(e)}'}


def _compute_risk_score(
    flagged_comments: List[dict],
    total_comments: int,
    posts: List[dict],
) -> Dict[str, Any]:
    """Compute weighted logistics risk score from Claude's classifications.

    Expects flagged_comments to have a '_postUrl' field (enriched by caller).
    """
    empty_trend = {'recent_6_posts_complaint_rate': 0,
                   'older_6_posts_complaint_rate': 0, 'trend': 'stable'}

    if total_comments == 0 or not flagged_comments:
        return {'risk_score': 0, 'risk_level': 'none', 'recency_trend': empty_trend}

    # Calculate weighted complaint scores using post rank for recency
    total_weighted = 0.0
    for fc in flagged_comments:
        severity_w = SEVERITY_WEIGHTS.get(fc.get('severity', 'medium'), 2.0)
        post_url = fc.get('_postUrl', '')
        post_rank = _get_post_rank(post_url, posts)
        recency_w = math.exp(-0.1 * (post_rank - 1))
        total_weighted += severity_w * recency_w

    # Max possible: every comment is high severity on newest post
    max_possible = total_comments * 3.0 * 1.0
    raw_ratio = total_weighted / max_possible if max_possible > 0 else 0

    # Sigmoid-like scaling
    risk_score = min(100, round(100 * (1 - math.exp(-8 * raw_ratio))))

    # Risk level
    risk_level = 'critical'
    for threshold, level in RISK_LEVELS:
        if risk_score <= threshold:
            risk_level = level
            break

    # Recency trend: compare complaint rate in newest half vs oldest half of posts
    midpoint = max(len(posts) // 2, 1)
    recent_post_urls = set(p['url'] for p in posts[:midpoint])
    older_post_urls = set(p['url'] for p in posts[midpoint:])

    recent_complaints = sum(1 for fc in flagged_comments if fc.get('_postUrl', '') in recent_post_urls)
    older_complaints = sum(1 for fc in flagged_comments if fc.get('_postUrl', '') in older_post_urls)

    # Estimate comments per half (rough: split total evenly)
    recent_total = max(total_comments // 2, 1)
    older_total = max(total_comments - recent_total, 1)

    recent_rate = round(recent_complaints / recent_total * 100, 1)
    older_rate = round(older_complaints / older_total * 100, 1)

    if recent_rate > older_rate + 2:
        trend = 'worsening'
    elif older_rate > recent_rate + 2:
        trend = 'improving'
    else:
        trend = 'stable'

    recency_trend = {
        'recent_6_posts_complaint_rate': recent_rate,
        'older_6_posts_complaint_rate': older_rate,
        'trend': trend,
    }

    return {'risk_score': risk_score, 'risk_level': risk_level, 'recency_trend': recency_trend}


def _get_post_rank(post_url: str, posts: List[dict]) -> int:
    """Get 1-based rank of a post (1=newest). Returns middle rank if not found."""
    for i, p in enumerate(posts):
        if p['url'] == post_url:
            return i + 1
    return len(posts) // 2 + 1  # default to middle


def _not_available(
    company_url: str,
    reason: str,
    start_time: float,
    instagram: Optional[dict] = None,
    warnings: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Build a not_available response."""
    return {
        'success': True,
        'status': 'not_available',
        'reason': reason,
        'company_url': company_url,
        'instagram': instagram,
        'analysis': None,
        'metadata': _build_metadata(start_time, warnings=warnings or []),
        'error': None
    }


def _build_output(
    company_url: str,
    instagram: dict,
    analysis: dict,
    start_time: float,
    warnings: Optional[List[str]] = None,
    claude_tokens: int = 0,
) -> Dict[str, Any]:
    """Build the final completed response."""
    return {
        'success': True,
        'status': 'completed',
        'company_url': company_url,
        'instagram': instagram,
        'analysis': analysis,
        'metadata': _build_metadata(start_time, warnings=warnings or [], claude_tokens=claude_tokens),
        'error': None
    }


def _build_metadata(
    start_time: float,
    warnings: Optional[List[str]] = None,
    claude_tokens: int = 0,
) -> Dict[str, Any]:
    """Build metadata section."""
    elapsed = round(time.time() - start_time, 1)
    # Rough cost estimate: Apify ~$1.00 + Claude ~$0.01/1K tokens
    apify_cost = 1.00  # rough estimate for profile + comments
    claude_cost = (claude_tokens / 1000) * 0.006 if claude_tokens else 0
    return {
        'analyzed_at': datetime.utcnow().isoformat(),
        'runtime_sec': elapsed,
        'apify_cost_estimate_usd': round(apify_cost, 2),
        'claude_tokens_used': claude_tokens,
        'claude_cost_estimate_usd': round(claude_cost, 4),
        'warnings': [w for w in (warnings or []) if w],
    }


# ---------------------------------------------------------------------------
# Google Sheets output
# ---------------------------------------------------------------------------
LOGISTICS_SHEET_HEADERS = [
    "analyzed_at", "company_url", "instagram_username", "ig_followers",
    "risk_score", "risk_level", "trend", "complaints_found",
    "comments_analyzed", "complaint_rate_pct",
    "DELAY", "NON_DELIVERY", "DAMAGED", "WRONG_ITEM", "RETURN_REFUND", "POOR_SERVICE",
    "summary", "top_complaints", "runtime_sec", "warnings",
]

LOGISTICS_WORKSHEET_NAME = "logistics_complaints"


def write_to_sheet(result: Dict[str, Any], sheet_url: Optional[str] = None) -> Dict[str, Any]:
    """
    Write a logistics analysis result to a Google Sheet in a
    'logistics_complaints' tab.

    If sheet_url is provided, opens that spreadsheet. Otherwise falls back to
    SHEET_V2_URL env var. If neither is set, creates a new spreadsheet.

    Returns:
        {success: bool, sheet_url: str or None, error: str or None}
    """
    try:
        from export.google_sheets_writer import get_gspread_client
    except ImportError:
        return {'success': False, 'sheet_url': None,
                'error': 'google_sheets_writer not importable'}

    target_url = sheet_url or os.getenv('SHEET_V2_URL', '')

    try:
        client = get_gspread_client()

        if target_url:
            spreadsheet = client.open_by_url(target_url)
        else:
            # Create a new spreadsheet
            spreadsheet = client.create("Logistics Complaints Analysis")
            spreadsheet.share("", perm_type="anyone", role="reader")

        # Get or create the logistics_complaints tab
        try:
            worksheet = spreadsheet.worksheet(LOGISTICS_WORKSHEET_NAME)
        except Exception:
            worksheet = spreadsheet.add_worksheet(
                title=LOGISTICS_WORKSHEET_NAME, rows=1000,
                cols=len(LOGISTICS_SHEET_HEADERS)
            )

        # Write headers if first row is empty
        first_row = worksheet.row_values(1)
        if not first_row:
            worksheet.append_row(LOGISTICS_SHEET_HEADERS, value_input_option="USER_ENTERED")

        # Build row from result
        row = _result_to_row(result)
        worksheet.append_row(row, value_input_option="USER_ENTERED")

        return {'success': True, 'sheet_url': spreadsheet.url, 'error': None}

    except Exception as e:
        return {'success': False, 'sheet_url': None,
                'error': f'Google Sheets error: {str(e)}'}


def _result_to_row(result: Dict[str, Any]) -> list:
    """Convert a logistics analysis result dict to a flat row matching LOGISTICS_SHEET_HEADERS."""
    analysis = result.get('analysis') or {}
    metadata = result.get('metadata') or {}
    instagram = result.get('instagram') or {}
    breakdown = analysis.get('category_breakdown') or {}
    trend_data = analysis.get('recency_trend') or {}

    # Format top complaints as condensed text
    top_complaints_text = ""
    for fc in (analysis.get('top_flagged_comments') or [])[:5]:
        top_complaints_text += f"[{fc.get('category','?')}/{fc.get('severity','?')}] {fc.get('owner','?')}: {fc.get('text','')[:100]}\n"

    def fmt(val):
        return val if val is not None else ""

    return [
        fmt(metadata.get('analyzed_at', '')),
        fmt(result.get('company_url', '')),
        fmt(instagram.get('username', '')),
        fmt(instagram.get('followers')),
        fmt(analysis.get('risk_score')),
        fmt(analysis.get('risk_level', '')),
        fmt(trend_data.get('trend', '')),
        fmt(analysis.get('complaints_found')),
        fmt(analysis.get('comments_analyzed')),
        fmt(analysis.get('complaint_rate_pct')),
        # Category counts
        breakdown.get('DELAY', {}).get('count', 0),
        breakdown.get('NON_DELIVERY', {}).get('count', 0),
        breakdown.get('DAMAGED', {}).get('count', 0),
        breakdown.get('WRONG_ITEM', {}).get('count', 0),
        breakdown.get('RETURN_REFUND', {}).get('count', 0),
        breakdown.get('POOR_SERVICE', {}).get('count', 0),
        # Text fields
        fmt(analysis.get('summary', '')),
        top_complaints_text.strip(),
        fmt(metadata.get('runtime_sec')),
        "; ".join(metadata.get('warnings', [])) if metadata.get('warnings') else "",
    ]


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------
if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description="Analyze Instagram comments for logistics complaints")
    parser.add_argument("company_url", help="Company website URL")
    parser.add_argument("--sheet", help="Google Sheet URL to write results to (creates 'logistics_complaints' tab)")
    parser.add_argument("--no-sheet", action="store_true", help="Skip writing to Google Sheet")
    args = parser.parse_args()

    print(f"Instagram Logistics Complaint Analysis")
    print(f"=" * 60)
    print(f"Company URL: {args.company_url}\n")

    result = analyze_logistics_complaints(args.company_url)

    print(f"\n{'=' * 60}")
    print(json.dumps(result, indent=2, ensure_ascii=False))

    # Write to Google Sheet if analysis completed
    if result.get('status') == 'completed' and not args.no_sheet:
        print(f"\nWriting results to Google Sheet...")
        sheet_result = write_to_sheet(result, sheet_url=args.sheet)
        if sheet_result['success']:
            print(f"Saved to: {sheet_result['sheet_url']}")
        else:
            print(f"Sheet write failed: {sheet_result['error']}")
