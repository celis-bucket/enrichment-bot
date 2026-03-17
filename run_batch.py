#!/usr/bin/env python3
"""
Simple batch enrichment CLI.

Usage:
  python run_batch.py urls.txt
  python run_batch.py urls.txt --dry-run 3
  python run_batch.py urls.txt --sheet "https://docs.google.com/spreadsheets/d/..."
  python run_batch.py urls.txt --country Colombia
"""

import os
import sys

# Add tools to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "tools"))

from orchestrator.batch_runner import run_batch, _read_urls_from_file

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Batch enrichment — process URLs from a file and write to Google Sheets"
    )
    parser.add_argument("file", help="Text file with one URL per line")
    parser.add_argument("--sheet", default=None, help="Existing Google Sheet URL (enables resume)")
    parser.add_argument("--dry-run", type=int, default=0, help="Process only N companies")
    parser.add_argument("--country", default=None, help="Country context (e.g., 'Colombia')")
    parser.add_argument("--skip-cache", action="store_true", help="Bypass cache for fresh data")
    args = parser.parse_args()

    if not os.path.isfile(args.file):
        print(f"ERROR: File not found: {args.file}")
        sys.exit(1)

    urls = _read_urls_from_file(args.file)
    print(f"Loaded {len(urls)} URLs from {args.file}")

    if not urls:
        print("ERROR: No URLs to process")
        sys.exit(1)

    run_batch(
        urls=urls,
        spreadsheet_url=args.sheet,
        dry_run=args.dry_run,
        country=args.country,
        skip_cache=args.skip_cache,
    )
