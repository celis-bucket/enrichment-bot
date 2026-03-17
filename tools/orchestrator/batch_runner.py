"""
Batch Enrichment Runner

Purpose: Process a list of URLs serially, writing results to Supabase.
Features:
  - Resume from database (skip already-processed domains)
  - Upsert each row immediately after processing
  - Console progress logging
  - Dry-run mode
  - CLI entry point

Usage:
  python batch_runner.py urls.txt
  python batch_runner.py urls.txt --dry-run 5
  python batch_runner.py urls.txt --batch-id my-batch-001
"""

import os
import sys
import time
import uuid
import argparse
from typing import List, Optional, Dict, Any

# Allow imports from tools/ root
_TOOLS_DIR = os.path.join(os.path.dirname(__file__), "..")
if _TOOLS_DIR not in sys.path:
    sys.path.insert(0, _TOOLS_DIR)

from models.enrichment_result import EnrichmentResult
from orchestrator.run_enrichment import run_enrichment
from export.supabase_writer import (
    get_client as get_supabase_client,
    upsert_enrichment,
    read_existing_domains,
)
from core.url_normalizer import normalize_url, extract_domain


def _quick_domain(raw_url: str) -> Optional[str]:
    """Quick domain extraction without full normalization."""
    text = raw_url.strip().lower()
    for prefix in ("https://", "http://", "www."):
        if text.startswith(prefix):
            text = text[len(prefix):]
    return text.split("/")[0].split("?")[0] if text else None


def _deduplicate_urls(urls: List[str]) -> List[str]:
    """Deduplicate URLs by domain, keeping first occurrence."""
    seen = set()
    result = []
    for url in urls:
        d = _quick_domain(url)
        if d and d not in seen:
            seen.add(d)
            result.append(url.strip())
        elif not d:
            result.append(url.strip())  # keep unresolvable entries
    return result


def _read_urls_from_file(file_path: str) -> List[str]:
    """Read URLs from a text file (one per line, skip comments and blanks)."""
    urls = []
    encodings = ["utf-8", "latin-1"]
    for enc in encodings:
        try:
            with open(file_path, "r", encoding=enc) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        urls.append(line)
            return urls
        except UnicodeDecodeError:
            continue
    raise ValueError(f"Could not read {file_path} with any supported encoding")


def _run_prediction(enrichment_result) -> Optional[Dict[str, Any]]:
    """Run the orders estimator on an enrichment result. Returns prediction dict or None."""
    try:
        import pandas as pd

        # Add project root to path for orders_estimator imports
        project_root = os.path.join(os.path.dirname(__file__), "..", "..")
        if project_root not in sys.path:
            sys.path.insert(0, project_root)

        from tools.orders_estimator.predict import load_models, predict_batch

        row = {
            "platform": enrichment_result.platform,
            "category": enrichment_result.category,
            "ig_followers": enrichment_result.ig_followers,
            "ig_engagement_rate": enrichment_result.ig_engagement_rate,
            "ig_size_score": enrichment_result.ig_size_score,
            "ig_health_score": enrichment_result.ig_health_score,
            "product_count": enrichment_result.product_count,
            "avg_price": enrichment_result.avg_price,
            "price_range_min": enrichment_result.price_range_min,
            "price_range_max": enrichment_result.price_range_max,
            "estimated_monthly_visits": enrichment_result.estimated_monthly_visits,
            "brand_demand_score": enrichment_result.brand_demand_score,
            "number_employes": enrichment_result.number_employes,
            "meta_active_ads_count": enrichment_result.meta_active_ads_count,
        }
        df = pd.DataFrame([row])
        models = load_models()
        result_df = predict_batch(df, loaded=models)

        return {
            "predicted_orders_p10": int(result_df["predicted_orders_p10"].iloc[0]),
            "predicted_orders_p50": int(result_df["predicted_orders_p50"].iloc[0]),
            "predicted_orders_p90": int(result_df["predicted_orders_p90"].iloc[0]),
            "prediction_confidence": result_df["prediction_confidence"].iloc[0],
        }
    except Exception as e:
        print(f"  [WARN] Prediction failed: {e}")
        return None


def run_batch(
    urls: List[str],
    batch_id: Optional[str] = None,
    dry_run: int = 0,
    enable_google_demand: bool = True,
    country: Optional[str] = None,
    skip_cache: bool = False,
) -> Dict[str, Any]:
    """
    Process URLs serially, upserting each result to Supabase.

    Args:
        urls: List of raw URLs or brand names
        batch_id: Shared batch_id (auto-generated if None)
        dry_run: If > 0, process only this many companies
        enable_google_demand: If True, run Google Demand scoring
        country: Country context for brand name resolution (e.g., "Colombia")
        skip_cache: If True, bypass cache for fresh data

    Returns:
        {total, processed, succeeded, failed, skipped, batch_id}
    """
    batch_id = batch_id or str(uuid.uuid4())

    print(f"Batch ID: {batch_id}")
    print(f"Google Demand: {'ON' if enable_google_demand else 'OFF'}")
    if country:
        print(f"Country context: {country}")

    # Deduplicate input
    original_count = len(urls)
    urls = _deduplicate_urls(urls)
    if len(urls) < original_count:
        print(f"Deduplicated: {original_count} -> {len(urls)} unique URLs")

    # Apply dry-run limit
    if dry_run > 0:
        urls = urls[:dry_run]
        print(f"DRY RUN: processing only {len(urls)} companies")

    print(f"Total to process: {len(urls)}")
    print()

    # --- Supabase setup ---
    print("Connecting to Supabase...", end=" ", flush=True)
    try:
        sb_client = get_supabase_client()
        print("OK")
    except Exception as e:
        print(f"FAILED: {e}")
        return {"error": str(e)}

    # --- Resume: read existing domains ---
    print("Reading existing domains for resume...", end=" ", flush=True)
    existing_domains = read_existing_domains(sb_client)
    print(f"{len(existing_domains)} already processed")

    print("=" * 60)

    # --- Serial processing ---
    stats = {
        "total": len(urls),
        "processed": 0,
        "succeeded": 0,
        "failed": 0,
        "skipped": 0,
        "batch_id": batch_id,
    }

    batch_start = time.time()

    for i, raw_url in enumerate(urls):
        # Check resume
        domain = _quick_domain(raw_url)
        if domain and domain in existing_domains:
            stats["skipped"] += 1
            print(f"[{i+1}/{len(urls)}] SKIP {raw_url} (already in database)")
            continue

        t0 = time.time()
        print(f"[{i+1}/{len(urls)}] {raw_url}...", end=" ", flush=True)

        result = run_enrichment(
            raw_url,
            batch_id=batch_id,
            enable_google_demand=enable_google_demand,
            country=country,
            skip_cache=skip_cache,
        )
        elapsed = time.time() - t0

        # Run orders prediction
        prediction = _run_prediction(result)

        # Determine success/fail
        if result.clean_url and result.domain:
            stats["succeeded"] += 1
            status = "OK"
        else:
            stats["failed"] += 1
            status = "FAIL"
        stats["processed"] += 1

        # Summary line
        parts = [f"{status} ({elapsed:.1f}s)"]
        if result.platform:
            parts.append(result.platform)
        if result.category:
            parts.append(result.category)
        if result.ig_followers:
            parts.append(f"IG:{result.ig_followers:,}")
        if prediction:
            parts.append(f"P50:{prediction['predicted_orders_p50']}")
        print(" | ".join(parts))

        # Upsert to Supabase immediately
        try:
            upsert_enrichment(sb_client, result, prediction)
            print(f"  >> saved to Supabase")
        except Exception as e:
            print(f"  >> ERROR saving: {e}")

    # --- Summary ---
    total_time = time.time() - batch_start
    print()
    print("=" * 60)
    print(f"BATCH COMPLETE")
    print(f"  Total:     {stats['total']}")
    print(f"  Processed: {stats['processed']}")
    print(f"  Succeeded: {stats['succeeded']}")
    print(f"  Failed:    {stats['failed']}")
    print(f"  Skipped:   {stats['skipped']}")
    print(f"  Time:      {total_time:.1f}s ({total_time/60:.1f}m)")
    if stats["processed"] > 0:
        print(f"  Avg/URL:   {total_time/stats['processed']:.1f}s")
    print(f"  Batch ID:  {batch_id}")

    return stats


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Batch Enrichment Runner — process URLs and save to Supabase"
    )
    parser.add_argument(
        "input",
        help="Path to URL list file (one URL per line) or comma-separated URLs",
    )
    parser.add_argument(
        "--dry-run",
        type=int,
        default=0,
        help="Process only N companies (for testing)",
    )
    parser.add_argument(
        "--batch-id",
        default=None,
        help="Custom batch ID (auto-generated if not provided)",
    )
    parser.add_argument(
        "--no-demand",
        action="store_true",
        help="Disable Google Demand scoring (saves Serper credits)",
    )
    parser.add_argument(
        "--country",
        default=None,
        help="Country context for brand name resolution (e.g., 'Colombia')",
    )
    parser.add_argument(
        "--skip-cache",
        action="store_true",
        help="Bypass cache for fresh data on all steps",
    )
    args = parser.parse_args()

    # Read URLs from file or treat as comma-separated
    if os.path.isfile(args.input):
        urls = _read_urls_from_file(args.input)
        print(f"Read {len(urls)} URLs from {args.input}")
    else:
        urls = [u.strip() for u in args.input.split(",") if u.strip()]
        print(f"Parsed {len(urls)} URLs from command line")

    if not urls:
        print("ERROR: No URLs to process")
        sys.exit(1)

    stats = run_batch(
        urls=urls,
        batch_id=args.batch_id,
        dry_run=args.dry_run,
        enable_google_demand=not args.no_demand,
        country=args.country,
        skip_cache=args.skip_cache,
    )
