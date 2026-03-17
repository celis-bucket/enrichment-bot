"""
Backfill META Ads count for training data.

Reads the training Google Sheet (colombia_175), runs the Meta Ad Library
scraper for each store, and writes the `meta_active_ads_count` column back.

Uses Instagram URL or brand name as the search term (Facebook URLs
are not reliably available in the training data).

Usage:
    python -m tools.orders_estimator.backfill_meta_ads [--dry-run] [--delay SECONDS]
"""

import os
import sys
import time
import json
import argparse
from datetime import datetime

# Allow imports from tools/ root
_TOOLS_DIR = os.path.join(os.path.dirname(__file__), "..")
if _TOOLS_DIR not in sys.path:
    sys.path.insert(0, _TOOLS_DIR)

from social.apify_meta_ads import get_meta_ads_count, get_meta_ads_multi_search
from social.apify_instagram import extract_instagram_username
from export.google_sheets_writer import get_gspread_client
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
SHEET_URL = "https://docs.google.com/spreadsheets/d/1si5LxiXiaz0N5vh_w8LgGFnQ6ngpHX2UijTCLS_H1-o/"
WORKSHEET_NAME = "colombia_175"
TARGET_COLUMN_NAME = "meta_active_ads_count"
DEFAULT_DELAY = 3  # seconds between APIFY calls (rate limiting)
BACKUP_DIR = os.path.join(os.path.dirname(__file__), "..", "..", ".tmp", "orders_estimator", "datasets")


def backfill(dry_run: bool = False, delay: float = DEFAULT_DELAY):
    """
    Backfill meta_active_ads_count for all stores in the training sheet.

    Steps:
        1. Read sheet data
        2. Find identifier column (instagram_url, then domain)
        3. For each store: call get_meta_ads_count()
        4. Write results back to sheet in a new column
    """
    print(f"META Ads Backfill {'(DRY RUN)' if dry_run else ''}")
    print("=" * 60)

    # Step 1: Read sheet
    client = get_gspread_client()
    spreadsheet = client.open_by_url(SHEET_URL)
    worksheet = spreadsheet.worksheet(WORKSHEET_NAME)

    all_data = worksheet.get_all_records()
    headers = worksheet.row_values(1)
    print(f"Sheet: {WORKSHEET_NAME}")
    print(f"Rows: {len(all_data)}")
    print(f"Columns: {headers[:10]}...")

    # Step 2: Find identifier columns
    has_instagram = "instagram_url" in headers
    has_domain = "domain" in headers
    has_clean_url = "clean_url" in headers

    print(f"Has instagram_url column: {has_instagram}")
    print(f"Has domain column: {has_domain}")

    if not has_instagram and not has_domain and not has_clean_url:
        print("ERROR: No usable identifier column found (need instagram_url, domain, or clean_url)")
        return

    # Step 3: Check if target column already exists
    if TARGET_COLUMN_NAME in headers:
        col_index = headers.index(TARGET_COLUMN_NAME) + 1  # gspread is 1-indexed
        print(f"Column '{TARGET_COLUMN_NAME}' already exists at position {col_index}")
    else:
        col_index = len(headers) + 1
        print(f"Column '{TARGET_COLUMN_NAME}' will be added at position {col_index}")
        if not dry_run:
            worksheet.update_cell(1, col_index, TARGET_COLUMN_NAME)

    # Step 4: Save local backup
    os.makedirs(BACKUP_DIR, exist_ok=True)
    backup_path = os.path.join(BACKUP_DIR, f"backfill_meta_ads_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
    results = []

    # Step 5: Process each row
    total = len(all_data)
    succeeded = 0
    failed = 0
    skipped = 0

    for i, row in enumerate(all_data):
        row_num = i + 2  # 1-indexed, skip header

        domain_str = row.get("domain", row.get("clean_url", f"row_{row_num}"))

        # Build search terms (same multi-search strategy as run_enrichment.py)
        search_terms = []
        if has_instagram and row.get("instagram_url"):
            ig_username = extract_instagram_username(row["instagram_url"])
            if ig_username:
                search_terms.append(ig_username)
        if has_domain and row.get("domain"):
            # Use domain root as brand name (e.g., "pinkrose" from "pinkrose.com.co")
            brand_from_domain = row["domain"].split(".")[0].replace("-", " ").title()
            if brand_from_domain and brand_from_domain not in search_terms:
                search_terms.append(brand_from_domain)

        if not search_terms:
            print(f"  [{i+1}/{total}] {domain_str}: SKIP (no search terms)")
            skipped += 1
            results.append({"row": row_num, "domain": domain_str, "status": "skip", "count": None})
            continue

        # Check if already backfilled
        existing = row.get(TARGET_COLUMN_NAME)
        if existing not in (None, "", "N/A"):
            print(f"  [{i+1}/{total}] {domain_str}: SKIP (already has value: {existing})")
            skipped += 1
            results.append({"row": row_num, "domain": domain_str, "status": "existing", "count": existing})
            continue

        if dry_run:
            print(f"  [{i+1}/{total}] {domain_str}: WOULD query (terms={search_terms})")
            continue

        # Call multi-search (tries all terms, returns highest count)
        print(f"  [{i+1}/{total}] {domain_str}: querying (terms={search_terms})...", end=" ", flush=True)
        meta_result = get_meta_ads_multi_search(search_terms, country="CO")

        if meta_result["success"]:
            count = meta_result["data"]["active_ads_count"]
            print(f"OK ({count} ads)")
            succeeded += 1
            results.append({"row": row_num, "domain": domain_str, "status": "ok", "count": count})

            # Write to sheet
            worksheet.update_cell(row_num, col_index, count)
        else:
            error = meta_result["error"]
            print(f"FAIL ({error[:80]})")
            failed += 1
            results.append({"row": row_num, "domain": domain_str, "status": "fail", "error": error})

        # Rate limiting
        time.sleep(delay)

    # Step 6: Save backup
    with open(backup_path, "w") as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "sheet": WORKSHEET_NAME,
            "total": total,
            "succeeded": succeeded,
            "failed": failed,
            "skipped": skipped,
            "results": results,
        }, f, indent=2)

    # Summary
    print(f"\n{'='*60}")
    print(f"SUMMARY {'(DRY RUN)' if dry_run else ''}")
    print(f"  Total: {total}")
    print(f"  Succeeded: {succeeded}")
    print(f"  Failed: {failed}")
    print(f"  Skipped: {skipped}")
    if not dry_run:
        print(f"  Backup saved to: {backup_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backfill META ads count for training data")
    parser.add_argument("--dry-run", action="store_true", help="Preview without making APIFY calls")
    parser.add_argument("--delay", type=float, default=DEFAULT_DELAY, help=f"Seconds between API calls (default: {DEFAULT_DELAY})")
    args = parser.parse_args()

    backfill(dry_run=args.dry_run, delay=args.delay)
