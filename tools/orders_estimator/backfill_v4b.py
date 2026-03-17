"""
Backfill V4b features for training data.

Reads the training Google Sheet (colombia_175) and backfills:
  - founded_year: via Apollo org enrichment API (free, no credits)
  - ig_is_verified: via SearchAPI Instagram Profile API
  - fb_followers: via SearchAPI Facebook Business Page API
  - tiktok_followers: via SearchAPI TikTok Profile API

Usage:
    python -m tools.orders_estimator.backfill_v4b [--dry-run] [--delay SECONDS]
    python -m tools.orders_estimator.backfill_v4b --column founded_year
    python -m tools.orders_estimator.backfill_v4b --column ig_is_verified
    python -m tools.orders_estimator.backfill_v4b --column fb_followers
    python -m tools.orders_estimator.backfill_v4b --column tiktok_followers
"""

import os
import sys
import time
import json
import re
import argparse
from datetime import datetime

import requests

_TOOLS_DIR = os.path.join(os.path.dirname(__file__), "..")
if _TOOLS_DIR not in sys.path:
    sys.path.insert(0, _TOOLS_DIR)

from contacts.apollo_enrichment import enrich_company
from export.google_sheets_writer import get_gspread_client
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
SHEET_URL = "https://docs.google.com/spreadsheets/d/1si5LxiXiaz0N5vh_w8LgGFnQ6ngpHX2UijTCLS_H1-o/"
WORKSHEET_NAME = "colombia_175"
DEFAULT_DELAY = 1.5  # seconds between API calls
BACKUP_DIR = os.path.join(os.path.dirname(__file__), "..", "..", ".tmp", "orders_estimator", "datasets")

SEARCHAPI_BASE_URL = "https://www.searchapi.io/api/v1/search"
SEARCHAPI_TOKEN = os.getenv("SEARCHAPI_API_KEY", "")

# All backfillable columns
ALL_COLUMNS = ["founded_year", "ig_is_verified", "fb_followers", "tiktok_followers"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _ensure_column(worksheet, headers: list, col_name: str, dry_run: bool = False) -> int:
    """Ensure column exists in sheet. Returns 1-indexed column position."""
    if col_name in headers:
        return headers.index(col_name) + 1
    col_index = len(headers) + 1
    if not dry_run:
        worksheet.update_cell(1, col_index, col_name)
    headers.append(col_name)
    print(f"  {'Would add' if dry_run else 'Added'} column '{col_name}' at position {col_index}")
    return col_index


def _batch_write_column(worksheet, col_index: int, row_values: dict):
    """Write multiple values to a single column in one batch API call.

    Args:
        worksheet: gspread worksheet
        col_index: 1-indexed column position
        row_values: dict mapping row_num (1-indexed) to value
    """
    if not row_values:
        return
    from gspread import Cell
    cells = []
    for row_num, value in sorted(row_values.items()):
        cells.append(Cell(row=row_num, col=col_index, value=value))
    # Batch update in chunks of 50 to avoid API limits
    chunk_size = 50
    for i in range(0, len(cells), chunk_size):
        chunk = cells[i:i + chunk_size]
        worksheet.update_cells(chunk)
        if i + chunk_size < len(cells):
            time.sleep(1)
    print(f"  Batch-wrote {len(cells)} values to column {col_index}")


def _extract_ig_username(ig_url: str) -> str:
    """Extract Instagram username from URL or raw username."""
    if not ig_url:
        return ""
    ig_url = str(ig_url).strip()
    # Try to extract from URL
    match = re.match(
        r'(?:https?://)?(?:www\.)?instagram\.com/([a-zA-Z0-9_.]+)/?',
        ig_url, re.IGNORECASE
    )
    if match:
        username = match.group(1)
        if username.lower() not in ('p', 'tv', 'reel', 'explore', 'accounts', 'direct', 'stories'):
            return username
    # If no URL pattern, treat as raw username (no slashes)
    if '/' not in ig_url and ig_url:
        return ig_url
    return ""


def _searchapi_call(engine: str, params: dict, timeout: int = 15) -> dict:
    """Call SearchAPI REST API. Returns parsed JSON or error dict."""
    if not SEARCHAPI_TOKEN:
        return {"error": "SEARCHAPI_API_KEY not set in .env"}
    try:
        full_params = {"engine": engine, **params}
        headers = {"Authorization": f"Bearer {SEARCHAPI_TOKEN}"}
        resp = requests.get(
            SEARCHAPI_BASE_URL, params=full_params, headers=headers, timeout=timeout
        )
        if resp.status_code == 200:
            return resp.json()
        elif resp.status_code == 429:
            return {"error": f"Rate limited (429)"}
        else:
            return {"error": f"HTTP {resp.status_code}: {resp.text[:200]}"}
    except requests.exceptions.Timeout:
        return {"error": "Request timed out"}
    except Exception as e:
        return {"error": str(e)}


# ---------------------------------------------------------------------------
# Backfill: founded_year (Apollo)
# ---------------------------------------------------------------------------
def backfill_founded_year(
    worksheet, all_data: list, headers: list,
    dry_run: bool = False, delay: float = DEFAULT_DELAY
) -> dict:
    """Backfill founded_year via Apollo org enrichment."""
    col_index = _ensure_column(worksheet, headers, "founded_year", dry_run)

    total = len(all_data)
    succeeded = 0
    failed = 0
    skipped = 0
    results = []

    for i, row in enumerate(all_data):
        row_num = i + 2
        domain = row.get("domain", row.get("clean_url", ""))

        if not domain:
            print(f"  [{i+1}/{total}] row {row_num}: SKIP (no domain)")
            skipped += 1
            results.append({"row": row_num, "status": "skip"})
            continue

        domain = str(domain).replace("https://", "").replace("http://", "").rstrip("/")

        existing = row.get("founded_year")
        if existing not in (None, "", "N/A", 0, "0"):
            print(f"  [{i+1}/{total}] {domain}: SKIP (already has: {existing})")
            skipped += 1
            results.append({"row": row_num, "domain": domain, "status": "existing", "value": existing})
            continue

        if dry_run:
            print(f"  [{i+1}/{total}] {domain}: WOULD query Apollo")
            continue

        print(f"  [{i+1}/{total}] {domain}: Apollo...", end=" ", flush=True)
        result = enrich_company(domain)

        if result["success"]:
            founded_year = result["data"].get("founded_year")
            if founded_year:
                print(f"OK ({founded_year})")
                worksheet.update_cell(row_num, col_index, int(founded_year))
                succeeded += 1
                results.append({"row": row_num, "domain": domain, "status": "ok", "value": founded_year})
            else:
                print("OK (empty)")
                succeeded += 1
                results.append({"row": row_num, "domain": domain, "status": "ok_empty"})
        else:
            error = result.get("error", "unknown")
            print(f"FAIL ({error[:60]})")
            failed += 1
            results.append({"row": row_num, "domain": domain, "status": "fail", "error": error})
            if "rate limit" in error.lower():
                print("  Rate limited, waiting 30s...")
                time.sleep(30)

        time.sleep(delay)

    return {"column": "founded_year", "total": total, "succeeded": succeeded,
            "failed": failed, "skipped": skipped, "results": results}


# ---------------------------------------------------------------------------
# Backfill: ig_is_verified (SearchAPI Instagram Profile)
# ---------------------------------------------------------------------------
def backfill_ig_is_verified(
    worksheet, all_data: list, headers: list,
    dry_run: bool = False, delay: float = DEFAULT_DELAY
) -> dict:
    """Backfill ig_is_verified via SearchAPI Instagram Profile."""
    col_index = _ensure_column(worksheet, headers, "ig_is_verified", dry_run)

    total = len(all_data)
    succeeded = 0
    failed = 0
    skipped = 0
    results = []
    pending_writes = {}  # row_num -> value

    for i, row in enumerate(all_data):
        row_num = i + 2
        domain = row.get("domain", "")
        ig_username = _extract_ig_username(row.get("instagram_url", ""))

        if not ig_username:
            print(f"  [{i+1}/{total}] {domain}: SKIP (no IG username)")
            skipped += 1
            results.append({"row": row_num, "domain": domain, "status": "skip_no_ig"})
            continue

        existing = row.get("ig_is_verified")
        if existing not in (None, "", "N/A"):
            print(f"  [{i+1}/{total}] {domain}: SKIP (already has: {existing})")
            skipped += 1
            results.append({"row": row_num, "domain": domain, "status": "existing"})
            continue

        if dry_run:
            print(f"  [{i+1}/{total}] {domain}: WOULD query IG @{ig_username}")
            continue

        print(f"  [{i+1}/{total}] {domain}: IG @{ig_username}...", end=" ", flush=True)
        data = _searchapi_call("instagram_profile", {"username": ig_username})

        if "error" in data:
            print(f"FAIL ({data['error'][:60]})")
            failed += 1
            results.append({"row": row_num, "domain": domain, "status": "fail", "error": data["error"]})
            if "429" in str(data["error"]):
                time.sleep(10)
        else:
            profile = data.get("profile") or data
            is_verified = profile.get("is_verified", False)
            verified_int = 1 if is_verified else 0
            print(f"OK (verified={is_verified})")
            pending_writes[row_num] = verified_int
            succeeded += 1
            results.append({"row": row_num, "domain": domain, "status": "ok", "value": verified_int})

        time.sleep(delay)

    # Batch write all results to sheet
    if not dry_run and pending_writes:
        _batch_write_column(worksheet, col_index, pending_writes)

    return {"column": "ig_is_verified", "total": total, "succeeded": succeeded,
            "failed": failed, "skipped": skipped, "results": results}


# ---------------------------------------------------------------------------
# Backfill: fb_followers (SearchAPI Facebook Business Page)
# ---------------------------------------------------------------------------
def backfill_fb_followers(
    worksheet, all_data: list, headers: list,
    dry_run: bool = False, delay: float = DEFAULT_DELAY
) -> dict:
    """Backfill fb_followers via SearchAPI Facebook Business Page.

    Strategy for Facebook username:
    1. Use IG username as Facebook username (common for small brands)
    2. Use brand name from domain as fallback
    """
    col_index = _ensure_column(worksheet, headers, "fb_followers", dry_run)

    total = len(all_data)
    succeeded = 0
    failed = 0
    skipped = 0
    results = []
    pending_writes = {}

    for i, row in enumerate(all_data):
        row_num = i + 2
        domain = row.get("domain", "")

        existing = row.get("fb_followers")
        if existing not in (None, "", "N/A"):
            print(f"  [{i+1}/{total}] {domain}: SKIP (already has: {existing})")
            skipped += 1
            results.append({"row": row_num, "domain": domain, "status": "existing"})
            continue

        # Build list of usernames to try
        usernames_to_try = []
        ig_username = _extract_ig_username(row.get("instagram_url", ""))
        if ig_username:
            usernames_to_try.append(ig_username)
        # Brand name from domain
        if domain:
            brand = str(domain).split(".")[0].replace("-", "")
            if brand and brand not in usernames_to_try:
                usernames_to_try.append(brand)

        if not usernames_to_try:
            print(f"  [{i+1}/{total}] {domain}: SKIP (no username candidates)")
            skipped += 1
            results.append({"row": row_num, "domain": domain, "status": "skip_no_id"})
            continue

        if dry_run:
            print(f"  [{i+1}/{total}] {domain}: WOULD query FB ({usernames_to_try})")
            continue

        # Try each username
        fb_followers = None
        tried = []
        for username in usernames_to_try:
            print(f"  [{i+1}/{total}] {domain}: FB @{username}...", end=" ", flush=True)
            data = _searchapi_call("facebook_business_page", {"username": username})
            tried.append(username)

            if "error" in data:
                print(f"FAIL ({data['error'][:40]})")
                if "429" in str(data["error"]):
                    time.sleep(10)
                time.sleep(delay)
                continue

            # Extract followers
            page = data.get("page", {})
            followers_obj = page.get("followers", {})
            if isinstance(followers_obj, dict):
                fb_followers = followers_obj.get("count")
            elif isinstance(followers_obj, (int, float)):
                fb_followers = int(followers_obj)

            if fb_followers is not None:
                print(f"OK ({fb_followers} followers)")
                break
            else:
                # Page found but no followers data
                print("OK (no followers data)")
                fb_followers = 0
                break

        if fb_followers is not None:
            pending_writes[row_num] = int(fb_followers)
            succeeded += 1
            results.append({"row": row_num, "domain": domain, "status": "ok",
                          "value": fb_followers, "username": tried[-1]})
        else:
            failed += 1
            results.append({"row": row_num, "domain": domain, "status": "fail",
                          "tried": tried})

        time.sleep(delay)

    # Batch write all results to sheet
    if not dry_run and pending_writes:
        _batch_write_column(worksheet, col_index, pending_writes)

    return {"column": "fb_followers", "total": total, "succeeded": succeeded,
            "failed": failed, "skipped": skipped, "results": results}


# ---------------------------------------------------------------------------
# Backfill: tiktok_followers (SearchAPI TikTok Profile)
# ---------------------------------------------------------------------------
def backfill_tiktok_followers(
    worksheet, all_data: list, headers: list,
    dry_run: bool = False, delay: float = DEFAULT_DELAY
) -> dict:
    """Backfill tiktok_followers via SearchAPI TikTok Profile.

    Strategy: try IG username first, then brand name from domain.
    """
    col_index = _ensure_column(worksheet, headers, "tiktok_followers", dry_run)

    total = len(all_data)
    succeeded = 0
    failed = 0
    skipped = 0
    results = []
    pending_writes = {}

    for i, row in enumerate(all_data):
        row_num = i + 2
        domain = row.get("domain", "")

        existing = row.get("tiktok_followers")
        if existing not in (None, "", "N/A"):
            print(f"  [{i+1}/{total}] {domain}: SKIP (already has: {existing})")
            skipped += 1
            results.append({"row": row_num, "domain": domain, "status": "existing"})
            continue

        # Build usernames to try
        usernames_to_try = []
        ig_username = _extract_ig_username(row.get("instagram_url", ""))
        if ig_username:
            usernames_to_try.append(ig_username)
        if domain:
            brand = str(domain).split(".")[0].replace("-", "")
            if brand and brand not in usernames_to_try:
                usernames_to_try.append(brand)

        if not usernames_to_try:
            print(f"  [{i+1}/{total}] {domain}: SKIP (no username candidates)")
            skipped += 1
            results.append({"row": row_num, "domain": domain, "status": "skip_no_id"})
            continue

        if dry_run:
            print(f"  [{i+1}/{total}] {domain}: WOULD query TikTok ({usernames_to_try})")
            continue

        # Try each username
        tiktok_followers = None
        tried = []
        for username in usernames_to_try:
            print(f"  [{i+1}/{total}] {domain}: TT @{username}...", end=" ", flush=True)
            data = _searchapi_call("tiktok_profile", {"username": username})
            tried.append(username)

            if "error" in data:
                print(f"FAIL ({data['error'][:40]})")
                if "429" in str(data["error"]):
                    time.sleep(10)
                time.sleep(delay)
                continue

            # Extract followers from profile
            profile = data.get("profile", {})
            followers = profile.get("followers")

            if followers is not None:
                tiktok_followers = int(followers)
                print(f"OK ({tiktok_followers} followers)")
                break
            else:
                # Profile found but empty? Might be wrong account
                print("OK (no followers data)")
                time.sleep(delay)
                continue

        if tiktok_followers is not None:
            pending_writes[row_num] = tiktok_followers
            succeeded += 1
            results.append({"row": row_num, "domain": domain, "status": "ok",
                          "value": tiktok_followers, "username": tried[-1]})
        else:
            # No TikTok found — write 0 (genuinely no presence)
            pending_writes[row_num] = 0
            succeeded += 1
            results.append({"row": row_num, "domain": domain, "status": "ok_zero",
                          "tried": tried})

        time.sleep(delay)

    # Batch write all results to sheet
    if not dry_run and pending_writes:
        _batch_write_column(worksheet, col_index, pending_writes)

    return {"column": "tiktok_followers", "total": total, "succeeded": succeeded,
            "failed": failed, "skipped": skipped, "results": results}


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------
BACKFILL_FUNCS = {
    "founded_year": backfill_founded_year,
    "ig_is_verified": backfill_ig_is_verified,
    "fb_followers": backfill_fb_followers,
    "tiktok_followers": backfill_tiktok_followers,
}


def backfill(
    columns: list = None,
    dry_run: bool = False,
    delay: float = DEFAULT_DELAY,
):
    """Run backfill for specified columns (default: all)."""
    columns = columns or ALL_COLUMNS

    print(f"V4b Feature Backfill {'(DRY RUN)' if dry_run else ''}")
    print("=" * 60)
    print(f"Columns: {columns}")

    # Check SearchAPI token
    if not SEARCHAPI_TOKEN:
        searchapi_cols = [c for c in columns if c != "founded_year"]
        if searchapi_cols:
            print(f"WARNING: SEARCHAPI_API_KEY not set. Cannot backfill: {searchapi_cols}")

    # Read sheet
    client = get_gspread_client()
    spreadsheet = client.open_by_url(SHEET_URL)
    worksheet = spreadsheet.worksheet(WORKSHEET_NAME)
    all_data = worksheet.get_all_records()
    headers = worksheet.row_values(1)

    print(f"Sheet: {WORKSHEET_NAME}")
    print(f"Rows: {len(all_data)}")

    os.makedirs(BACKUP_DIR, exist_ok=True)
    all_results = {}

    for col in columns:
        print(f"\n{'-'*60}")
        print(f"Backfilling: {col}")
        print(f"{'-'*60}")

        func = BACKFILL_FUNCS.get(col)
        if not func:
            print(f"  Unknown column: {col}")
            continue

        result = func(worksheet, all_data, headers, dry_run, delay)
        all_results[col] = result
        print(f"\n  {col}: {result['succeeded']} OK, {result['failed']} FAIL, {result['skipped']} SKIP")

    # Save backup
    backup_path = os.path.join(
        BACKUP_DIR,
        f"backfill_v4b_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    )
    if not dry_run:
        with open(backup_path, "w") as f:
            json.dump({
                "timestamp": datetime.now().isoformat(),
                "sheet": WORKSHEET_NAME,
                "columns": columns,
                "results": all_results,
            }, f, indent=2, default=str)
        print(f"\nBackup saved to: {backup_path}")

    print(f"\n{'='*60}")
    print("BACKFILL COMPLETE")
    print(f"{'='*60}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backfill V4b features for training data")
    parser.add_argument("--dry-run", action="store_true", help="Preview without making API calls")
    parser.add_argument("--delay", type=float, default=DEFAULT_DELAY,
                       help=f"Seconds between API calls (default: {DEFAULT_DELAY})")
    parser.add_argument("--column", type=str, choices=ALL_COLUMNS,
                       help="Backfill specific column only")
    args = parser.parse_args()

    columns = [args.column] if args.column else None
    backfill(columns=columns, dry_run=args.dry_run, delay=args.delay)
