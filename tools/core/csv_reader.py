"""
CSV Lead Reader

Purpose: Parse CSV files with company name + URLs for lite enrichment.
Inputs: CSV file path (HubSpot export or similar)
Outputs: Cleaned, deduplicated list of leads with classified URL types
Dependencies: tools/core/url_normalizer.py, tools/social/apify_instagram.py

Handles noisy real-world data: empty fields, broken URLs, BOM encoding,
mixed website/Instagram URLs in the same column.
"""

import csv
import os
import re
import sys
from typing import Dict, Any, Optional, List

_TOOLS_DIR = os.path.join(os.path.dirname(__file__), "..")
if _TOOLS_DIR not in sys.path:
    sys.path.insert(0, _TOOLS_DIR)

from core.url_normalizer import normalize_url, extract_domain
from social.apify_instagram import extract_instagram_username

# Keywords for auto-detecting columns (lowercase)
_NAME_KEYWORDS = ["name", "company", "nombre", "empresa", "brand", "marca", "negocio"]
_WEBSITE_KEYWORDS = ["website", "web", "url", "sitio", "domain", "dominio", "pagina", "página"]
_IG_KEYWORDS = ["instagram", "ig", "insta"]


def _detect_columns(headers: List[str]) -> Dict[str, Optional[int]]:
    """Auto-detect column indices from header names."""
    result = {"name": None, "website": None, "instagram": None}
    lower_headers = [h.lower().strip() for h in headers]

    for i, h in enumerate(lower_headers):
        # Instagram first (more specific — "instagram url" contains "url")
        if result["instagram"] is None and any(kw in h for kw in _IG_KEYWORDS):
            result["instagram"] = i
        elif result["website"] is None and any(kw in h for kw in _WEBSITE_KEYWORDS):
            result["website"] = i
        elif result["name"] is None and any(kw in h for kw in _NAME_KEYWORDS):
            result["name"] = i

    return result


def _is_instagram_url(url: str) -> bool:
    """Check if a URL is an Instagram URL."""
    return bool(re.search(r"instagram\.com/", url, re.IGNORECASE))


def _clean_field(value: str) -> str:
    """Strip whitespace and common noise from a field value."""
    if not value:
        return ""
    cleaned = value.strip().strip('"').strip("'").strip()
    if cleaned.lower() in ("n/a", "na", "none", "null", "-", "--", "sin url", "no tiene"):
        return ""
    return cleaned


def read_csv_leads(
    file_path: str,
    name_col: str = None,
    website_col: str = None,
    ig_col: str = None,
) -> Dict[str, Any]:
    """
    Read a CSV file with company name and URL columns.

    Auto-detects column names if not specified. Handles BOM, encoding
    issues, empty rows, and noisy data typical of HubSpot exports.

    Args:
        file_path: Path to CSV file
        name_col: Explicit name column header (auto-detect if None)
        website_col: Explicit website URL column header (auto-detect if None)
        ig_col: Explicit Instagram URL column header (auto-detect if None)

    Returns:
        Standard tool dict: {success, data, error}
        data.leads: List of {company_name, website_url, instagram_url,
                             instagram_username, row_number}
    """
    try:
        if not os.path.exists(file_path):
            return {"success": False, "data": {}, "error": f"File not found: {file_path}"}

        # Read file with encoding fallback
        content = None
        for encoding in ["utf-8-sig", "utf-8", "latin-1"]:
            try:
                with open(file_path, "r", encoding=encoding) as f:
                    content = f.read()
                break
            except UnicodeDecodeError:
                continue

        if content is None:
            return {"success": False, "data": {}, "error": f"Could not read file (encoding error): {file_path}"}

        # Parse CSV
        reader = csv.reader(content.splitlines())
        rows = list(reader)

        if len(rows) < 2:
            return {"success": False, "data": {}, "error": "CSV has no data rows (need header + at least 1 row)"}

        headers = rows[0]

        # Resolve column indices
        if name_col or website_col or ig_col:
            # Explicit column names provided
            lower_headers = [h.lower().strip() for h in headers]
            col_idx = {"name": None, "website": None, "instagram": None}
            if name_col:
                try:
                    col_idx["name"] = lower_headers.index(name_col.lower().strip())
                except ValueError:
                    return {"success": False, "data": {}, "error": f"Column '{name_col}' not found in headers: {headers}"}
            if website_col:
                try:
                    col_idx["website"] = lower_headers.index(website_col.lower().strip())
                except ValueError:
                    return {"success": False, "data": {}, "error": f"Column '{website_col}' not found in headers: {headers}"}
            if ig_col:
                try:
                    col_idx["instagram"] = lower_headers.index(ig_col.lower().strip())
                except ValueError:
                    return {"success": False, "data": {}, "error": f"Column '{ig_col}' not found in headers: {headers}"}
        else:
            col_idx = _detect_columns(headers)

        if col_idx["name"] is None and col_idx["website"] is None and col_idx["instagram"] is None:
            return {
                "success": False,
                "data": {},
                "error": f"Could not auto-detect columns from headers: {headers}. "
                         "Provide name_col, website_col, or ig_col explicitly.",
            }

        # Process data rows
        leads = []
        empty_rows = 0
        duplicates_removed = 0
        seen_domains = set()
        seen_ig_usernames = set()

        for row_num, row in enumerate(rows[1:], start=2):
            # Handle short rows
            name = _clean_field(row[col_idx["name"]]) if col_idx["name"] is not None and col_idx["name"] < len(row) else ""
            website = _clean_field(row[col_idx["website"]]) if col_idx["website"] is not None and col_idx["website"] < len(row) else ""
            ig_url = _clean_field(row[col_idx["instagram"]]) if col_idx["instagram"] is not None and col_idx["instagram"] < len(row) else ""

            # Skip completely empty rows
            if not name and not website and not ig_url:
                empty_rows += 1
                continue

            # Check if website column actually contains an Instagram URL
            if website and _is_instagram_url(website) and not ig_url:
                ig_url = website
                website = ""

            # Extract Instagram username if IG URL provided
            ig_username = None
            if ig_url:
                ig_username = extract_instagram_username(ig_url)

            # Normalize website for dedup
            domain = None
            if website:
                norm = normalize_url(website)
                if norm["success"]:
                    domain = extract_domain(norm["data"]["url"])

            # Dedup by domain (first occurrence wins)
            if domain:
                domain_key = domain.lower()
                if domain_key in seen_domains:
                    duplicates_removed += 1
                    continue
                seen_domains.add(domain_key)
            elif ig_username:
                # Dedup by IG username if no domain
                ig_key = ig_username.lower()
                if ig_key in seen_ig_usernames:
                    duplicates_removed += 1
                    continue
                seen_ig_usernames.add(ig_key)

            leads.append({
                "company_name": name,
                "website_url": website,
                "instagram_url": ig_url,
                "instagram_username": ig_username,
                "row_number": row_num,
            })

        return {
            "success": True,
            "data": {
                "leads": leads,
                "total_rows": len(rows) - 1,
                "valid_leads": len(leads),
                "duplicates_removed": duplicates_removed,
                "empty_rows_skipped": empty_rows,
                "detected_columns": {
                    "name": headers[col_idx["name"]] if col_idx["name"] is not None else None,
                    "website": headers[col_idx["website"]] if col_idx["website"] is not None else None,
                    "instagram": headers[col_idx["instagram"]] if col_idx["instagram"] is not None else None,
                },
            },
            "error": None,
        }

    except Exception as e:
        return {"success": False, "data": {}, "error": f"CSV reader error: {str(e)}"}


if __name__ == "__main__":
    file_path = sys.argv[1] if len(sys.argv) > 1 else "leads.csv"

    print("CSV Lead Reader")
    print("=" * 60)
    print(f"File: {file_path}")

    result = read_csv_leads(file_path)
    print(f"\nSuccess: {result['success']}")

    if result["success"]:
        data = result["data"]
        print(f"  Total rows: {data['total_rows']}")
        print(f"  Valid leads: {data['valid_leads']}")
        print(f"  Duplicates removed: {data['duplicates_removed']}")
        print(f"  Empty rows skipped: {data['empty_rows_skipped']}")
        print(f"  Detected columns: {data['detected_columns']}")
        print(f"\n  First 10 leads:")
        for lead in data["leads"][:10]:
            parts = [f"  [{lead['row_number']}]"]
            if lead["company_name"]:
                parts.append(lead["company_name"])
            if lead["website_url"]:
                parts.append(f"web:{lead['website_url'][:40]}")
            if lead["instagram_username"]:
                parts.append(f"ig:@{lead['instagram_username']}")
            print(" | ".join(parts))
        if len(data["leads"]) > 10:
            print(f"  ... and {len(data['leads']) - 10} more")
    else:
        print(f"  Error: {result['error']}")
