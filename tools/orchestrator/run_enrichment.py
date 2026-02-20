"""
Single Company Enrichment Orchestrator

Purpose: Run the full enrichment pipeline for one URL, returning EnrichmentResult.
Inputs: raw_url (str), batch_id (str, optional)
Outputs: EnrichmentResult dataclass instance (never raises)
Dependencies: All tools in tools/, models/enrichment_result.py
"""

import os
import sys
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
from detection.detect_fulfillment_provider import detect_fulfillment_from_html
from social.extract_social_links import extract_social_links_from_html, search_instagram_via_serper
from social.apify_instagram import get_instagram_metrics, extract_instagram_username
from ecommerce.scrape_product_catalog import scrape_product_catalog
from traffic.estimate_traffic import estimate_traffic_from_html
from scoring.instagram_scoring import calculate_ig_size_score, calculate_ig_health_score
from ai.classify_category import classify_category
from google_demand.score_demand import score_google_demand
from contacts.apollo_enrichment import apollo_enrich

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


def run_enrichment(
    raw_url: str,
    batch_id: Optional[str] = None,
    skip_apollo: bool = True,
    skip_playwright: bool = True,
    enable_google_demand: bool = True,
    country: Optional[str] = None,
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
        cache_hit = cache_get(domain, "web_scraper") if domain else None
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
            cached = cache_get(domain, "detect_platform") if domain else None
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
    if html:
        tools_attempted += 1
        t0 = time.time()
        try:
            cached = cache_get(domain, "detect_geography") if domain else None
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
    if html:
        tools_attempted += 1
        t0 = time.time()
        try:
            cached = cache_get(domain, "social_links") if domain else None
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
            if instagram_url:
                result.instagram_url = instagram_url
                platforms_found = [k for k, v in social_data.items() if v]
                _step("social_links", "ok", ms, f"IG found + {len(platforms_found)} platforms")
                tools_succeeded += 1
            else:
                _step("social_links", "warn", ms, "no Instagram in HTML, trying Serper...")
                # Fallback: search for Instagram via Serper
                t0_serper = time.time()
                try:
                    brand_name = meta_info.get("meta_title") or (_extract_brand_name(domain) if domain else None)
                    if brand_name or domain:
                        ig_from_serper = search_instagram_via_serper(brand_name or "", domain=domain)
                        ms_serper = int((time.time() - t0_serper) * 1000)
                        if ig_from_serper:
                            instagram_url = ig_from_serper
                            result.instagram_url = instagram_url
                            _step("social_links_serper", "ok", ms_serper, f"IG found via Serper: {ig_from_serper}")
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
            cached = cache_get(domain, "apify_instagram") if domain else None
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
                        cache_set(domain, "apify_instagram", insta_data)
                else:
                    insta_data = {}
                    ms = int((time.time() - t0) * 1000)

            if insta_data.get("followers") is not None:
                instagram_data = insta_data
                result.ig_followers = insta_data.get("followers")
                result.ig_engagement_rate = insta_data.get("engagement_rate")
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
                      f"size={result.ig_size_score} health={result.ig_health_score}")
                tools_succeeded += 1
            else:
                _step("instagram", "warn", ms, "no follower data")
        except Exception as e:
            ms = int((time.time() - t0) * 1000)
            _step("instagram", "fail", ms, str(e))

    # ===== STEP 7: Product catalog =====
    tools_attempted += 1
    t0 = time.time()
    try:
        cached = cache_get(domain, "product_catalog") if domain else None
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
            cached = cache_get(domain, "traffic") if domain else None
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
            cached = cache_get(domain, "google_demand") if domain else None
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

    # ===== STEP 10: Fulfillment (passive only) =====
    if html:
        tools_attempted += 1
        t0 = time.time()
        try:
            cached = cache_get(domain, "fulfillment") if domain else None
            if cached and cached.get("success"):
                fd = cached["data"]
                ms = int((time.time() - t0) * 1000)
            else:
                ff_result = detect_fulfillment_from_html(html, result.clean_url)
                ms = int((time.time() - t0) * 1000)
                fd = ff_result.get("data", {}) if ff_result.get("success") else {}
                if domain and fd:
                    cache_set(domain, "fulfillment", fd)

            if fd.get("primary_provider"):
                result.fulfillment_provider = fd["primary_provider"]
                result.fulfillment_confidence = fd.get("confidence", 0)
                _step("fulfillment", "ok", ms, fd["primary_provider"])
                tools_succeeded += 1
            else:
                _step("fulfillment", "warn", ms, "no provider detected")
        except Exception as e:
            ms = int((time.time() - t0) * 1000)
            _step("fulfillment", "fail", ms, str(e))

    # ===== STEP 11: Category classification (LLM) =====
    tools_attempted += 1
    t0 = time.time()
    try:
        cached = cache_get(domain, "classify_category") if domain else None
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
                # Best contact (first with email)
                contacts = ap_data.get("contacts", [])
                for c in contacts:
                    if c.get("email"):
                        result.contact_name = c.get("name", "")
                        result.contact_email = c.get("email", "")
                        break
                _step("apollo", "ok", ms, f"{len(contacts)} contacts, linkedin={'yes' if result.company_linkedin else 'no'}")
                tools_succeeded += 1
            else:
                err = apollo_result.get("error", "no data")
                _step("apollo", "warn", ms, err)
        except Exception as e:
            ms = int((time.time() - t0) * 1000)
            _step("apollo", "fail", ms, str(e))

    # ===== FINALIZE =====
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
    print(f"  Coverage:   {r.tool_coverage_pct}")
    print(f"  Runtime:    {r.total_runtime_sec}s")
    print(f"  Cost:       ${r.cost_estimate_usd}")

    # Print workflow log
    log = json.loads(r.workflow_execution_log)
    print(f"\nWorkflow log ({len(log)} steps):")
    for s in log:
        print(f"  {s['step']:20s} {s['status']:5s} {s['duration_ms']:6d}ms  {s.get('detail', '')}")
