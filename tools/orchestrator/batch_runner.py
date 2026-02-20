"""
Batch Enrichment Runner

Purpose: Process a list of URLs serially, writing results to Google Sheets.
Features:
  - Resume from sheet (skip already-processed domains)
  - Buffer + flush every 10 rows
  - Console progress logging
  - Dry-run mode
  - CLI entry point

Usage:
  python batch_runner.py urls.txt
  python batch_runner.py urls.txt --dry-run 5
  python batch_runner.py urls.txt --sheet "https://docs.google.com/spreadsheets/d/..."
  python batch_runner.py urls.txt --sheet URL --batch-id my-batch-001
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

from models.enrichment_result import EnrichmentResult, SHEET_HEADERS
from orchestrator.run_enrichment import run_enrichment
from export.google_sheets_writer import (
    get_gspread_client,
    create_or_open_spreadsheet,
    append_rows,
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


def run_batch(
    urls: List[str],
    spreadsheet_url: Optional[str] = None,
    batch_id: Optional[str] = None,
    dry_run: int = 0,
    enable_google_demand: bool = True,
    buffer_size: int = 10,
    worksheet_name: Optional[str] = None,
    country: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Process URLs serially, writing to Google Sheets every buffer_size rows.

    Args:
        urls: List of raw URLs or brand names
        spreadsheet_url: Existing sheet URL for resume (optional)
        batch_id: Shared batch_id (auto-generated if None)
        dry_run: If > 0, process only this many companies
        enable_google_demand: If True, run Google Demand scoring
        buffer_size: Number of rows to buffer before flushing (default: 10)
        country: Country context for brand name resolution (e.g., "Colombia")

    Returns:
        {total, processed, succeeded, failed, skipped, sheet_url, batch_id}
    """
    batch_id = batch_id or str(uuid.uuid4())
    batch_short = batch_id[:8]

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

    # --- Google Sheets setup ---
    print("Connecting to Google Sheets...", end=" ", flush=True)
    try:
        client = get_gspread_client()
        sheet_result = create_or_open_spreadsheet(
            client,
            spreadsheet_url=spreadsheet_url,
            batch_id_short=batch_short,
            worksheet_name=worksheet_name,
        )
        if not sheet_result["success"]:
            print(f"FAILED: {sheet_result['error']}")
            return {"error": sheet_result["error"]}

        worksheet = sheet_result["data"]["worksheet"]
        sheet_url = sheet_result["data"]["sheet_url"]
        print(f"OK")
        print(f"Sheet: {sheet_url}")
    except Exception as e:
        print(f"FAILED: {e}")
        return {"error": str(e)}

    # --- Resume: read existing domains ---
    existing_domains = set()
    if spreadsheet_url:
        print("Reading existing domains for resume...", end=" ", flush=True)
        existing_domains = read_existing_domains(worksheet)
        print(f"{len(existing_domains)} already processed")

    print("=" * 60)

    # --- Serial processing ---
    buffer = []
    stats = {
        "total": len(urls),
        "processed": 0,
        "succeeded": 0,
        "failed": 0,
        "skipped": 0,
        "sheet_url": sheet_url,
        "batch_id": batch_id,
    }

    batch_start = time.time()

    for i, raw_url in enumerate(urls):
        # Check resume
        domain = _quick_domain(raw_url)
        if domain and domain in existing_domains:
            stats["skipped"] += 1
            print(f"[{i+1}/{len(urls)}] SKIP {raw_url} (already in sheet)")
            continue

        t0 = time.time()
        print(f"[{i+1}/{len(urls)}] {raw_url}...", end=" ", flush=True)

        result = run_enrichment(
            raw_url,
            batch_id=batch_id,
            enable_google_demand=enable_google_demand,
            country=country,
        )
        elapsed = time.time() - t0

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
        print(" | ".join(parts))

        # Add to buffer
        row = result.to_row()
        buffer.append(row)

        # Flush buffer
        if len(buffer) >= buffer_size:
            try:
                flush_result = append_rows(worksheet, buffer)
                if flush_result["success"]:
                    print(f"  >> flushed {len(buffer)} rows to sheet")
                else:
                    print(f"  >> ERROR flushing: {flush_result['error']}")
            except Exception as e:
                print(f"  >> ERROR flushing: {e}")
            buffer = []

    # Flush remaining
    if buffer:
        try:
            flush_result = append_rows(worksheet, buffer)
            if flush_result["success"]:
                print(f"  >> flushed final {len(buffer)} rows to sheet")
            else:
                print(f"  >> ERROR flushing final rows: {flush_result['error']}")
        except Exception as e:
            print(f"  >> ERROR flushing final rows: {e}")

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
    print(f"  Sheet:     {sheet_url}")
    print(f"  Batch ID:  {batch_id}")

    return stats


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Batch Enrichment Runner — process URLs and write to Google Sheets"
    )
    parser.add_argument(
        "input",
        help="Path to URL list file (one URL per line) or comma-separated URLs",
    )
    parser.add_argument(
        "--sheet",
        default=None,
        help="Existing Google Sheet URL (enables resume from where we left off)",
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
        "--buffer-size",
        type=int,
        default=10,
        help="Rows to buffer before flushing to Sheets (default: 10)",
    )
    parser.add_argument(
        "--worksheet",
        default=None,
        help="Worksheet tab name (creates new tab if it doesn't exist)",
    )
    parser.add_argument(
        "--country",
        default=None,
        help="Country context for brand name resolution (e.g., 'Colombia')",
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
        spreadsheet_url=args.sheet,
        batch_id=args.batch_id,
        dry_run=args.dry_run,
        enable_google_demand=not args.no_demand,
        buffer_size=args.buffer_size,
        worksheet_name=args.worksheet,
        country=args.country,
    )
