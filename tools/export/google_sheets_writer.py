"""
Google Sheets Writer Tool

Purpose: Create/open Google Sheets and write enrichment results in chunks.
Inputs: Authenticated gspread client, spreadsheet URL (optional), rows of data.
Outputs: Sheet URL, row write confirmations.
Dependencies: gspread, google-auth, python-dotenv
"""

import os
import sys
import json
from datetime import datetime
from typing import Dict, Any, Optional, Set

import gspread
from dotenv import load_dotenv

load_dotenv()

# Import new schema headers (single source of truth)
_TOOLS_DIR = os.path.join(os.path.dirname(__file__), "..")
if _TOOLS_DIR not in sys.path:
    sys.path.insert(0, _TOOLS_DIR)

from models.enrichment_result import SHEET_HEADERS as V2_SHEET_HEADERS

# Legacy 26-column headers (kept for backward compatibility with old sheets)
SHEET_HEADERS_LEGACY = [
    "Clean URL", "CMS", "CMS Confidence", "Geography", "Geography Confidence",
    "Instagram URL", "Instagram Followers", "Instagram Engagement Rate",
    "Instagram Size Score", "Instagram Health Score", "Product Count",
    "Average Price", "Price Range", "Workflow Execution Log",
    "Estimated Monthly Traffic", "Traffic Confidence", "Sitemap Size",
    "Review Count", "Contact Name", "Contact Title", "Contact Email",
    "Contact Phone", "Company LinkedIn", "Current Fulfillment Provider",
    "Detected Carriers", "Shipping Options",
]

# Default to new V2 headers for new sheets
SHEET_HEADERS = V2_SHEET_HEADERS

DEFAULT_SHEET_TITLE_PREFIX = os.getenv("DEFAULT_SHEET_TITLE_PREFIX", "Ecommerce Batch")


def get_gspread_client() -> gspread.Client:
    """
    Authenticate with Google Sheets using service account credentials.

    Tries (in order):
    1. GOOGLE_SERVICE_ACCOUNT_JSON env var (raw JSON string)
    2. GOOGLE_APPLICATION_CREDENTIALS env var (file path)
    3. Default gspread location (~/.config/gspread/service_account.json)

    Returns:
        Authenticated gspread.Client

    Raises:
        RuntimeError: if no valid credentials are found
    """
    # Option 1: raw JSON string in env var
    raw_json = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
    if raw_json:
        try:
            creds_dict = json.loads(raw_json)
            return gspread.service_account_from_dict(creds_dict)
        except (json.JSONDecodeError, Exception) as e:
            raise RuntimeError(f"Failed to parse GOOGLE_SERVICE_ACCOUNT_JSON: {e}")

    # Option 2: file path in env var
    creds_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    if creds_path and os.path.exists(creds_path):
        try:
            return gspread.service_account(filename=creds_path)
        except Exception as e:
            raise RuntimeError(f"Failed to load credentials from {creds_path}: {e}")

    # Option 3: default gspread location
    try:
        return gspread.service_account()
    except Exception as e:
        raise RuntimeError(
            "No Google service account credentials found. "
            "Set GOOGLE_SERVICE_ACCOUNT_JSON or GOOGLE_APPLICATION_CREDENTIALS. "
            f"Details: {e}"
        )


def create_or_open_spreadsheet(
    client: gspread.Client,
    spreadsheet_url: Optional[str] = None,
    title: Optional[str] = None,
    batch_id_short: Optional[str] = None,
    worksheet_name: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Create a new spreadsheet or open an existing one.
    Writes header row if the target worksheet is empty.

    Args:
        client: Authenticated gspread client
        spreadsheet_url: Optional URL of existing spreadsheet
        title: Custom title (ignored if spreadsheet_url provided)
        batch_id_short: Short batch ID for default title
        worksheet_name: Optional worksheet tab name. If provided and the
            spreadsheet already exists, creates or opens this tab instead
            of using sheet1.

    Returns:
        {success, data: {spreadsheet, worksheet, sheet_url}, error}
    """
    try:
        if spreadsheet_url:
            spreadsheet = client.open_by_url(spreadsheet_url)
        else:
            if not title:
                date_str = datetime.now().strftime("%m/%d/%Y")
                bid = batch_id_short or "new"
                title = f"{DEFAULT_SHEET_TITLE_PREFIX} - {date_str} - {bid}"
            spreadsheet = client.create(title)
            # Share as "anyone with the link can view"
            spreadsheet.share("", perm_type="anyone", role="reader")

        # Select or create the target worksheet
        if worksheet_name:
            try:
                worksheet = spreadsheet.worksheet(worksheet_name)
            except gspread.exceptions.WorksheetNotFound:
                worksheet = spreadsheet.add_worksheet(
                    title=worksheet_name, rows=1000, cols=len(SHEET_HEADERS)
                )
        else:
            worksheet = spreadsheet.sheet1
            if worksheet.title == "Sheet1":
                worksheet.update_title("results")

        # Write headers if first row is empty
        first_row = worksheet.row_values(1)
        if not first_row:
            worksheet.append_row(SHEET_HEADERS, value_input_option="USER_ENTERED")

        return {
            "success": True,
            "data": {
                "spreadsheet": spreadsheet,
                "worksheet": worksheet,
                "sheet_url": spreadsheet.url,
            },
            "error": None,
        }

    except Exception as e:
        return {
            "success": False,
            "data": {},
            "error": f"Google Sheets error: {str(e)}",
        }


def append_rows(worksheet, rows: list) -> Dict[str, Any]:
    """
    Append multiple rows to the worksheet.

    Uses USER_ENTERED so numbers are treated as numbers in Sheets.

    Args:
        worksheet: gspread Worksheet object
        rows: List of row data (each row is a list of values)

    Returns:
        {success, data: {rows_written}, error}
    """
    try:
        if not rows:
            return {"success": True, "data": {"rows_written": 0}, "error": None}

        worksheet.append_rows(rows, value_input_option="USER_ENTERED")
        return {
            "success": True,
            "data": {"rows_written": len(rows)},
            "error": None,
        }

    except Exception as e:
        return {
            "success": False,
            "data": {"rows_written": 0},
            "error": f"Failed to append rows: {str(e)}",
        }


def read_existing_domains(worksheet) -> Set[str]:
    """
    Read all domains from the 'domain' column to support batch resume.

    Returns:
        Set of lowercase domain strings already in the sheet.
    """
    try:
        domain_col_index = SHEET_HEADERS.index("domain") + 1  # gspread is 1-indexed
        values = worksheet.col_values(domain_col_index)
        # Skip header row
        return set(v.strip().lower() for v in values[1:] if v.strip())
    except Exception:
        return set()


def enrichment_result_to_row_v2(result) -> list:
    """
    Convert an EnrichmentResult dataclass to a row list matching V2_SHEET_HEADERS.

    Args:
        result: EnrichmentResult instance (has .to_row() method)

    Returns:
        List of values matching SHEET_HEADERS column order.
    """
    return result.to_row()


# --- Legacy function (backward compatibility) ---

def enrichment_result_to_row(result: dict) -> list:
    """
    LEGACY: Convert a flat enrichment result dict into a 26-element list
    matching SHEET_HEADERS_LEGACY.

    Args:
        result: Dict with keys like url, cms, cms_confidence, geography, etc.

    Returns:
        List of 26 values. Missing/None values become empty string.
    """
    def fmt(val):
        if val is None:
            return ""
        return val

    def fmt_confidence(val):
        if val is None:
            return ""
        return round(val, 2)

    def fmt_pct(val):
        if val is None:
            return ""
        return round(val, 2)

    return [
        fmt(result.get("url")),
        fmt(result.get("cms")),
        fmt_confidence(result.get("cms_confidence")),
        fmt(result.get("geography")),
        fmt_confidence(result.get("geography_confidence")),
        fmt(result.get("instagram_url")),
        fmt(result.get("instagram_followers")),
        fmt_pct(result.get("instagram_engagement_rate")),
        fmt(result.get("instagram_size_score")),
        fmt(result.get("instagram_health_score")),
        fmt(result.get("product_count")),
        fmt(result.get("avg_price")),
        fmt(result.get("price_range")),
        fmt(result.get("workflow_log")),
        fmt(result.get("estimated_monthly_traffic")),
        fmt_confidence(result.get("traffic_confidence")),
        fmt(result.get("sitemap_size")),
        fmt(result.get("review_count")),
        fmt(result.get("contact_name")),
        fmt(result.get("contact_title")),
        fmt(result.get("contact_email")),
        fmt(result.get("contact_phone")),
        fmt(result.get("company_linkedin")),
        fmt(result.get("fulfillment_provider")),
        fmt(result.get("detected_carriers")),
        fmt(result.get("shipping_options")),
    ]


if __name__ == "__main__":
    # Quick smoke test
    print("Testing Google Sheets Writer...")
    print("=" * 50)

    try:
        client = get_gspread_client()
        print("[OK] Authenticated with Google Sheets")

        result = create_or_open_spreadsheet(client, batch_id_short="test")
        if result["success"]:
            print(f"[OK] Created spreadsheet: {result['data']['sheet_url']}")
            ws = result["data"]["worksheet"]

            # Test row with V2 schema
            from models.enrichment_result import EnrichmentResult
            test_er = EnrichmentResult(
                clean_url="https://example.com",
                domain="example.com",
                platform="shopify",
                platform_confidence=0.95,
                geography="COL",
                geography_confidence=0.87,
                category="Ropa",
                category_confidence=0.92,
                ig_followers=15000,
            )
            row = enrichment_result_to_row_v2(test_er)
            append_result = append_rows(ws, [row])
            if append_result["success"]:
                print(f"[OK] Appended {append_result['data']['rows_written']} test row(s)")
            else:
                print(f"[FAIL] {append_result['error']}")
        else:
            print(f"[FAIL] {result['error']}")

    except Exception as e:
        print(f"[FAIL] {e}")
