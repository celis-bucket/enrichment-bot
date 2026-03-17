"""
Backfill site_serp_coverage_score (and refresh brand_demand_score) for training data.

Reads the training Google Sheet (colombia_175), runs score_google_demand()
for each store, and writes site_serp_coverage_score + brand_demand_score back.

Cost: 3 Serper queries per company (free tier: 2,500/month).
      142 companies × 3 = 426 queries.

Usage:
    python -m tools.orders_estimator.backfill_serp_coverage [--dry-run] [--delay SECONDS]
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

from google_demand.score_demand import score_google_demand
from export.google_sheets_writer import get_gspread_client
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
SHEET_URL = "https://docs.google.com/spreadsheets/d/1si5LxiXiaz0N5vh_w8LgGFnQ6ngpHX2UijTCLS_H1-o/"
WORKSHEET_NAME = "colombia_175"
SERP_COLUMN_NAME = "site_serp_coverage_score"
DEMAND_COLUMN_NAME = "brand_demand_score"
DEFAULT_DELAY = 2  # seconds between Serper calls (conservative)
BACKUP_DIR = os.path.join(os.path.dirname(__file__), "..", "..", ".tmp", "orders_estimator", "datasets")


def _ensure_column(worksheet, headers, column_name):
    """Ensure a column exists in the sheet, return its 1-based index."""
    if column_name in headers:
        return headers.index(column_name) + 1
    col_index = len(headers) + 1
    worksheet.update_cell(1, col_index, column_name)
    headers.append(column_name)
    return col_index


def backfill(dry_run: bool = False, delay: float = DEFAULT_DELAY):
    """
    Backfill site_serp_coverage_score and refresh brand_demand_score
    for all stores in the training sheet.

    Steps:
        1. Read sheet data
        2. For each store: extract domain + brand name
        3. Call score_google_demand(brand_name, domain, country="co")
        4. Write site_serp_coverage_score and brand_demand_score back to sheet
    """
    print(f"SERP Coverage Backfill {'(DRY RUN)' if dry_run else ''}")
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

    # Step 2: Verify required columns exist
    # The sheet uses "domain (Seller key)" or "domain" for the domain column
    domain_col = None
    for candidate in ["domain", "domain (Seller key)"]:
        if candidate in headers:
            domain_col = candidate
            break

    brand_col = None
    for candidate in ["Nombre", "company_name"]:
        if candidate in headers:
            brand_col = candidate
            break

    print(f"Domain column: {domain_col}")
    print(f"Brand name column: {brand_col}")

    if not domain_col:
        print("ERROR: No domain column found in sheet")
        return

    # Step 3: Ensure target columns exist
    if not dry_run:
        serp_col_index = _ensure_column(worksheet, headers, SERP_COLUMN_NAME)
        demand_col_index = _ensure_column(worksheet, headers, DEMAND_COLUMN_NAME)
    else:
        serp_col_index = headers.index(SERP_COLUMN_NAME) + 1 if SERP_COLUMN_NAME in headers else len(headers) + 1
        demand_col_index = headers.index(DEMAND_COLUMN_NAME) + 1 if DEMAND_COLUMN_NAME in headers else len(headers) + 2

    print(f"'{SERP_COLUMN_NAME}' at column {serp_col_index}")
    print(f"'{DEMAND_COLUMN_NAME}' at column {demand_col_index}")

    # Step 4: Save local backup
    os.makedirs(BACKUP_DIR, exist_ok=True)
    backup_path = os.path.join(BACKUP_DIR, f"backfill_serp_coverage_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
    results = []

    # Step 5: Process each row
    total = len(all_data)
    succeeded = 0
    failed = 0
    skipped = 0

    for i, row in enumerate(all_data):
        row_num = i + 2  # 1-indexed, skip header

        domain = row.get(domain_col, "")
        brand_name = row.get(brand_col, "") if brand_col else ""

        if not domain:
            print(f"  [{i+1}/{total}] row_{row_num}: SKIP (no domain)")
            skipped += 1
            results.append({"row": row_num, "domain": "", "status": "skip", "reason": "no_domain"})
            continue

        # Check if SERP coverage already backfilled
        existing_serp = row.get(SERP_COLUMN_NAME)
        if existing_serp not in (None, "", "N/A", 0, "0"):
            print(f"  [{i+1}/{total}] {domain}: SKIP (already has serp_coverage: {existing_serp})")
            skipped += 1
            results.append({"row": row_num, "domain": domain, "status": "existing", "serp": existing_serp})
            continue

        # Use brand name or derive from domain
        if not brand_name:
            brand_name = domain.split(".")[0].replace("-", " ").title()

        if dry_run:
            print(f"  [{i+1}/{total}] {domain}: WOULD query (brand='{brand_name}')")
            continue

        # Call Google Demand scoring
        print(f"  [{i+1}/{total}] {domain}: querying (brand='{brand_name}')...", end=" ", flush=True)
        result = score_google_demand(brand_name, domain, country="co")

        if result["success"]:
            serp_score = result["data"]["site_serp_coverage_score"]
            demand_score = result["data"]["brand_demand_score"]
            confidence = result["data"]["google_confidence"]
            print(f"OK (serp={serp_score:.3f}, demand={demand_score:.3f}, conf={confidence:.2f})")
            succeeded += 1
            results.append({
                "row": row_num, "domain": domain, "status": "ok",
                "serp_coverage": serp_score, "brand_demand": demand_score,
                "confidence": confidence,
            })

            # Write both columns to sheet
            worksheet.update_cell(row_num, serp_col_index, round(serp_score, 4))
            worksheet.update_cell(row_num, demand_col_index, round(demand_score, 4))
        else:
            error = result["error"]
            print(f"FAIL ({error[:80]})")
            failed += 1
            results.append({"row": row_num, "domain": domain, "status": "fail", "error": error})

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
    print(f"  Serper queries used: ~{succeeded * 3}")
    if not dry_run:
        print(f"  Backup saved to: {backup_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backfill SERP coverage score for training data")
    parser.add_argument("--dry-run", action="store_true", help="Preview without making API calls")
    parser.add_argument("--delay", type=float, default=DEFAULT_DELAY, help=f"Seconds between API calls (default: {DEFAULT_DELAY})")
    args = parser.parse_args()

    backfill(dry_run=args.dry_run, delay=args.delay)
