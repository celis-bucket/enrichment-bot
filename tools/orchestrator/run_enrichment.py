"""
Single Company Enrichment Orchestrator

Purpose: Run the full enrichment pipeline for one URL, returning EnrichmentResult.
Inputs: raw_url (str), batch_id (str, optional)
Outputs: EnrichmentResult dataclass instance (never raises)
Dependencies: All tools in tools/, models/enrichment_result.py
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

from models.enrichment_result import EnrichmentResult, ALLOWED_CATEGORIES
from core.url_normalizer import normalize_url, extract_domain
from core.web_scraper import scrape_website
from core.resolve_brand_url import resolve_brand_url
from core.cache_manager import cache_get, cache_set
from detection.detect_ecommerce_platform import detect_platform_from_html
from detection.detect_geography import detect_geography_from_html
from social.extract_social_links import extract_social_links_from_html, search_instagram_via_serper, search_facebook_via_serper
from social.apify_instagram import get_instagram_metrics, extract_instagram_username
from social.apify_meta_ads import get_meta_ads_count, get_meta_ads_multi_search, searchapi_facebook_page
from social.searchapi_tiktok_ads import get_tiktok_ads_multi_search
from ecommerce.scrape_product_catalog import scrape_product_catalog
from traffic.estimate_traffic import estimate_traffic_from_html
from scoring.instagram_scoring import calculate_ig_size_score, calculate_ig_health_score
from ai.classify_category import classify_category
from google_demand.score_demand import score_google_demand
from contacts.apollo_enrichment import apollo_enrich
from hubspot.hubspot_lookup import hubspot_enrich

COST_PER_COMPANY_USD = 0.05


def _extract_meta_from_html(html: str) -> Dict[str, Optional[str]]:
    """Extract meta title, description, and H1 from HTML."""
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")

        meta_title = None
        title_tag = soup.find("title")
        if title_tag and title_tag.string:
            meta_title = title_tag.string.strip()[:200]

        meta_description = None
        desc_tag = soup.find("meta", attrs={"name": "description"})
        if desc_tag and desc_tag.get("content"):
            meta_description = desc_tag["content"].strip()[:300]

        h1_text = None
        h1_tag = soup.find("h1")
        if h1_tag:
            h1_text = h1_tag.get_text(strip=True)[:200]

        return {
            "meta_title": meta_title,
            "meta_description": meta_description,
            "h1_text": h1_text,
        }
    except Exception:
        return {"meta_title": None, "meta_description": None, "h1_text": None}


def _extract_brand_name(domain: str) -> str:
    """Extract likely brand name from domain (e.g., 'armatura.com.co' -> 'armatura')."""
    parts = domain.split(".")
    name = parts[0]
    if name == "www" and len(parts) > 1:
        name = parts[1]
    return name


def _extract_brand_from_meta_title(meta_title: str, domain: str) -> Optional[str]:
    """Extract clean brand name from meta title by splitting on common delimiters.

    Examples:
        "ONE HALF | Women's Clothes Made in Colombia" -> "ONE HALF"
        "Shop Women's Clothing - One Half" -> "One Half"
        "Armatura" -> "Armatura"
    """
    if not meta_title:
        return _extract_brand_name(domain) if domain else None

    segments = re.split(r'\s*[|·–—]\s*|\s+-\s+', meta_title)
    segments = [s.strip() for s in segments if s.strip()]
    if not segments:
        return _extract_brand_name(domain) if domain else None

    generic_re = re.compile(r'^(?:Welcome to|Shop|Buy|Official|Home)\s+', re.IGNORECASE)
    candidate = generic_re.sub('', segments[0]).strip()

    # If first segment is too long, try last segment (brand sometimes at end)
    if len(candidate) > 40 and len(segments) > 1:
        last = generic_re.sub('', segments[-1]).strip()
        if 2 <= len(last) <= 40:
            candidate = last

    if 2 <= len(candidate) <= 40:
        return candidate
    return _extract_brand_name(domain) if domain else None


def run_enrichment(
    raw_url: str,
    batch_id: Optional[str] = None,
    skip_apollo: bool = False,
    skip_hubspot: bool = False,
    skip_playwright: bool = True,
    enable_google_demand: bool = True,
    country: Optional[str] = None,
    skip_cache: bool = False,
    on_step: Optional[Callable[[str, str, int, str], None]] = None,
) -> EnrichmentResult:
    """
    Run the full enrichment pipeline for a single URL.

    NEVER raises exceptions. Returns an EnrichmentResult with whatever data
    could be collected. Missing fields stay None.

    Args:
        raw_url: Raw URL or brand name
        batch_id: Shared batch identifier (optional)
        skip_apollo: If True, skip Apollo enrichment (default: True)
        skip_playwright: If True, use passive fulfillment only (default: True)
        enable_google_demand: If True, run Google Demand scoring (default: True)

    Returns:
        EnrichmentResult dataclass instance
    """
    result = EnrichmentResult(batch_id=batch_id)
    steps: List[Dict[str, Any]] = []
    start_time = time.time()
    tools_attempted = 0
    tools_succeeded = 0

    # If geography was explicitly provided (from API), lock it in
    COUNTRY_CODES = {"COL", "MEX"}
    if country and country.upper() in COUNTRY_CODES:
        result.geography = country.upper()
        result.geography_confidence = 1.0

    # Intermediate data shared between steps
    html = None
    headers = {}
    domain = None
    instagram_data = None
    catalog_data = None
    meta_info = {}

    def _step(name: str, status: str, duration_ms: int, detail: str = ""):
        steps.append({
            "step": name,
            "status": status,
            "duration_ms": duration_ms,
            "detail": detail,
        })
        if on_step:
            try:
                on_step(name, status, duration_ms, detail)
            except Exception:
                pass  # never let callback errors break the pipeline

    # ===== STEP 0: Resolve brand URL =====
    t0 = time.time()
    try:
        resolve_result = resolve_brand_url(raw_url, country=country)
        ms = int((time.time() - t0) * 1000)
        if not resolve_result["success"]:
            _step("resolve", "fail", ms, resolve_result.get("error", ""))
            result.workflow_execution_log = json.dumps(steps)
            result.total_runtime_sec = round(time.time() - start_time, 2)
            result.tool_coverage_pct = 0.0
            result.cost_estimate_usd = COST_PER_COMPANY_USD
            return result
        resolved_url = resolve_result["data"]["url"]
        was_searched = resolve_result["data"].get("was_searched", False)
        _step("resolve", "ok", ms, f"{'searched' if was_searched else 'direct'}: {resolved_url}")
    except Exception as e:
        ms = int((time.time() - t0) * 1000)
        _step("resolve", "fail", ms, str(e))
        result.workflow_execution_log = json.dumps(steps)
        result.total_runtime_sec = round(time.time() - start_time, 2)
        result.tool_coverage_pct = 0.0
        result.cost_estimate_usd = COST_PER_COMPANY_USD
        return result

    # ===== STEP 1: Normalize URL =====
    t0 = time.time()
    try:
        norm_result = normalize_url(resolved_url)
        ms = int((time.time() - t0) * 1000)
        if norm_result["success"]:
            result.clean_url = norm_result["data"]["url"]
            domain = extract_domain(result.clean_url)
            result.domain = domain
            _step("normalize", "ok", ms, result.clean_url)
        else:
            # Use resolved URL as fallback
            result.clean_url = resolved_url
            domain = resolved_url.replace("https://", "").replace("http://", "").split("/")[0].lower()
            result.domain = domain
            _step("normalize", "warn", ms, norm_result.get("error", ""))
    except Exception as e:
        ms = int((time.time() - t0) * 1000)
        result.clean_url = resolved_url
        domain = resolved_url.replace("https://", "").replace("http://", "").split("/")[0].lower()
        result.domain = domain
        _step("normalize", "warn", ms, str(e))

    # ===== STEP 2: Scrape website =====
    tools_attempted += 1
    t0 = time.time()
    try:
        # Check cache first
        cache_hit = cache_get(domain, "web_scraper") if (domain and not skip_cache) else None
        if cache_hit and cache_hit.get("success"):
            html = cache_hit["data"].get("html", "")
            headers = cache_hit["data"].get("headers", {})
            ms = int((time.time() - t0) * 1000)
            _step("scrape", "ok", ms, f"cached, {len(html) // 1024}KB")
            tools_succeeded += 1
        else:
            scrape_result = scrape_website(result.clean_url, timeout=60)
            ms = int((time.time() - t0) * 1000)
            if scrape_result["success"]:
                html = scrape_result["data"]["html"]
                headers = scrape_result["data"].get("headers", {})
                _step("scrape", "ok", ms, f"{len(html) // 1024}KB")
                tools_succeeded += 1
                # Cache the scrape (store html truncated to 500KB for cache)
                if domain:
                    cache_set(domain, "web_scraper", {
                        "html": html[:500_000],
                        "headers": dict(headers) if headers else {},
                    })
            else:
                _step("scrape", "fail", ms, scrape_result.get("error", ""))
    except Exception as e:
        ms = int((time.time() - t0) * 1000)
        _step("scrape", "fail", ms, str(e))

    # Extract meta info from HTML (for category classification later)
    if html:
        meta_info = _extract_meta_from_html(html)

    # ===== STEP 3: Detect platform =====
    if html:
        tools_attempted += 1
        t0 = time.time()
        try:
            cached = cache_get(domain, "detect_platform") if (domain and not skip_cache) else None
            if cached and cached.get("success"):
                pd = cached["data"]
                ms = int((time.time() - t0) * 1000)
            else:
                platform_result = detect_platform_from_html(html, result.clean_url, headers)
                ms = int((time.time() - t0) * 1000)
                pd = platform_result.get("data", {}) if platform_result.get("success") else {}
                if domain and pd:
                    cache_set(domain, "detect_platform", pd)

            if pd.get("platform"):
                result.platform = pd["platform"]
                result.platform_confidence = pd.get("confidence", 0)
                _step("platform", "ok", ms, f"{pd['platform']} ({pd.get('confidence', 0):.2f})")
                tools_succeeded += 1
            else:
                _step("platform", "warn", ms, "no platform detected")
        except Exception as e:
            ms = int((time.time() - t0) * 1000)
            _step("platform", "fail", ms, str(e))

    # ===== STEP 4: Detect geography =====
    # If geography was locked by user input, skip auto-detection (just validate)
    if result.geography and result.geography_confidence == 1.0:
        _step("geography", "ok", 0, f"{result.geography} (user-provided)")
        tools_attempted += 1
        tools_succeeded += 1
    elif html:
        tools_attempted += 1
        t0 = time.time()
        try:
            cached = cache_get(domain, "detect_geography") if (domain and not skip_cache) else None
            if cached and cached.get("success"):
                gd = cached["data"]
                ms = int((time.time() - t0) * 1000)
            else:
                geo_result = detect_geography_from_html(html, result.clean_url)
                ms = int((time.time() - t0) * 1000)
                gd = geo_result.get("data", {}) if geo_result.get("success") else {}
                if domain and gd:
                    cache_set(domain, "detect_geography", gd)

            if gd.get("primary_country"):
                result.geography = gd["primary_country"]
                result.geography_confidence = gd.get("confidence", 0)
                _step("geography", "ok", ms, f"{gd['primary_country']} ({gd.get('confidence', 0):.2f})")
                tools_succeeded += 1
            else:
                result.geography = "UNKNOWN"
                _step("geography", "warn", ms, "no geography detected")
        except Exception as e:
            ms = int((time.time() - t0) * 1000)
            _step("geography", "fail", ms, str(e))

    # ===== STEP 5: Extract social links =====
    instagram_url = None
    facebook_url = None
    social_data = {}
    if html:
        tools_attempted += 1
        t0 = time.time()
        try:
            cached = cache_get(domain, "social_links") if (domain and not skip_cache) else None
            if cached and cached.get("success"):
                social_data = cached["data"]
                ms = int((time.time() - t0) * 1000)
            else:
                social_result = extract_social_links_from_html(html, result.clean_url)
                ms = int((time.time() - t0) * 1000)
                social_data = social_result.get("data", {}) if social_result.get("success") else {}
                if domain and social_data:
                    cache_set(domain, "social_links", social_data)

            instagram_url = social_data.get("instagram")
            facebook_url = social_data.get("facebook")
            if instagram_url:
                result.instagram_url = instagram_url
                platforms_found = [k for k, v in social_data.items() if v]
                _step("social_links", "ok", ms, f"IG found + {len(platforms_found)} platforms")
                tools_succeeded += 1
            else:
                _step("social_links", "warn", ms, "no Instagram in HTML, trying alternate domain...")

                # Fallback 1: Try alternate country domain (handles geo-redirect sites)
                alt_social_found = False
                if result.geography and result.geography != "UNKNOWN" and domain:
                    COUNTRY_TLDS = {
                        "COL": ".com.co", "MEX": ".com.mx", "CHL": ".cl",
                        "PER": ".com.pe", "ARG": ".com.ar", "ECU": ".com.ec",
                        "PAN": ".com.pa", "CRI": ".co.cr", "DOM": ".com.do",
                        "GTM": ".com.gt", "BOL": ".com.bo", "URY": ".com.uy",
                        "PRY": ".com.py", "SLV": ".com.sv", "HND": ".com.hn",
                    }
                    country_tld = COUNTRY_TLDS.get(result.geography)
                    if country_tld and not domain.endswith(country_tld):
                        brand_name = _extract_brand_from_meta_title(meta_info.get("meta_title"), domain)
                        domain_slug = _extract_brand_name(domain)
                        # Build candidate domains: brand name (no spaces) + TLD, then domain slug + TLD
                        candidates = []
                        if brand_name:
                            brand_slug = re.sub(r'[^a-z0-9]', '', brand_name.lower())
                            if brand_slug != domain_slug:
                                candidates.append(f"{brand_slug}{country_tld}")
                        candidates.append(f"{domain_slug}{country_tld}")

                        t0_alt = time.time()
                        for alt_domain in candidates:
                            try:
                                alt_result = scrape_website(f"https://{alt_domain}/", timeout=8, max_retries=1)
                                if alt_result["success"]:
                                    alt_social = extract_social_links_from_html(
                                        alt_result["data"]["html"], f"https://{alt_domain}/"
                                    )
                                    alt_data = alt_social.get("data", {}) if alt_social.get("success") else {}
                                    if alt_data.get("instagram") or alt_data.get("facebook") or alt_data.get("tiktok"):
                                        social_data = alt_data
                                        instagram_url = alt_data.get("instagram")
                                        facebook_url = alt_data.get("facebook")
                                        if instagram_url:
                                            result.instagram_url = instagram_url
                                        ms_alt = int((time.time() - t0_alt) * 1000)
                                        platforms_found = [k for k, v in alt_data.items() if v]
                                        _step("social_links_alt", "ok", ms_alt,
                                              f"found via {alt_domain}: {len(platforms_found)} platforms")
                                        tools_succeeded += 1
                                        alt_social_found = True
                                        break
                            except Exception:
                                pass
                        if not alt_social_found:
                            ms_alt = int((time.time() - t0_alt) * 1000)
                            _step("social_links_alt", "warn", ms_alt, "no alternate domain resolved")

                # Fallback 2: search for Instagram via Serper
                if not instagram_url:
                    t0_serper = time.time()
                    try:
                        brand_name = _extract_brand_from_meta_title(meta_info.get("meta_title"), domain)
                        if brand_name or domain:
                            ig_from_serper = search_instagram_via_serper(brand_name or "", domain=domain)
                            ms_serper = int((time.time() - t0_serper) * 1000)
                            if ig_from_serper:
                                instagram_url = ig_from_serper
                                result.instagram_url = instagram_url
                                _step("social_links_serper", "ok", ms_serper, f"IG found via Serper: {ig_from_serper}")
                                if not alt_social_found:
                                    tools_succeeded += 1
                            else:
                                _step("social_links_serper", "warn", ms_serper, f"no IG found for '{brand_name}'")
                    except Exception as e_serper:
                        ms_serper = int((time.time() - t0_serper) * 1000)
                        _step("social_links_serper", "fail", ms_serper, str(e_serper))
        except Exception as e:
            ms = int((time.time() - t0) * 1000)
            _step("social_links", "fail", ms, str(e))

    # ===== STEP 6: Instagram metrics =====
    if instagram_url:
        tools_attempted += 1
        t0 = time.time()
        try:
            cached = cache_get(domain, "searchapi_instagram") if (domain and not skip_cache) else None
            if cached and cached.get("success"):
                insta_data = cached["data"]
                ms = int((time.time() - t0) * 1000)
            else:
                username = extract_instagram_username(instagram_url)
                if username:
                    insta_result = get_instagram_metrics(username, include_posts=True, posts_limit=20)
                    ms = int((time.time() - t0) * 1000)
                    insta_data = insta_result.get("data", {}) if insta_result.get("success") else {}
                    if domain and insta_data:
                        cache_set(domain, "searchapi_instagram", insta_data)
                else:
                    insta_data = {}
                    ms = int((time.time() - t0) * 1000)

            if insta_data.get("followers") is not None:
                instagram_data = insta_data
                result.ig_followers = insta_data.get("followers")
                result.ig_engagement_rate = insta_data.get("engagement_rate")
                result.ig_is_verified = 1 if insta_data.get("is_verified") else 0
                result.ig_size_score = calculate_ig_size_score(
                    followers=insta_data.get("followers", 0),
                    posts_last_30d=insta_data.get("posts_last_30d", 0),
                    engagement_rate=insta_data.get("engagement_rate", 0),
                )
                result.ig_health_score = calculate_ig_health_score(
                    engagement_rate=insta_data.get("engagement_rate", 0),
                    posts_last_30d=insta_data.get("posts_last_30d", 0),
                    followers=insta_data.get("followers", 0),
                )
                followers_str = f"{insta_data.get('followers', 0):,}"
                _step("instagram", "ok", ms,
                      f"@{insta_data.get('username', '?')} {followers_str} followers, "
                      f"verified={result.ig_is_verified} size={result.ig_size_score} health={result.ig_health_score}")
                tools_succeeded += 1
            else:
                _step("instagram", "warn", ms, "no follower data")
        except Exception as e:
            ms = int((time.time() - t0) * 1000)
            _step("instagram", "fail", ms, str(e))

    # ===== STEP 6b: META Ads (Ad Library) =====
    # Search for Facebook page via Serper if not found in HTML
    fb_page_name = None
    if not facebook_url:
        try:
            brand_name = _extract_brand_from_meta_title(meta_info.get("meta_title"), domain)
            if brand_name or domain:
                fb_serper = search_facebook_via_serper(brand_name or "", domain=domain)
                if fb_serper:
                    facebook_url = fb_serper["url"]
                    fb_page_name = fb_serper["page_name"]
        except Exception:
            pass

    # Try SearchAPI Facebook Business Page for more reliable page name + page_id
    fb_page_id = None
    if facebook_url:
        try:
            from social.apify_meta_ads import _extract_facebook_username
            fb_username = _extract_facebook_username(facebook_url)
            if fb_username:
                fb_page_info = searchapi_facebook_page(fb_username)
                if fb_page_info:
                    if fb_page_info.get("page_name") and not fb_page_name:
                        fb_page_name = fb_page_info["page_name"]
                    if fb_page_info.get("page_id"):
                        fb_page_id = str(fb_page_info["page_id"])
        except Exception:
            pass

    # Build search terms for Meta Ad Library (multi-search strategy):
    # When page_id is available, it filters to the exact Facebook page (most accurate).
    # Without page_id, picks the lowest non-zero count to avoid keyword noise.
    ig_full_name = instagram_data.get("full_name") if instagram_data else None
    ig_username = instagram_data.get("username") if instagram_data else None
    search_terms = [fb_page_name, ig_full_name, ig_username]
    search_terms = [t for t in search_terms if t]  # filter None/empty

    if search_terms:
        tools_attempted += 1
        t0 = time.time()
        _step("meta_ads", "running", 0, f"multi-search: {search_terms}" + (f" (page_id: {fb_page_id})" if fb_page_id else ""))
        try:
            cached = cache_get(domain, "meta_ads") if (domain and not skip_cache) else None
            if cached and cached.get("success"):
                ma = cached["data"]
                ms = int((time.time() - t0) * 1000)
            else:
                # Map geography codes: COL→CO, MEX→MX
                geo_map = {"COL": "CO", "MEX": "MX"}
                ad_country = geo_map.get(result.geography, "CO")
                meta_ads_result = get_meta_ads_multi_search(search_terms, country=ad_country, facebook_page_id=fb_page_id)
                ms = int((time.time() - t0) * 1000)
                ma = meta_ads_result.get("data", {}) if meta_ads_result.get("success") else {}
                if domain and ma:
                    cache_set(domain, "meta_ads", ma)

            if ma.get("active_ads_count") is not None:
                result.meta_active_ads_count = ma["active_ads_count"]
                search_used = ma.get("search_term", "?")
                _step("meta_ads", "ok", ms, f"{ma['active_ads_count']} active ads (term: {search_used})")
                tools_succeeded += 1
            else:
                _step("meta_ads", "warn", ms, "no META ads data")
        except Exception as e:
            ms = int((time.time() - t0) * 1000)
            _step("meta_ads", "fail", ms, str(e))

    # ===== STEP 6c: Facebook & TikTok followers (SearchAPI) =====
    ig_username = instagram_data.get("username") if instagram_data else None
    brand_name_for_social = ig_username or _extract_brand_from_meta_title(meta_info.get("meta_title"), domain)

    # Extract Facebook username from the URL found in HTML (more reliable than brand search)
    fb_search_name = brand_name_for_social
    if facebook_url:
        import re as _re
        _fb_match = _re.search(r'facebook\.com/(?:p/|pages/[^/]+/)?([a-zA-Z0-9._-]+)', facebook_url)
        if _fb_match:
            fb_search_name = _fb_match.group(1)

    # Extract TikTok username from the URL found in HTML
    tiktok_url = social_data.get("tiktok") if social_data else None
    tiktok_username = brand_name_for_social
    if tiktok_url:
        import re as _re
        _tt_match = _re.search(r'tiktok\.com/@?([a-zA-Z0-9_.]+)', tiktok_url)
        if _tt_match:
            tiktok_username = _tt_match.group(1)

    if fb_search_name:
        # Facebook followers
        tools_attempted += 1
        t0 = time.time()
        try:
            cached = cache_get(domain, "searchapi_facebook") if (domain and not skip_cache) else None
            if cached and cached.get("success"):
                fb_data = cached["data"]
                ms = int((time.time() - t0) * 1000)
            else:
                fb_data = searchapi_facebook_page(fb_search_name) or {}
                ms = int((time.time() - t0) * 1000)
                if domain and fb_data:
                    cache_set(domain, "searchapi_facebook", fb_data)

            fb_followers = fb_data.get("followers")
            if isinstance(fb_followers, dict):
                fb_followers = fb_followers.get("count", 0)
            if fb_followers:
                result.fb_followers = int(fb_followers)
                _step("facebook", "ok", ms, f"{result.fb_followers} followers")
                tools_succeeded += 1
            else:
                result.fb_followers = 0
                _step("facebook", "warn", ms, f"no page found (searched: {fb_search_name})")
        except Exception as e:
            ms = int((time.time() - t0) * 1000)
            _step("facebook", "fail", ms, str(e))

    # TikTok enabled only for Mexico (not active in Colombia yet)
    _skip_tiktok = (geography != "MEX")
    if tiktok_username and not _skip_tiktok:
        # TikTok followers
        tools_attempted += 1
        t0 = time.time()
        try:
            cached = cache_get(domain, "searchapi_tiktok") if (domain and not skip_cache) else None
            if cached and cached.get("success"):
                tt_data = cached["data"]
                ms = int((time.time() - t0) * 1000)
            else:
                import requests as _requests
                _searchapi_token = os.getenv("SEARCHAPI_API_KEY", "")
                tt_data = {}
                if _searchapi_token:
                    _resp = _requests.get(
                        "https://www.searchapi.io/api/v1/search",
                        params={"engine": "tiktok_profile", "username": tiktok_username},
                        headers={"Authorization": f"Bearer {_searchapi_token}"},
                        timeout=15,
                    )
                    if _resp.status_code == 200:
                        tt_data = _resp.json().get("profile", {})
                ms = int((time.time() - t0) * 1000)
                if domain and tt_data:
                    cache_set(domain, "searchapi_tiktok", tt_data)

            if tt_data.get("followers") is not None:
                result.tiktok_followers = int(tt_data["followers"])
                _step("tiktok", "ok", ms, f"{result.tiktok_followers} followers")
                tools_succeeded += 1
            else:
                result.tiktok_followers = 0
                _step("tiktok", "warn", ms, f"no profile found (searched: {tiktok_username})")
        except Exception as e:
            ms = int((time.time() - t0) * 1000)
            _step("tiktok", "fail", ms, str(e))

    # ===== STEP 6d: TikTok Ads (SearchAPI) — disabled for Colombia =====
    tiktok_ads_search_terms = [t for t in [tiktok_username, brand_name_for_social] if t]
    if tiktok_ads_search_terms and not _skip_tiktok:
        tools_attempted += 1
        t0 = time.time()
        _step("tiktok_ads", "running", 0, f"searching: {tiktok_ads_search_terms}")
        try:
            cached = cache_get(domain, "tiktok_ads") if (domain and not skip_cache) else None
            if cached and cached.get("success"):
                ta = cached["data"]
                ms = int((time.time() - t0) * 1000)
            else:
                tiktok_ads_result = get_tiktok_ads_multi_search(tiktok_ads_search_terms)
                ms = int((time.time() - t0) * 1000)
                ta = tiktok_ads_result.get("data", {}) if tiktok_ads_result.get("success") else {}
                if domain and ta:
                    cache_set(domain, "tiktok_ads", ta)

            if ta.get("active_ads_count") is not None:
                result.tiktok_active_ads_count = ta["active_ads_count"]
                search_used = ta.get("search_term", "?")
                _step("tiktok_ads", "ok", ms, f"{ta['active_ads_count']} active ads (term: {search_used})")
                tools_succeeded += 1
            else:
                _step("tiktok_ads", "warn", ms, "no TikTok ads data")
        except Exception as e:
            ms = int((time.time() - t0) * 1000)
            _step("tiktok_ads", "fail", ms, str(e))

    # ===== STEP 7: Product catalog =====
    tools_attempted += 1
    t0 = time.time()
    try:
        cached = cache_get(domain, "product_catalog") if (domain and not skip_cache) else None
        if cached and cached.get("success"):
            cd = cached["data"]
            ms = int((time.time() - t0) * 1000)
        else:
            cat_result = scrape_product_catalog(result.clean_url, platform=result.platform)
            ms = int((time.time() - t0) * 1000)
            cd = cat_result.get("data", {}) if cat_result.get("success") else {}
            if domain and cd:
                cache_set(domain, "product_catalog", cd)

        if cd.get("product_count", 0) > 0:
            catalog_data = cd
            result.product_count = cd["product_count"]
            result.avg_price = cd.get("avg_price")
            pr = cd.get("price_range", {})
            result.price_range_min = pr.get("min")
            result.price_range_max = pr.get("max")
            result.currency = cd.get("currency")
            _step("catalog", "ok", ms, f"{cd['product_count']} products, {cd.get('currency', '?')}")
            tools_succeeded += 1
        else:
            _step("catalog", "warn", ms, "no products found")
    except Exception as e:
        ms = int((time.time() - t0) * 1000)
        _step("catalog", "fail", ms, str(e))

    # ===== STEP 8: Traffic estimation =====
    if html:
        tools_attempted += 1
        t0 = time.time()
        try:
            cached = cache_get(domain, "traffic") if (domain and not skip_cache) else None
            if cached and cached.get("success"):
                td = cached["data"]
                ms = int((time.time() - t0) * 1000)
            else:
                social_for_traffic = {}
                if result.ig_followers:
                    social_for_traffic["instagram_followers"] = result.ig_followers
                traffic_result = estimate_traffic_from_html(html, result.clean_url, social_for_traffic)
                ms = int((time.time() - t0) * 1000)
                td = traffic_result.get("data", {}) if traffic_result.get("success") else {}
                if domain and td:
                    cache_set(domain, "traffic", td)

            if td.get("estimated_monthly_visits"):
                result.estimated_monthly_visits = td["estimated_monthly_visits"]
                result.traffic_confidence = td.get("confidence", 0)
                signals = td.get("signals_used", [])
                result.signals_used = ", ".join(signals) if isinstance(signals, list) else str(signals)
                visits_str = f"{td['estimated_monthly_visits']:,}"
                _step("traffic", "ok", ms, f"{visits_str} visits/mo ({result.traffic_confidence:.2f})")
                tools_succeeded += 1
            else:
                _step("traffic", "warn", ms, "no traffic estimate")
        except Exception as e:
            ms = int((time.time() - t0) * 1000)
            _step("traffic", "fail", ms, str(e))

    # ===== STEP 9: Google Demand =====
    if enable_google_demand and domain:
        tools_attempted += 1
        t0 = time.time()
        try:
            cached = cache_get(domain, "google_demand") if (domain and not skip_cache) else None
            if cached and cached.get("success"):
                dd = cached["data"]
                ms = int((time.time() - t0) * 1000)
            else:
                brand_name = _extract_brand_name(domain)
                country_code = None
                if result.geography == "COL":
                    country_code = "co"
                elif result.geography == "MEX":
                    country_code = "mx"
                demand_result = score_google_demand(brand_name, domain, country=country_code)
                ms = int((time.time() - t0) * 1000)
                dd = demand_result.get("data", {}) if demand_result.get("success") else {}
                if domain and dd:
                    cache_set(domain, "google_demand", dd)

            if dd.get("brand_demand_score") is not None:
                result.brand_demand_score = dd["brand_demand_score"]
                result.site_serp_coverage_score = dd.get("site_serp_coverage_score")
                result.google_confidence = dd.get("google_confidence")
                _step("google_demand", "ok", ms,
                      f"brand={dd['brand_demand_score']:.2f} site={dd.get('site_serp_coverage_score', 0):.2f}")
                tools_succeeded += 1
            else:
                _step("google_demand", "warn", ms, "no demand data")
        except Exception as e:
            ms = int((time.time() - t0) * 1000)
            _step("google_demand", "fail", ms, str(e))

    # ===== STEP 10: Category classification (LLM) =====
    tools_attempted += 1
    t0 = time.time()
    try:
        cached = cache_get(domain, "classify_category") if (domain and not skip_cache) else None
        if cached and cached.get("success"):
            cat_data = cached["data"]
            ms = int((time.time() - t0) * 1000)
        else:
            # Gather product titles for LLM
            product_titles = None
            if catalog_data and catalog_data.get("sample_products"):
                product_titles = [
                    p.get("name", p.get("title", ""))
                    for p in catalog_data["sample_products"][:20]
                    if p.get("name") or p.get("title")
                ]

            # Gather IG info
            ig_bio = None
            ig_name = None
            if instagram_data:
                ig_bio = instagram_data.get("biography")
                ig_name = instagram_data.get("full_name")

            cat_result = classify_category(
                domain=domain or "",
                meta_title=meta_info.get("meta_title"),
                meta_description=meta_info.get("meta_description"),
                h1_text=meta_info.get("h1_text"),
                product_titles=product_titles,
                ig_bio=ig_bio,
                ig_name=ig_name,
            )
            ms = int((time.time() - t0) * 1000)
            cat_data = cat_result.get("data", {}) if cat_result.get("success") else {}
            if domain and cat_data.get("category"):
                cache_set(domain, "classify_category", cat_data)

        if cat_data.get("category"):
            result.category = cat_data["category"]
            result.category_confidence = cat_data.get("confidence", 0)
            result.category_evidence = cat_data.get("evidence", "")
            result.company_name = cat_data.get("company_name", "")
            _step("category", "ok", ms, f"{cat_data['category']} ({cat_data.get('confidence', 0):.2f})")
            tools_succeeded += 1
        else:
            _step("category", "warn", ms, cat_result.get("error", "no category") if 'cat_result' in dir() else "no category")
    except Exception as e:
        ms = int((time.time() - t0) * 1000)
        _step("category", "fail", ms, str(e))

    # ===== STEP 12: Apollo =====
    apollo_country = None
    if not skip_apollo:
        t0 = time.time()
        tools_attempted += 1
        try:
            apollo_result = apollo_enrich(domain)
            ms = int((time.time() - t0) * 1000)
            if apollo_result.get("success") and apollo_result.get("data", {}).get("source") != "stub":
                ap_data = apollo_result["data"]
                # Company info
                company_info = ap_data.get("company", {})
                result.company_linkedin = company_info.get("linkedin_url", "")
                result.number_employes = company_info.get("employee_count")
                result.founded_year = company_info.get("founded_year")
                apollo_country = company_info.get("country", "")
                # All contacts
                contacts = ap_data.get("contacts", [])
                result.contacts_list = [
                    {
                        "name": c.get("name", ""),
                        "title": c.get("title", ""),
                        "email": c.get("email"),
                        "linkedin_url": c.get("linkedin_url"),
                        "phone": c.get("phone"),
                    }
                    for c in contacts
                ]
                # Best contact (first with email) — kept for Sheet + backwards compat
                for c in contacts:
                    if c.get("email"):
                        result.contact_name = c.get("name", "")
                        result.contact_email = c.get("email", "")
                        break
                apollo_domain = ap_data.get("apollo_domain", domain)
                via_suffix = f" (via {apollo_domain})" if apollo_domain != domain else ""
                _step("apollo", "ok", ms, f"{len(contacts)} contacts, linkedin={'yes' if result.company_linkedin else 'no'}{via_suffix}")
                tools_succeeded += 1
            else:
                err = apollo_result.get("error", "no data")
                _step("apollo", "warn", ms, err)
        except Exception as e:
            ms = int((time.time() - t0) * 1000)
            _step("apollo", "fail", ms, str(e))

    # ===== STEP 12b: Geography reconciliation =====
    # Skip if geography was user-provided (confidence 1.0)
    if result.geography in (None, "UNKNOWN") and result.geography_confidence != 1.0:
        t0 = time.time()
        geo_resolved = None
        geo_source = ""

        COUNTRY_NORM = {
            "colombia": "COL", "col": "COL",
            "mexico": "MEX", "méxico": "MEX", "mex": "MEX",
        }

        # Signal 1: explicit country parameter
        if country and country.strip().lower() in COUNTRY_NORM:
            geo_resolved = COUNTRY_NORM[country.strip().lower()]
            geo_source = f"input param: {country}"

        # Signal 2: Apollo company country
        if not geo_resolved and apollo_country:
            norm_key = apollo_country.strip().lower()
            if norm_key in COUNTRY_NORM:
                geo_resolved = COUNTRY_NORM[norm_key]
                geo_source = f"apollo country: {apollo_country}"

        # Signal 3: catalog currency
        if not geo_resolved and result.currency:
            CURRENCY_GEO = {"COP": "COL", "MXN": "MEX"}
            if result.currency in CURRENCY_GEO:
                geo_resolved = CURRENCY_GEO[result.currency]
                geo_source = f"catalog currency: {result.currency}"

        # Signal 4: domain TLD
        if not geo_resolved and domain:
            if domain.endswith(".co") or ".co." in domain:
                geo_resolved = "COL"
                geo_source = f"domain TLD: {domain}"
            elif domain.endswith(".mx") or ".mx." in domain:
                geo_resolved = "MEX"
                geo_source = f"domain TLD: {domain}"

        ms = int((time.time() - t0) * 1000)
        if geo_resolved:
            result.geography = geo_resolved
            result.geography_confidence = 0.5
            _step("geo_reconcile", "ok", ms, geo_source)
        else:
            _step("geo_reconcile", "warn", ms, "still UNKNOWN after all signals")

    # ===== STEP 13: HubSpot CRM Lookup =====
    if not skip_hubspot and domain:
        tools_attempted += 1
        t0 = time.time()
        try:
            cached = cache_get(domain, "hubspot_lookup") if (domain and not skip_cache) else None
            if cached and cached.get("success") and cached.get("data", {}).get("company_found"):
                hs_data = cached["data"]
                ms = int((time.time() - t0) * 1000)
            else:
                hs_result = hubspot_enrich(domain, contact_email=result.contact_email)
                ms = int((time.time() - t0) * 1000)
                hs_data = hs_result.get("data", {}) if hs_result.get("success") else {}
                # Only cache positive matches — negatives should re-check each run
                if domain and hs_data and hs_data.get("company_found"):
                    cache_set(domain, "hubspot_lookup", hs_data)

            if hs_data.get("company_found"):
                result.hubspot_company_id = hs_data.get("company_id")
                result.hubspot_company_url = hs_data.get("hubspot_company_url")
                result.hubspot_deal_count = hs_data.get("deal_count", 0)
                result.hubspot_deal_stage = hs_data.get("deal_stage")
                result.hubspot_contact_exists = 1 if hs_data.get("contact_exists") else 0
                result.hubspot_lifecycle_label = hs_data.get("lifecycle_label")
                result.hubspot_last_contacted = hs_data.get("last_contacted")
                _step("hubspot", "ok", ms,
                      f"found! {hs_data.get('lifecycle_label', '?')}, "
                      f"{hs_data.get('deal_count', 0)} deals, "
                      f"stage={hs_data.get('deal_stage', 'n/a')}")
                tools_succeeded += 1
            else:
                result.hubspot_contact_exists = 1 if hs_data.get("contact_exists") else 0
                _step("hubspot", "ok", ms, "company not in HubSpot")
                tools_succeeded += 1
        except Exception as e:
            ms = int((time.time() - t0) * 1000)
            _step("hubspot", "fail", ms, str(e))

    # ===== STEP 14: Retail Channel Enrichment =====
    if domain:
        t0 = time.time()
        try:
            from retail.run_retail_enrichment import run_retail_enrichment
            from datetime import datetime, timezone

            # Gather inputs already available from earlier steps
            retail_ig_bio = instagram_data.get("biography") if instagram_data else None
            retail_ig_username = instagram_data.get("username") if instagram_data else None

            retail_result = run_retail_enrichment(
                domain=domain,
                brand_name=result.company_name or domain.split(".")[0],
                html=html,
                geography=result.geography,
                category=result.category,
                ig_bio=retail_ig_bio,
                ig_username=retail_ig_username,
                skip_cache=skip_cache,
                on_step=on_step,
            )

            if retail_result.get("success"):
                rd = retail_result["data"]
                result.has_distributors = rd.get("has_distributors")
                result.has_own_stores = rd.get("has_own_stores")
                result.own_store_count_col = rd.get("own_store_count_col")
                result.own_store_count_mex = rd.get("own_store_count_mex")
                result.has_multibrand_stores = rd.get("has_multibrand_stores")
                result.multibrand_store_names = rd.get("multibrand_store_names", [])
                result.on_mercadolibre = rd.get("on_mercadolibre")
                result.on_amazon = rd.get("on_amazon")
                result.on_rappi = rd.get("on_rappi")
                result.on_walmart = rd.get("on_walmart")
                result.on_liverpool = rd.get("on_liverpool")
                result.on_coppel = rd.get("on_coppel")
                result.marketplace_names = rd.get("marketplace_names", [])
                result.retail_confidence = rd.get("retail_confidence")
                result.retail_enriched_at = datetime.now(timezone.utc).isoformat()
        except Exception as e:
            ms = int((time.time() - t0) * 1000)
            _step("retail_enrichment", "fail", ms, str(e))

    # ===== STEP 15: Potential Scoring =====
    t0 = time.time()
    try:
        from scoring.potential_scoring import score_company
        score_input = result.to_dict()
        scores = score_company(score_input)
        result.ecommerce_size_score = scores["ecommerce_size_score"]
        result.retail_size_score = scores["retail_size_score"]
        result.combined_size_score = scores["combined_size_score"]
        result.fit_score = scores["fit_score"]
        result.overall_potential_score = scores["overall_potential_score"]
        result.potential_tier = scores["potential_tier"]
        ms = int((time.time() - t0) * 1000)
        _step("potential_scoring", "ok", ms,
              f"tier={scores['potential_tier']} overall={scores['overall_potential_score']} "
              f"size={scores['combined_size_score']} fit={scores['fit_score']}")
    except Exception as e:
        ms = int((time.time() - t0) * 1000)
        _step("potential_scoring", "fail", ms, str(e))

    # ===== FINALIZE =====
    result.enrichment_type = "full"
    result.tool_coverage_pct = round(tools_succeeded / max(tools_attempted, 1), 2)
    result.total_runtime_sec = round(time.time() - start_time, 2)
    result.cost_estimate_usd = COST_PER_COMPANY_USD
    result.workflow_execution_log = json.dumps(steps)

    return result


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run enrichment for a single URL")
    parser.add_argument("url", help="URL or brand name to enrich")
    parser.add_argument("--no-demand", action="store_true", help="Skip Google Demand scoring")
    args = parser.parse_args()

    print(f"Running enrichment for: {args.url}")
    print("=" * 60)

    r = run_enrichment(args.url, enable_google_demand=not args.no_demand)

    print(f"\nResult:")
    print(f"  URL:        {r.clean_url}")
    print(f"  Domain:     {r.domain}")
    print(f"  Platform:   {r.platform} ({r.platform_confidence})")
    print(f"  Geography:  {r.geography} ({r.geography_confidence})")
    print(f"  Category:   {r.category} ({r.category_confidence})")
    print(f"  IG:         {r.ig_followers} followers, size={r.ig_size_score}, health={r.ig_health_score}")
    print(f"  Catalog:    {r.product_count} products, avg={r.avg_price} {r.currency}")
    print(f"  Traffic:    {r.estimated_monthly_visits} visits/mo")
    print(f"  Demand:     brand={r.brand_demand_score}, site={r.site_serp_coverage_score}")
    print(f"  Fulfillment:{r.fulfillment_provider}")
    print(f"  Potential:  {r.potential_tier} (overall={r.overall_potential_score}, size={r.combined_size_score}, fit={r.fit_score})")
    print(f"  Coverage:   {r.tool_coverage_pct}")
    print(f"  Runtime:    {r.total_runtime_sec}s")
    print(f"  Cost:       ${r.cost_estimate_usd}")

    # Print workflow log
    log = json.loads(r.workflow_execution_log)
    print(f"\nWorkflow log ({len(log)} steps):")
    for s in log:
        print(f"  {s['step']:20s} {s['status']:5s} {s['duration_ms']:6d}ms  {s.get('detail', '')}")
