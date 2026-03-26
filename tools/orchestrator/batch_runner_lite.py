"""
Batch Lite Enrichment Runner

Purpose: Process CSV lead lists concurrently through the lite pipeline.
Features:
  - Concurrent processing (ThreadPoolExecutor, 5 workers default)
  - Resume from database (skip already-processed domains with full enrichment)
  - CSV input with auto-detection of columns
  - Console progress logging
  - Summary CSV output
  - Dry-run mode

Usage:
  python batch_runner_lite.py leads.csv
  python batch_runner_lite.py leads.csv --dry-run 10
  python batch_runner_lite.py leads.csv --workers 8 --batch-id hubspot-mar26
  python batch_runner_lite.py leads.csv --country Colombia --skip-cache
"""

import os
import sys
import csv
import time
import uuid
import argparse
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Optional, Dict, Any

# Allow imports from tools/ root
_TOOLS_DIR = os.path.join(os.path.dirname(__file__), "..")
if _TOOLS_DIR not in sys.path:
    sys.path.insert(0, _TOOLS_DIR)

from core.csv_reader import read_csv_leads
from core.url_normalizer import normalize_url, extract_domain
from orchestrator.run_enrichment_lite import run_enrichment_lite
from export.supabase_writer import (
    get_client as get_supabase_client,
    upsert_enrichment,
)
from logistics.supabase_client import SupabaseClient

TABLE = "enriched_companies"

# Thread-safe progress counter
_lock = threading.Lock()
_stats = {
    "processed": 0,
    "succeeded": 0,
    "failed": 0,
    "skipped": 0,
}


def _read_existing_full_domains(client: SupabaseClient) -> set:
    """Read domains that already have full enrichment (should not be overwritten)."""
    try:
        rows = client.select(
            TABLE,
            columns="domain,enrichment_type",
        )
        # Skip domains with full enrichment; re-process lite ones
        return {
            r["domain"]
            for r in rows
            if r.get("domain") and r.get("enrichment_type") == "full"
        }
    except Exception:
        return set()


def _process_single_lead(
    lead: Dict,
    index: int,
    total: int,
    sb_client: SupabaseClient,
    batch_id: str,
    country: Optional[str],
    skip_cache: bool,
) -> Dict[str, Any]:
    """Process one lead through the lite pipeline. Thread-safe."""
    t0 = time.time()
    name = lead.get("company_name", "")
    website = lead.get("website_url", "")
    ig = lead.get("instagram_url", "")

    label = name or website or ig or f"row-{lead.get('row_number', '?')}"

    try:
        result = run_enrichment_lite(
            company_name=name,
            website_url=website,
            instagram_url=ig,
            batch_id=batch_id,
            country=country,
            skip_cache=skip_cache,
        )
        elapsed = time.time() - t0

        # Determine success
        has_data = bool(result.domain or result.ig_followers)

        # Upsert to Supabase (only if we have a domain to key on)
        saved = False
        if result.domain:
            try:
                upsert_enrichment(sb_client, result)
                saved = True
            except Exception as e:
                pass  # logged below

        # Build summary line
        parts = []
        if has_data:
            parts.append(f"OK ({elapsed:.1f}s)")
        else:
            parts.append(f"FAIL ({elapsed:.1f}s)")

        if result.platform:
            parts.append(result.platform)
        if result.ig_followers:
            parts.append(f"IG:{result.ig_followers:,}")
        if result.lite_triage_score is not None:
            marker = "ENRICH" if result.worth_full_enrichment else "skip"
            parts.append(f"Score:{result.lite_triage_score} {marker}")

        with _lock:
            _stats["processed"] += 1
            if has_data:
                _stats["succeeded"] += 1
            else:
                _stats["failed"] += 1
            current = _stats["processed"] + _stats["skipped"]
            print(f"[{current}/{total}] {label[:40]:40s} | {' | '.join(parts)}")

        return {
            "company_name": result.company_name or name,
            "domain": result.domain,
            "website_url": result.clean_url,
            "instagram_url": result.instagram_url,
            "platform": result.platform,
            "geography": result.geography,
            "ig_followers": result.ig_followers,
            "ig_size_score": result.ig_size_score,
            "hubspot_deal_stage": result.hubspot_deal_stage,
            "lite_triage_score": result.lite_triage_score,
            "worth_full_enrichment": result.worth_full_enrichment,
            "elapsed_sec": round(elapsed, 1),
            "saved": saved,
        }

    except Exception as e:
        elapsed = time.time() - t0
        with _lock:
            _stats["processed"] += 1
            _stats["failed"] += 1
            current = _stats["processed"] + _stats["skipped"]
            print(f"[{current}/{total}] {label[:40]:40s} | ERROR ({elapsed:.1f}s): {str(e)[:60]}")

        return {
            "company_name": name,
            "domain": None,
            "error": str(e),
            "lite_triage_score": 0,
            "worth_full_enrichment": False,
            "elapsed_sec": round(elapsed, 1),
        }


def run_batch_lite(
    leads: List[Dict],
    batch_id: Optional[str] = None,
    max_workers: int = 5,
    dry_run: int = 0,
    country: Optional[str] = None,
    skip_cache: bool = False,
) -> Dict[str, Any]:
    """
    Process leads concurrently through the lite enrichment pipeline.

    Args:
        leads: List of lead dicts from csv_reader
        batch_id: Shared batch identifier
        max_workers: Concurrent workers (default 5)
        dry_run: Process only N leads (0 = all)
        country: Country context
        skip_cache: Bypass cache

    Returns:
        Summary dict with stats and results
    """
    batch_id = batch_id or f"lite-{str(uuid.uuid4())[:8]}"

    print(f"Batch Lite Enrichment")
    print(f"=" * 70)
    print(f"Batch ID:  {batch_id}")
    print(f"Workers:   {max_workers}")
    if country:
        print(f"Country:   {country}")

    # Apply dry-run
    if dry_run > 0:
        leads = leads[:dry_run]
        print(f"DRY RUN:   processing only {len(leads)} leads")

    total_leads = len(leads)
    print(f"Total:     {total_leads} leads")
    print()

    # Supabase setup
    print("Connecting to Supabase...", end=" ", flush=True)
    try:
        sb_client = get_supabase_client()
        print("OK")
    except Exception as e:
        print(f"FAILED: {e}")
        return {"error": str(e)}

    # Resume: skip domains with full enrichment
    print("Reading existing full-enrichment domains...", end=" ", flush=True)
    full_domains = _read_existing_full_domains(sb_client)
    print(f"{len(full_domains)} domains with full enrichment (will skip)")

    # Filter out leads whose domain already has full enrichment
    filtered_leads = []
    for lead in leads:
        website = lead.get("website_url", "")
        if website:
            norm = normalize_url(website)
            if norm["success"]:
                d = extract_domain(norm["data"]["url"])
                if d and d.lower() in {fd.lower() for fd in full_domains}:
                    with _lock:
                        _stats["skipped"] += 1
                    continue
        filtered_leads.append(lead)

    skipped_full = total_leads - len(filtered_leads)
    if skipped_full > 0:
        print(f"Skipping {skipped_full} leads (already have full enrichment)")

    print(f"Processing {len(filtered_leads)} leads with {max_workers} workers")
    print("=" * 70)

    # Reset stats
    _stats["processed"] = 0
    _stats["succeeded"] = 0
    _stats["failed"] = 0
    # Keep skipped count from above

    batch_start = time.time()
    all_results = []

    # Concurrent processing
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {}
        for i, lead in enumerate(filtered_leads):
            # Small delay between submissions to avoid burst
            time.sleep(0.15)
            future = executor.submit(
                _process_single_lead,
                lead=lead,
                index=i,
                total=total_leads,
                sb_client=sb_client,
                batch_id=batch_id,
                country=country,
                skip_cache=skip_cache,
            )
            futures[future] = i

        for future in as_completed(futures):
            try:
                result = future.result()
                all_results.append(result)
            except Exception as e:
                all_results.append({"error": str(e), "lite_triage_score": 0})

    total_time = time.time() - batch_start

    # Sort results by triage score (descending)
    all_results.sort(key=lambda r: r.get("lite_triage_score") or 0, reverse=True)

    # Count worth_full
    worth_full = [r for r in all_results if r.get("worth_full_enrichment")]

    # Summary
    print()
    print("=" * 70)
    print("BATCH LITE COMPLETE")
    print(f"  Total leads:    {total_leads}")
    print(f"  Processed:      {_stats['processed']}")
    print(f"  Succeeded:      {_stats['succeeded']}")
    print(f"  Failed:         {_stats['failed']}")
    print(f"  Skipped (full): {_stats['skipped']}")
    print(f"  Worth enrich:   {len(worth_full)}")
    print(f"  Time:           {total_time:.1f}s ({total_time/60:.1f}m)")
    if _stats["processed"] > 0:
        print(f"  Avg/lead:       {total_time/_stats['processed']:.1f}s")
        est_cost = _stats["processed"] * 0.02
        print(f"  Est. cost:      ${est_cost:.2f}")
    print(f"  Batch ID:       {batch_id}")

    # Top candidates
    if worth_full:
        print(f"\n  TOP CANDIDATES ({len(worth_full)} worth full enrichment):")
        for r in worth_full[:20]:
            name = r.get("company_name", "?")[:30]
            dom = r.get("domain", "?")[:25]
            score = r.get("lite_triage_score", 0)
            plat = r.get("platform", "?")
            ig = r.get("ig_followers") or 0
            print(f"    {score:3d} | {name:30s} | {dom:25s} | {plat:15s} | IG:{ig:,}")

    # Save summary CSV
    _save_summary_csv(all_results, batch_id)

    return {
        "total": total_leads,
        "processed": _stats["processed"],
        "succeeded": _stats["succeeded"],
        "failed": _stats["failed"],
        "skipped": _stats["skipped"],
        "worth_full_count": len(worth_full),
        "batch_id": batch_id,
        "total_time_sec": round(total_time, 1),
        "avg_time_per_lead": round(total_time / max(_stats["processed"], 1), 1),
        "results": all_results,
    }


def _save_summary_csv(results: List[Dict], batch_id: str):
    """Save a summary CSV for quick review."""
    tmp_dir = os.path.join(os.path.dirname(__file__), "..", "..", ".tmp")
    os.makedirs(tmp_dir, exist_ok=True)
    out_path = os.path.join(tmp_dir, f"lite_results_{batch_id}.csv")

    fieldnames = [
        "company_name", "domain", "website_url", "instagram_url",
        "platform", "geography", "ig_followers", "ig_size_score",
        "hubspot_deal_stage", "lite_triage_score", "worth_full_enrichment",
        "elapsed_sec",
    ]

    try:
        with open(out_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            for r in results:
                writer.writerow(r)
        print(f"\n  Summary CSV: {out_path}")
    except Exception as e:
        print(f"\n  [WARN] Could not save summary CSV: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Batch Lite Enrichment — fast triage of CSV lead lists"
    )
    parser.add_argument(
        "input",
        help="Path to CSV file with company name + URL columns",
    )
    parser.add_argument(
        "--dry-run",
        type=int,
        default=0,
        help="Process only N leads (for testing)",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=5,
        help="Number of concurrent workers (default: 5)",
    )
    parser.add_argument(
        "--batch-id",
        default=None,
        help="Custom batch ID (auto-generated if not provided)",
    )
    parser.add_argument(
        "--country",
        default=None,
        help="Country context (e.g., 'Colombia')",
    )
    parser.add_argument(
        "--skip-cache",
        action="store_true",
        help="Bypass cache for fresh data",
    )
    parser.add_argument(
        "--name-col",
        default=None,
        help="Explicit name column header",
    )
    parser.add_argument(
        "--website-col",
        default=None,
        help="Explicit website URL column header",
    )
    parser.add_argument(
        "--ig-col",
        default=None,
        help="Explicit Instagram URL column header",
    )
    args = parser.parse_args()

    # Read CSV
    print(f"Reading CSV: {args.input}")
    csv_result = read_csv_leads(
        args.input,
        name_col=args.name_col,
        website_col=args.website_col,
        ig_col=args.ig_col,
    )

    if not csv_result["success"]:
        print(f"ERROR: {csv_result['error']}")
        sys.exit(1)

    data = csv_result["data"]
    print(f"  Rows: {data['total_rows']}")
    print(f"  Valid leads: {data['valid_leads']}")
    print(f"  Duplicates removed: {data['duplicates_removed']}")
    print(f"  Empty rows skipped: {data['empty_rows_skipped']}")
    print(f"  Columns: {data['detected_columns']}")
    print()

    leads = data["leads"]
    if not leads:
        print("ERROR: No valid leads to process")
        sys.exit(1)

    stats = run_batch_lite(
        leads=leads,
        batch_id=args.batch_id,
        max_workers=args.workers,
        dry_run=args.dry_run,
        country=args.country,
        skip_cache=args.skip_cache,
    )
