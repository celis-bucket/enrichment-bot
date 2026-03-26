"""
Lite Enrichment Pipeline

Purpose: Fast, cheap enrichment for triage of large lead lists.
Inputs: company_name + optional website_url + optional instagram_url
Outputs: EnrichmentResult with subset of fields + lite_triage_score
Dependencies: Core tools only (no Apollo, no catalog, no traffic, no Claude)

7 steps (~5-10s per company, ~$0.02/company):
  0. URL Resolution
  1. Quick Scrape (15s timeout)
  2. Platform Detection
  3. Social Links Extraction
  4. Instagram Profile + Scoring
  5. Google Quick Check (1 SearchAPI query)
  6. HubSpot Lookup
  7. Lite Scoring
"""

import os
import sys
import re
import time
import json
from typing import Optional, List, Dict, Any, Callable

# Allow imports from tools/ root
_TOOLS_DIR = os.path.join(os.path.dirname(__file__), "..")
if _TOOLS_DIR not in sys.path:
    sys.path.insert(0, _TOOLS_DIR)

from models.enrichment_result import EnrichmentResult
from core.url_normalizer import normalize_url, extract_domain
from core.web_scraper import scrape_website
from core.cache_manager import cache_get, cache_set
from detection.detect_ecommerce_platform import detect_platform_from_html
from detection.detect_geography import detect_geography_from_html
from social.extract_social_links import extract_social_links_from_html
from social.apify_instagram import get_instagram_metrics, extract_instagram_username
from scoring.instagram_scoring import calculate_ig_size_score, calculate_ig_health_score
from hubspot.hubspot_lookup import hubspot_enrich

import requests as _requests
from dotenv import load_dotenv as _load_dotenv
_load_dotenv()

COST_PER_COMPANY_LITE_USD = 0.02
TARGET_PLATFORMS = {"Shopify", "VTEX"}


def _searchapi_google(query: str, num_results: int = 10, country: str = "co", language: str = "es") -> Dict[str, Any]:
    """
    Google search via SearchAPI.io (replaces Serper for lite pipeline).
    Returns same format as core/google_search.py for compatibility.
    """
    api_key = os.getenv("SEARCHAPI_API_KEY")
    if not api_key:
        return {"success": False, "data": {}, "error": "SEARCHAPI_API_KEY not set"}

    try:
        resp = _requests.get(
            "https://www.searchapi.io/api/v1/search",
            params={
                "engine": "google",
                "q": query,
                "gl": country,
                "hl": language,
                "num": num_results,
                "api_key": api_key,
            },
            timeout=15,
        )

        if resp.status_code != 200:
            return {"success": False, "data": {}, "error": f"SearchAPI Google HTTP {resp.status_code}"}

        raw = resp.json()

        # Normalize to same format as core/google_search.py
        organic = [
            {
                "title": r.get("title", ""),
                "link": r.get("link", ""),
                "snippet": r.get("snippet", ""),
                "position": r.get("position"),
            }
            for r in raw.get("organic_results", [])
        ]

        return {
            "success": True,
            "data": {"organic": organic, "query": query},
            "error": None,
        }

    except Exception as e:
        return {"success": False, "data": {}, "error": f"SearchAPI Google error: {e}"}

# HubSpot deal stages that indicate already-won customer
CUSTOMER_STAGES = {
    "cierre ganado", "closedwon", "onboarding", "partnership activo",
    "closed won", "cliente", "customer",
}


def _extract_brand_name(domain: str) -> str:
    """Extract likely brand name from domain."""
    parts = domain.split(".")
    name = parts[0]
    if name == "www" and len(parts) > 1:
        name = parts[1]
    return name


def _extract_brand_from_meta_title(meta_title: str, domain: str) -> Optional[str]:
    """Extract clean brand name from meta title."""
    if not meta_title:
        return _extract_brand_name(domain) if domain else None

    segments = re.split(r'\s*[|·–—]\s*|\s+-\s+', meta_title)
    segments = [s.strip() for s in segments if s.strip()]
    if not segments:
        return _extract_brand_name(domain) if domain else None

    generic_re = re.compile(r'^(?:Welcome to|Shop|Buy|Official|Home)\s+', re.IGNORECASE)
    candidate = generic_re.sub('', segments[0]).strip()

    if len(candidate) > 40 and len(segments) > 1:
        last = generic_re.sub('', segments[-1]).strip()
        if 2 <= len(last) <= 40:
            candidate = last

    if 2 <= len(candidate) <= 40:
        return candidate
    return _extract_brand_name(domain) if domain else None


def run_enrichment_lite(
    company_name: str,
    website_url: str = "",
    instagram_url: str = "",
    batch_id: Optional[str] = None,
    country: Optional[str] = None,
    skip_cache: bool = False,
    on_step: Optional[Callable[[str, str, int, str], None]] = None,
) -> EnrichmentResult:
    """
    Run the lite enrichment pipeline for a single company.

    NEVER raises exceptions. Returns an EnrichmentResult with whatever data
    could be collected. Missing fields stay None.

    Args:
        company_name: Company or brand name
        website_url: Website URL (may be empty or broken)
        instagram_url: Instagram URL (may be empty)
        batch_id: Shared batch identifier
        country: Country context (e.g., "Colombia")
        skip_cache: Bypass cache
        on_step: Callback for progress streaming

    Returns:
        EnrichmentResult with enrichment_type="lite"
    """
    result = EnrichmentResult(batch_id=batch_id, enrichment_type="lite")
    result.company_name = company_name.strip() if company_name else None
    steps: List[Dict[str, Any]] = []
    start_time = time.time()
    tools_attempted = 0
    tools_succeeded = 0

    # Shared state between steps
    html = None
    resp_headers = {}
    domain = None
    ig_username = extract_instagram_username(instagram_url) if instagram_url else None

    def _step(name: str, status: str, duration_ms: int, detail: str = ""):
        steps.append({"step": name, "status": status, "duration_ms": duration_ms, "detail": detail})
        if on_step:
            try:
                on_step(name, status, duration_ms, detail)
            except Exception:
                pass

    # ===== STEP 0: URL Resolution =====
    t0 = time.time()
    resolved_url = None

    try:
        if website_url and website_url.strip():
            # Has website URL — normalize it
            norm = normalize_url(website_url.strip())
            if norm["success"]:
                resolved_url = norm["data"]["url"]
                domain = extract_domain(resolved_url)
                result.clean_url = resolved_url
                result.domain = domain
                ms = int((time.time() - t0) * 1000)
                _step("resolve", "ok", ms, f"direct: {resolved_url}")
            else:
                ms = int((time.time() - t0) * 1000)
                _step("resolve", "warn", ms, f"normalize failed: {norm.get('error', '')}")

        if not resolved_url and company_name and company_name.strip():
            # No website — try Google search
            t0_search = time.time()
            search_result = _searchapi_google(f'"{company_name.strip()}"', num_results=5)
            ms_search = int((time.time() - t0_search) * 1000)

            if search_result.get("success") and search_result.get("data", {}).get("organic"):
                first = search_result["data"]["organic"][0]
                found_url = first.get("link", "")
                if found_url:
                    norm = normalize_url(found_url)
                    if norm["success"]:
                        resolved_url = norm["data"]["url"]
                        domain = extract_domain(resolved_url)
                        result.clean_url = resolved_url
                        result.domain = domain
                        _step("resolve", "ok", ms_search, f"google: {resolved_url}")
                    else:
                        _step("resolve", "warn", ms_search, f"google found but normalize failed")
                else:
                    _step("resolve", "warn", ms_search, "google returned no links")
            else:
                _step("resolve", "warn", ms_search, "google search failed or empty")

        if not resolved_url and not ig_username:
            # Nothing to work with
            ms = int((time.time() - t0) * 1000)
            if not steps or steps[-1]["step"] != "resolve":
                _step("resolve", "fail", ms, "no URL, no IG, cannot resolve")
            result.enrichment_type = "lite"
            result.lite_triage_score = 0
            result.worth_full_enrichment = False
            result.workflow_execution_log = json.dumps(steps)
            result.total_runtime_sec = round(time.time() - start_time, 2)
            result.tool_coverage_pct = 0.0
            result.cost_estimate_usd = COST_PER_COMPANY_LITE_USD
            return result

    except Exception as e:
        ms = int((time.time() - t0) * 1000)
        _step("resolve", "fail", ms, str(e))

    # ===== STEP 1: Quick Scrape =====
    if resolved_url and domain:
        tools_attempted += 1
        t0 = time.time()
        try:
            cache_hit = cache_get(domain, "web_scraper") if (not skip_cache) else None
            if cache_hit and cache_hit.get("success"):
                html = cache_hit["data"].get("html", "")
                resp_headers = cache_hit["data"].get("headers", {})
                ms = int((time.time() - t0) * 1000)
                _step("scrape", "ok", ms, f"cached, {len(html) // 1024}KB")
                tools_succeeded += 1
            else:
                scrape_result = scrape_website(resolved_url, timeout=15, max_retries=1)
                ms = int((time.time() - t0) * 1000)
                if scrape_result["success"]:
                    html = scrape_result["data"].get("html", "")
                    resp_headers = scrape_result["data"].get("headers", {})
                    tools_succeeded += 1
                    _step("scrape", "ok", ms, f"{len(html) // 1024}KB")
                    # Cache the scrape
                    if not skip_cache:
                        cache_set(domain, "web_scraper", scrape_result)
                else:
                    _step("scrape", "fail", ms, scrape_result.get("error", "")[:100])
        except Exception as e:
            ms = int((time.time() - t0) * 1000)
            _step("scrape", "fail", ms, str(e)[:100])

    # ===== STEP 2: Platform Detection =====
    if html:
        tools_attempted += 1
        t0 = time.time()
        try:
            platform_result = detect_platform_from_html(html, resolved_url, resp_headers)
            ms = int((time.time() - t0) * 1000)
            if platform_result["success"]:
                result.platform = platform_result["data"].get("platform")
                result.platform_confidence = platform_result["data"].get("confidence")
                tools_succeeded += 1
                _step("platform", "ok", ms, f"{result.platform} ({result.platform_confidence:.2f})" if result.platform else "unknown")
            else:
                _step("platform", "fail", ms, platform_result.get("error", ""))
        except Exception as e:
            ms = int((time.time() - t0) * 1000)
            _step("platform", "fail", ms, str(e)[:100])

    # ===== STEP 2b: Geography Detection =====
    if html:
        t0 = time.time()
        try:
            geo_result = detect_geography_from_html(html, resolved_url or "")
            ms = int((time.time() - t0) * 1000)
            if geo_result["success"]:
                result.geography = geo_result["data"].get("geography")
                result.geography_confidence = geo_result["data"].get("confidence")
                _step("geography", "ok", ms, result.geography or "UNKNOWN")
        except Exception:
            pass  # non-critical

    # ===== STEP 3: Social Links Extraction =====
    if html:
        tools_attempted += 1
        t0 = time.time()
        try:
            social_result = extract_social_links_from_html(html, resolved_url or "")
            ms = int((time.time() - t0) * 1000)

            if social_result:
                # Extract brand name from meta title
                if html and domain:
                    try:
                        from bs4 import BeautifulSoup
                        soup = BeautifulSoup(html, "html.parser")
                        title_tag = soup.find("title")
                        if title_tag and title_tag.string:
                            meta_title = title_tag.string.strip()[:200]
                            brand = _extract_brand_from_meta_title(meta_title, domain)
                            if brand and (not result.company_name or result.company_name == _extract_brand_name(domain)):
                                result.company_name = brand
                    except Exception:
                        pass

                # IG from HTML if we don't have one yet
                ig_from_html = social_result.get("instagram")
                if ig_from_html and not ig_username:
                    ig_username = extract_instagram_username(ig_from_html)
                    result.instagram_url = ig_from_html

                tools_succeeded += 1
                found = [k for k, v in social_result.items() if v]
                _step("social_links", "ok", ms, ", ".join(found) if found else "none")
            else:
                _step("social_links", "ok", ms, "none found")
                tools_succeeded += 1
        except Exception as e:
            ms = int((time.time() - t0) * 1000)
            _step("social_links", "fail", ms, str(e)[:100])

    # ===== STEP 4: Instagram Profile =====
    if ig_username:
        tools_attempted += 1
        t0 = time.time()
        try:
            cache_key = f"ig_profile_{ig_username}"
            cache_hit = cache_get(ig_username, "instagram_profile") if (not skip_cache) else None

            if cache_hit and cache_hit.get("success"):
                ig_data = cache_hit["data"]
                ms = int((time.time() - t0) * 1000)
                _step("instagram", "ok", ms, f"cached, {ig_data.get('followers', 0):,} followers")
                tools_succeeded += 1
            else:
                ig_result = get_instagram_metrics(ig_username)
                ms = int((time.time() - t0) * 1000)
                if ig_result["success"]:
                    ig_data = ig_result["data"]
                    tools_succeeded += 1
                    _step("instagram", "ok", ms, f"{ig_data.get('followers', 0):,} followers")
                    if not skip_cache:
                        cache_set(ig_username, "instagram_profile", ig_result)
                else:
                    ig_data = None
                    _step("instagram", "fail", ms, ig_result.get("error", "")[:100])

            if ig_data:
                result.instagram_url = ig_data.get("url") or f"https://instagram.com/{ig_username}"
                result.ig_followers = ig_data.get("followers")
                result.ig_engagement_rate = ig_data.get("engagement_rate")
                result.ig_is_verified = 1 if ig_data.get("is_verified") else 0

                # Scoring
                followers = ig_data.get("followers", 0)
                posts_30d = ig_data.get("posts_last_30d", 0)
                eng_rate = ig_data.get("engagement_rate", 0.0)
                result.ig_size_score = calculate_ig_size_score(followers, posts_30d, eng_rate)
                result.ig_health_score = calculate_ig_health_score(followers, posts_30d, eng_rate)

                # Try to extract website from IG bio if we don't have a URL yet
                if not resolved_url and ig_data.get("biography"):
                    bio = ig_data["biography"]
                    url_match = re.search(r'https?://[^\s<>"]+', bio)
                    if url_match:
                        bio_url = url_match.group(0)
                        norm = normalize_url(bio_url)
                        if norm["success"]:
                            resolved_url = norm["data"]["url"]
                            domain = extract_domain(resolved_url)
                            result.clean_url = resolved_url
                            result.domain = domain

        except Exception as e:
            ms = int((time.time() - t0) * 1000)
            _step("instagram", "fail", ms, str(e)[:100])

    # ===== STEP 5: Google Quick Check (1 query) =====
    brand_name = result.company_name or (domain and _extract_brand_name(domain))
    google_found_in_top10 = False
    google_position = None

    if brand_name:
        tools_attempted += 1
        t0 = time.time()
        try:
            cache_hit = cache_get(brand_name, "google_quick_check") if (not skip_cache) else None

            if cache_hit and cache_hit.get("success"):
                gdata = cache_hit["data"]
                google_found_in_top10 = gdata.get("found_in_top10", False)
                google_position = gdata.get("position")
                ms = int((time.time() - t0) * 1000)
                _step("google_check", "ok", ms, f"cached, pos={google_position}")
                tools_succeeded += 1
            else:
                search_result = _searchapi_google(f'"{brand_name}"', num_results=10)
                ms = int((time.time() - t0) * 1000)

                if search_result.get("success") and search_result.get("data", {}).get("organic"):
                    organic = search_result["data"]["organic"]
                    # Check if our domain appears in results
                    if domain:
                        for pos, r in enumerate(organic, 1):
                            link = r.get("link", "").lower()
                            if domain.lower() in link:
                                google_found_in_top10 = True
                                google_position = pos
                                break
                    tools_succeeded += 1
                    _step("google_check", "ok", ms,
                           f"found at pos {google_position}" if google_found_in_top10 else "not in top 10")

                    # Cache result
                    if not skip_cache and brand_name:
                        cache_set(brand_name, "google_quick_check", {
                            "success": True,
                            "data": {"found_in_top10": google_found_in_top10, "position": google_position},
                        })
                else:
                    _step("google_check", "fail", ms, "search failed or empty")

        except Exception as e:
            ms = int((time.time() - t0) * 1000)
            _step("google_check", "fail", ms, str(e)[:100])

    # ===== STEP 6: HubSpot Lookup =====
    if domain:
        tools_attempted += 1
        t0 = time.time()
        try:
            hs_result = hubspot_enrich(domain)
            ms = int((time.time() - t0) * 1000)

            if hs_result.get("success") and hs_result.get("data", {}).get("company_found"):
                hs_data = hs_result["data"]
                result.hubspot_company_id = hs_data.get("company_id")
                result.hubspot_company_url = hs_data.get("hubspot_company_url")
                result.hubspot_deal_count = hs_data.get("deal_count")
                result.hubspot_deal_stage = hs_data.get("deal_stage")
                result.hubspot_lifecycle_label = hs_data.get("lifecycle_stage")
                result.hubspot_last_contacted = hs_data.get("last_contacted")
                tools_succeeded += 1
                _step("hubspot", "ok", ms, f"found, deals={hs_data.get('deal_count', 0)}, stage={hs_data.get('deal_stage', 'none')}")
            else:
                tools_succeeded += 1  # not finding is still "success" — the tool ran fine
                _step("hubspot", "ok", ms, "not found in HubSpot")

        except Exception as e:
            ms = int((time.time() - t0) * 1000)
            _step("hubspot", "fail", ms, str(e)[:100])

    # ===== STEP 7: Lite Scoring =====
    t0 = time.time()
    score = 0
    reasons = []

    # Platform signal (30 pts)
    if result.platform and result.platform in TARGET_PLATFORMS:
        score += 30
        reasons.append(f"platform:{result.platform}")
    elif not resolved_url and ig_username and result.ig_followers and result.ig_followers >= 500:
        # IG-only business (no website) — treat as "facebook_commerce"
        score += 15
        result.platform = "facebook_commerce"
        reasons.append("facebook_commerce")

    # Instagram signal (30 pts)
    if result.ig_followers:
        if result.ig_followers >= 5000:
            score += 30
            reasons.append(f"ig:{result.ig_followers:,}")
        elif result.ig_followers >= 1000:
            score += 15
            reasons.append(f"ig:{result.ig_followers:,}")

    # Google presence (20 pts)
    if google_found_in_top10:
        score += 20
        reasons.append(f"google_top10:pos{google_position}")

    # URL resolved (10 pts)
    if result.clean_url:
        score += 10
        reasons.append("url_ok")

    # Geography bonus (10 pts)
    if result.geography and result.geography in ("COL", "MEX"):
        score += 10
        reasons.append(f"geo:{result.geography}")

    # HubSpot penalty (already customer)
    if result.hubspot_deal_stage and result.hubspot_deal_stage.lower() in CUSTOMER_STAGES:
        score -= 50
        reasons.append("already_customer")

    # Clamp score
    score = max(0, min(100, score))

    result.lite_triage_score = score
    result.worth_full_enrichment = score >= 40

    ms = int((time.time() - t0) * 1000)
    _step("lite_scoring", "ok", ms, f"score={score}, enrich={result.worth_full_enrichment}, reasons={','.join(reasons)}")

    # ===== Finalize =====
    result.tool_coverage_pct = round(tools_succeeded / max(tools_attempted, 1), 2)
    result.total_runtime_sec = round(time.time() - start_time, 2)
    result.cost_estimate_usd = COST_PER_COMPANY_LITE_USD
    result.workflow_execution_log = json.dumps(steps)

    return result


if __name__ == "__main__":
    import sys

    name = sys.argv[1] if len(sys.argv) > 1 else "Test Brand"
    url = sys.argv[2] if len(sys.argv) > 2 else ""
    ig = sys.argv[3] if len(sys.argv) > 3 else ""

    print("Lite Enrichment Test")
    print("=" * 60)
    print(f"Name: {name}")
    print(f"URL:  {url}")
    print(f"IG:   {ig}")
    print()

    def on_step(name, status, ms, detail):
        print(f"  [{status.upper():4s}] {name}: {detail} ({ms}ms)")

    r = run_enrichment_lite(name, website_url=url, instagram_url=ig, on_step=on_step)
    print()
    print(f"Domain:     {r.domain}")
    print(f"Platform:   {r.platform}")
    print(f"Geography:  {r.geography}")
    print(f"IG:         @{extract_instagram_username(r.instagram_url) if r.instagram_url else 'none'} ({r.ig_followers or 0:,} followers)")
    print(f"HubSpot:    {r.hubspot_deal_stage or 'not found'}")
    print(f"Score:      {r.lite_triage_score}/100")
    print(f"Enrich?     {'YES' if r.worth_full_enrichment else 'NO'}")
    print(f"Time:       {r.total_runtime_sec}s")
