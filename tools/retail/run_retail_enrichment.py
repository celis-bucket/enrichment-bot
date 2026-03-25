"""
Retail Channel Enrichment Orchestrator

Purpose: Detect physical/retail channel presence for a brand across 4 channels + 3 signals
Inputs: domain (str), brand_name (str), optional HTML/geography/IG bio/knowledge graph
Outputs: Retail channel data → Supabase upsert on enriched_companies

Can run standalone or be called from the main enrichment pipeline.

Usage:
    # Single domain
    python -m tools.retail.run_retail_enrichment "armatura.com.co"

    # Batch (all domains where retail_enriched_at IS NULL)
    python -m tools.retail.run_retail_enrichment --batch

    # Programmatic
    from retail.run_retail_enrichment import run_retail_enrichment
    result = run_retail_enrichment("armatura.com.co", "Armatura", html=html, geography="COL")
"""

import os
import sys
import time
import json
import argparse
from typing import Optional, Dict, Any, Callable, List
from datetime import datetime, timezone

# Allow imports from tools/ root
_TOOLS_DIR = os.path.join(os.path.dirname(__file__), "..")
if _TOOLS_DIR not in sys.path:
    sys.path.insert(0, _TOOLS_DIR)

from core.web_scraper import scrape_website
from core.cache_manager import cache_get, cache_set


def run_retail_enrichment(
    domain: str,
    brand_name: str,
    html: Optional[str] = None,
    geography: Optional[str] = None,
    category: Optional[str] = None,
    ig_bio: Optional[str] = None,
    knowledge_graph: Optional[Dict] = None,
    ig_username: Optional[str] = None,
    apollo_name: Optional[str] = None,
    skip_cache: bool = False,
    on_step: Optional[Callable[[str, str, int, str], None]] = None,
) -> Dict[str, Any]:
    """
    Run the retail channel enrichment pipeline for a single brand.

    NEVER raises exceptions. Returns a result dict with whatever data
    could be collected. Missing fields stay None.

    Args:
        domain: Brand domain (e.g., 'armatura.com.co')
        brand_name: Brand/company name
        html: Pre-scraped HTML (optional, will scrape if missing)
        geography: 'COL', 'MEX', or None
        category: Product category (for Rappi relevance filtering)
        ig_bio: Instagram bio text (optional)
        knowledge_graph: Knowledge graph dict from Google Demand (optional)
        skip_cache: If True, bypass cache
        on_step: Callback for step progress (same signature as main pipeline)

    Returns:
        Dict with:
            - success: bool
            - data: {has_distributors, has_own_stores, own_store_count_col, own_store_count_mex,
                     has_multibrand_stores, multibrand_store_names, on_mercadolibre, on_amazon,
                     on_rappi, retail_confidence}
            - steps: list of step log entries
            - error: str or None
    """
    steps: List[Dict[str, Any]] = []
    start_time = time.time()
    channels_attempted = 0
    channels_succeeded = 0

    # Result accumulator
    data = {
        "has_distributors": None,
        "has_own_stores": None,
        "own_store_count_col": None,
        "own_store_count_mex": None,
        "has_multibrand_stores": None,
        "multibrand_store_names": [],
        "on_mercadolibre": None,
        "on_amazon": None,
        "on_rappi": None,
        "retail_confidence": None,
    }

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
                pass

    # ===== STEP R0: Ensure we have HTML =====
    t0 = time.time()
    if not html:
        try:
            cached = cache_get(domain, "web_scraper") if (domain and not skip_cache) else None
            if cached and cached.get("success"):
                html = cached["data"].get("html", "")
                ms = int((time.time() - t0) * 1000)
                _step("retail_scrape", "ok", ms, f"cached, {len(html) // 1024}KB")
            else:
                url = f"https://{domain}"
                scrape_result = scrape_website(url, timeout=60)
                ms = int((time.time() - t0) * 1000)
                if scrape_result["success"]:
                    html = scrape_result["data"]["html"]
                    cache_set(domain, "web_scraper", scrape_result["data"])
                    _step("retail_scrape", "ok", ms, f"{len(html) // 1024}KB")
                else:
                    html = ""
                    _step("retail_scrape", "warn", ms, scrape_result.get("error", "scrape failed"))
        except Exception as e:
            ms = int((time.time() - t0) * 1000)
            html = ""
            _step("retail_scrape", "fail", ms, str(e))
    else:
        ms = int((time.time() - t0) * 1000)
        _step("retail_scrape", "ok", ms, f"reused, {len(html) // 1024}KB")

    # ===== STEP R0.5: Google Shopping Sellers =====
    shopping_multibrand: List[str] = []
    shopping_marketplaces: Dict[str, bool] = {}
    shopping_other: List[str] = []
    t0 = time.time()
    try:
        from retail.google_shopping_sellers import detect_sellers_from_shopping
        sb_client = None
        try:
            from export.supabase_writer import get_client
            sb_client = get_client()
        except Exception:
            pass

        shop_result = detect_sellers_from_shopping(
            brand_name, geography, supabase_client=sb_client,
        )
        ms = int((time.time() - t0) * 1000)
        if shop_result["success"]:
            sd = shop_result["data"]
            shopping_multibrand = sd.get("multibrand_found", [])
            shopping_marketplaces = sd.get("marketplaces_found", {})
            shopping_other = sd.get("other_retailers", [])
            parts = []
            if shopping_multibrand:
                parts.append(f"stores: {', '.join(shopping_multibrand[:3])}")
            if shopping_marketplaces:
                parts.append(f"mkts: {', '.join(shopping_marketplaces.keys())}")
            parts.append(f"{len(sd.get('all_sellers', []))} sellers")
            _step("retail_shopping", "ok", ms, " | ".join(parts))
        else:
            _step("retail_shopping", "warn", ms, shop_result.get("error", ""))
    except Exception as e:
        ms = int((time.time() - t0) * 1000)
        _step("retail_shopping", "fail", ms, str(e))

    # ===== STEP R1: Distributors =====
    channels_attempted += 1
    t0 = time.time()
    try:
        cached = cache_get(domain, "retail_distributors") if (domain and not skip_cache) else None
        if cached and cached.get("success"):
            dist_data = cached["data"]
            ms = int((time.time() - t0) * 1000)
        else:
            from retail.detect_distributors import detect_distributors
            dist_result = detect_distributors(html, domain, brand_name, geography)
            ms = int((time.time() - t0) * 1000)
            dist_data = dist_result.get("data", {}) if dist_result.get("success") else {}
            if domain and dist_data:
                cache_set(domain, "retail_distributors", dist_data)

        if dist_data.get("has_distributors") is not None:
            data["has_distributors"] = dist_data["has_distributors"]
            status = "ok" if dist_data["has_distributors"] else "ok"
            _step("retail_distributors", status, ms,
                  f"{'Yes' if dist_data['has_distributors'] else 'No'} — {dist_data.get('evidence', '')[:100]}")
            channels_succeeded += 1
        else:
            _step("retail_distributors", "warn", ms, "no data")
    except Exception as e:
        ms = int((time.time() - t0) * 1000)
        _step("retail_distributors", "fail", ms, str(e))

    # ===== STEP R2: Own Stores =====
    channels_attempted += 1
    t0 = time.time()
    try:
        cached = cache_get(domain, "retail_own_stores") if (domain and not skip_cache) else None
        if cached and cached.get("success"):
            stores_data = cached["data"]
            ms = int((time.time() - t0) * 1000)
        else:
            from retail.detect_own_stores import detect_own_stores
            stores_result = detect_own_stores(
                html, domain, brand_name, geography,
                ig_bio=ig_bio, knowledge_graph=knowledge_graph,
            )
            ms = int((time.time() - t0) * 1000)
            stores_data = stores_result.get("data", {}) if stores_result.get("success") else {}
            if domain and stores_data:
                cache_set(domain, "retail_own_stores", stores_data)

        if stores_data.get("has_own_stores") is not None:
            data["has_own_stores"] = stores_data["has_own_stores"]
            data["own_store_count_col"] = stores_data.get("own_store_count_col")
            data["own_store_count_mex"] = stores_data.get("own_store_count_mex")
            col = stores_data.get("own_store_count_col") or 0
            mex = stores_data.get("own_store_count_mex") or 0
            _step("retail_own_stores", "ok", ms,
                  f"{'Yes' if stores_data['has_own_stores'] else 'No'} — COL:{col} MEX:{mex}")
            channels_succeeded += 1
        else:
            _step("retail_own_stores", "warn", ms, "no data")
    except Exception as e:
        ms = int((time.time() - t0) * 1000)
        _step("retail_own_stores", "fail", ms, str(e))

    # ===== STEP R3: Multi-brand Stores =====
    channels_attempted += 1
    t0 = time.time()
    try:
        cached = cache_get(domain, "retail_multibrand") if (domain and not skip_cache) else None
        if cached and cached.get("success"):
            mb_data = cached["data"]
            ms = int((time.time() - t0) * 1000)
        else:
            from retail.detect_multibrand_stores import detect_multibrand_stores
            # Try to get Supabase client for DB lookups
            sb_client = None
            try:
                from export.supabase_writer import get_client
                sb_client = get_client()
            except Exception:
                pass

            mb_result = detect_multibrand_stores(
                html, domain, brand_name, geography,
                ig_bio=ig_bio, supabase_client=sb_client,
                ig_username=ig_username, apollo_name=apollo_name,
                shopping_sellers=shopping_multibrand,
            )
            ms = int((time.time() - t0) * 1000)
            mb_data = mb_result.get("data", {}) if mb_result.get("success") else {}
            if domain and mb_data:
                cache_set(domain, "retail_multibrand", mb_data)

        if mb_data.get("has_multibrand_stores") is not None:
            data["has_multibrand_stores"] = mb_data["has_multibrand_stores"]
            data["multibrand_store_names"] = mb_data.get("multibrand_store_names", [])
            stores_str = ", ".join(data["multibrand_store_names"][:5]) if data["multibrand_store_names"] else "none"
            _step("retail_multibrand", "ok", ms,
                  f"{'Yes' if mb_data['has_multibrand_stores'] else 'No'} — {stores_str}")
            channels_succeeded += 1
        else:
            _step("retail_multibrand", "warn", ms, "no data")
    except Exception as e:
        ms = int((time.time() - t0) * 1000)
        _step("retail_multibrand", "fail", ms, str(e))

    # ===== STEP R4: Marketplaces =====
    channels_attempted += 1
    t0 = time.time()
    try:
        cached = cache_get(domain, "retail_marketplaces") if (domain and not skip_cache) else None
        if cached and cached.get("success"):
            mp_data = cached["data"]
            ms = int((time.time() - t0) * 1000)
        else:
            from retail.detect_marketplaces import detect_marketplaces
            mp_result = detect_marketplaces(
                html, domain, brand_name, geography, category=category,
                shopping_marketplaces=shopping_marketplaces,
            )
            ms = int((time.time() - t0) * 1000)
            mp_data = mp_result.get("data", {}) if mp_result.get("success") else {}
            if domain and mp_data:
                cache_set(domain, "retail_marketplaces", mp_data)

        if mp_data.get("on_mercadolibre") is not None:
            data["on_mercadolibre"] = mp_data["on_mercadolibre"]
            data["on_amazon"] = mp_data.get("on_amazon")
            data["on_rappi"] = mp_data.get("on_rappi")
            parts = []
            if mp_data["on_mercadolibre"]:
                parts.append("ML")
            if mp_data.get("on_amazon"):
                parts.append("AMZ")
            if mp_data.get("on_rappi"):
                parts.append("Rappi")
            _step("retail_marketplaces", "ok", ms,
                  f"Present: {', '.join(parts) if parts else 'none'}")
            channels_succeeded += 1
        else:
            _step("retail_marketplaces", "warn", ms, "no data")
    except Exception as e:
        ms = int((time.time() - t0) * 1000)
        _step("retail_marketplaces", "fail", ms, str(e))

    # ===== FINALIZE =====
    data["retail_confidence"] = round(channels_succeeded / max(channels_attempted, 1), 2)

    total_runtime = round(time.time() - start_time, 2)
    _step("retail_done", "ok", int(total_runtime * 1000),
          f"{channels_succeeded}/{channels_attempted} channels OK, {total_runtime}s")

    return {
        "success": channels_succeeded > 0,
        "data": data,
        "steps": steps,
        "error": None,
    }


def _write_retail_to_supabase(domain: str, data: Dict[str, Any]) -> bool:
    """
    Write retail enrichment results to Supabase enriched_companies table.

    Only updates existing rows (PATCH). If the domain doesn't exist in
    enriched_companies yet, it skips the write — retail enrichment is
    meant to enrich domains already in the table.
    """
    try:
        from export.supabase_writer import get_client
        client = get_client()

        # Check if domain exists first (upsert would fail on NOT NULL run_id)
        existing = client.select(
            "enriched_companies",
            columns="domain",
            eq={"domain": domain},
            limit=1,
        )
        if not existing:
            print(f"  [WARN] Domain '{domain}' not in enriched_companies, skipping write")
            return False

        row = {
            "has_distributors": data.get("has_distributors"),
            "has_own_stores": data.get("has_own_stores"),
            "own_store_count_col": data.get("own_store_count_col"),
            "own_store_count_mex": data.get("own_store_count_mex"),
            "has_multibrand_stores": data.get("has_multibrand_stores"),
            "multibrand_store_names": json.dumps(data.get("multibrand_store_names", [])),
            "on_mercadolibre": data.get("on_mercadolibre"),
            "on_amazon": data.get("on_amazon"),
            "on_rappi": data.get("on_rappi"),
            "retail_confidence": data.get("retail_confidence"),
            "retail_enriched_at": datetime.now(timezone.utc).isoformat(),
        }

        # PATCH (update) existing row via PostgREST
        import requests
        resp = requests.patch(
            f"{client.rest_url}/enriched_companies",
            headers=client.headers,
            params={"domain": f"eq.{domain}"},
            json=row,
            timeout=30,
        )
        resp.raise_for_status()
        return True

    except Exception as e:
        print(f"  [ERROR] Supabase write failed: {e}")
        return False


def _run_single(domain: str, skip_cache: bool = False) -> Dict[str, Any]:
    """
    Run retail enrichment for a single domain.
    Reads brand_name, geography, category from enriched_companies if available.
    """
    brand_name = domain.split(".")[0]
    geography = None
    category = None

    # Try to read existing enrichment data for context
    try:
        from export.supabase_writer import get_client
        client = get_client()
        rows = client.select(
            "enriched_companies",
            columns="company_name,geography,category",
            eq={"domain": domain},
            limit=1,
        )
        if rows:
            row = rows[0]
            brand_name = row.get("company_name") or brand_name
            geography = row.get("geography")
            category = row.get("category")
    except Exception:
        pass

    print(f"\n  Brand: {brand_name}")
    print(f"  Geography: {geography or 'unknown'}")
    print(f"  Category: {category or 'unknown'}")

    def on_step(name, status, duration_ms, detail):
        icon = {"ok": "+", "warn": "~", "fail": "!", "running": ">"}
        print(f"  [{icon.get(status, '?')}] {name:25s} {status:5s} {duration_ms:6d}ms  {detail[:80]}")

    result = run_retail_enrichment(
        domain=domain,
        brand_name=brand_name,
        geography=geography,
        category=category,
        skip_cache=skip_cache,
        on_step=on_step,
    )

    # Write to Supabase
    if result["success"]:
        print(f"\n  Writing to Supabase...")
        written = _write_retail_to_supabase(domain, result["data"])
        print(f"  {'OK' if written else 'FAILED'}")

    return result


def _run_batch(skip_cache: bool = False, limit: int = 0):
    """
    Run retail enrichment for all domains missing retail data.
    """
    try:
        from export.supabase_writer import get_client
        client = get_client()
    except Exception as e:
        print(f"[ERROR] Cannot connect to Supabase: {e}")
        return

    # Fetch domains where retail_enriched_at IS NULL
    # PostgREST uses "is.null" filter
    rows = client.select(
        "enriched_companies",
        columns="domain,company_name,geography,category",
        eq={"retail_enriched_at": "null"},  # This won't work for NULL; we'll filter client-side
    )

    # Actually, PostgREST NULL filter needs special handling
    # Let's fetch all and filter
    all_rows = client.select(
        "enriched_companies",
        columns="domain,company_name,geography,category,retail_enriched_at",
        order="created_at.desc",
    )
    pending = [r for r in all_rows if not r.get("retail_enriched_at")]

    if limit > 0:
        pending = pending[:limit]

    print(f"Found {len(pending)} domains pending retail enrichment")
    print("=" * 60)

    for i, row in enumerate(pending, 1):
        domain = row["domain"]
        brand_name = row.get("company_name") or domain.split(".")[0]
        geography = row.get("geography")
        category = row.get("category")

        print(f"\n[{i}/{len(pending)}] {domain}")

        def on_step(name, status, duration_ms, detail):
            icon = {"ok": "+", "warn": "~", "fail": "!", "running": ">"}
            print(f"  [{icon.get(status, '?')}] {name:25s} {status:5s} {duration_ms:6d}ms  {detail[:80]}")

        result = run_retail_enrichment(
            domain=domain,
            brand_name=brand_name,
            geography=geography,
            category=category,
            skip_cache=skip_cache,
            on_step=on_step,
        )

        if result["success"]:
            _write_retail_to_supabase(domain, result["data"])

        # Brief summary
        d = result["data"]
        flags = []
        if d.get("has_distributors"):
            flags.append("DIST")
        if d.get("has_own_stores"):
            flags.append(f"STORES(COL:{d.get('own_store_count_col', 0)} MEX:{d.get('own_store_count_mex', 0)})")
        if d.get("has_multibrand_stores"):
            flags.append(f"MULTI({','.join(d.get('multibrand_store_names', [])[:3])})")
        if d.get("on_mercadolibre"):
            flags.append("ML")
        if d.get("on_amazon"):
            flags.append("AMZ")
        if d.get("on_rappi"):
            flags.append("RAPPI")
        print(f"  => {' | '.join(flags) if flags else 'No retail channels detected'}")

    print(f"\n{'=' * 60}")
    print(f"Batch complete: {len(pending)} domains processed")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Retail channel enrichment")
    parser.add_argument("domain", nargs="?", help="Domain to enrich (e.g., armatura.com.co)")
    parser.add_argument("--batch", action="store_true", help="Process all domains without retail data")
    parser.add_argument("--skip-cache", action="store_true", help="Bypass cache")
    parser.add_argument("--limit", type=int, default=0, help="Max domains in batch mode")
    args = parser.parse_args()

    print("Retail Channel Enrichment")
    print("=" * 60)

    if args.batch:
        _run_batch(skip_cache=args.skip_cache, limit=args.limit)
    elif args.domain:
        print(f"Domain: {args.domain}")
        result = _run_single(args.domain, skip_cache=args.skip_cache)

        print(f"\n{'=' * 60}")
        print("Result summary:")
        d = result["data"]
        print(f"  Distributors:     {d.get('has_distributors')}")
        print(f"  Own stores:       {d.get('has_own_stores')} (COL: {d.get('own_store_count_col')}, MEX: {d.get('own_store_count_mex')})")
        print(f"  Multibrand:       {d.get('has_multibrand_stores')} ({d.get('multibrand_store_names', [])})")
        print(f"  MercadoLibre:     {d.get('on_mercadolibre')}")
        print(f"  Amazon:           {d.get('on_amazon')}")
        print(f"  Rappi:            {d.get('on_rappi')}")
        print(f"  Confidence:       {d.get('retail_confidence')}")
    else:
        parser.print_help()
