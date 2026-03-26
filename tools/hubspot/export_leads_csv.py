"""
Export HubSpot company IDs to CSV with name, website, and Instagram URL.

Usage:
  python export_leads_csv.py empresas_leads.csv output_leads.csv
"""

import os
import sys
import csv
import time
from typing import Optional

import requests
from dotenv import load_dotenv

load_dotenv()

HUBSPOT_API_BASE = "https://api.hubapi.com"
BATCH_SIZE = 100  # HubSpot batch read max


def _get_token() -> Optional[str]:
    return os.getenv("HUBSPOT_TOKEN")


def _headers() -> dict:
    token = _get_token()
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


def batch_read_companies(company_ids: list[str], properties: list[str]) -> list[dict]:
    """
    Batch read companies from HubSpot.

    POST /crm/v3/objects/companies/batch/read
    Max 100 IDs per request.
    """
    url = f"{HUBSPOT_API_BASE}/crm/v3/objects/companies/batch/read"
    results = []

    for i in range(0, len(company_ids), BATCH_SIZE):
        batch = company_ids[i:i + BATCH_SIZE]
        body = {
            "properties": properties,
            "inputs": [{"id": cid} for cid in batch],
        }

        for attempt in range(3):
            try:
                resp = requests.post(url, headers=_headers(), json=body, timeout=30)

                if resp.status_code == 429:
                    retry_after = int(resp.headers.get("Retry-After", 5))
                    print(f"  Rate limited, waiting {retry_after}s...")
                    time.sleep(retry_after)
                    continue

                resp.raise_for_status()
                data = resp.json()
                batch_results = data.get("results", [])
                results.extend(batch_results)
                print(f"  Batch {i // BATCH_SIZE + 1}: {len(batch_results)} companies fetched")
                break

            except requests.exceptions.RequestException as e:
                if attempt < 2:
                    print(f"  Retry {attempt + 1}: {e}")
                    time.sleep(2)
                else:
                    print(f"  FAILED batch starting at {i}: {e}")

        # Small delay between batches to respect rate limits
        time.sleep(0.3)

    return results


def read_company_ids(file_path: str) -> list[str]:
    """Read company IDs from CSV file, deduplicate."""
    ids = []
    for encoding in ["utf-8-sig", "utf-8", "latin-1"]:
        try:
            with open(file_path, "r", encoding=encoding) as f:
                reader = csv.reader(f)
                header = next(reader, None)  # skip header
                for row in reader:
                    if row and row[0].strip().isdigit():
                        ids.append(row[0].strip())
            break
        except UnicodeDecodeError:
            continue

    # Deduplicate preserving order
    seen = set()
    unique = []
    for cid in ids:
        if cid not in seen:
            seen.add(cid)
            unique.append(cid)

    return unique


def main():
    input_file = sys.argv[1] if len(sys.argv) > 1 else "empresas_leads.csv"
    output_file = sys.argv[2] if len(sys.argv) > 2 else ".tmp/leads_for_lite.csv"

    if not _get_token():
        print("ERROR: HUBSPOT_TOKEN not set in environment")
        sys.exit(1)

    print(f"Reading company IDs from: {input_file}")
    company_ids = read_company_ids(input_file)
    print(f"  Total unique IDs: {len(company_ids)}")

    print(f"\nFetching from HubSpot ({len(company_ids)} companies in batches of {BATCH_SIZE})...")
    properties = ["name", "domain", "website", "instagram", "instagram_new"]

    results = batch_read_companies(company_ids, properties)
    print(f"\n  Total fetched: {len(results)}")

    # Build CSV rows
    rows = []
    no_name = 0
    no_website = 0
    no_ig = 0

    for company in results:
        props = company.get("properties", {})
        cid = company.get("id", "")

        name = (props.get("name") or "").strip()
        domain = (props.get("domain") or "").strip()
        website = (props.get("website") or "").strip()
        ig = (props.get("instagram") or "").strip()
        ig_username = (props.get("instagram_new") or "").strip()
        # Build IG URL from username if URL field is empty
        if not ig and ig_username:
            ig = f"https://instagram.com/{ig_username}"

        # Build website URL from domain if website is empty
        if not website and domain:
            website = f"https://{domain}"

        if not name:
            no_name += 1
        if not website and not domain:
            no_website += 1
        if not ig:
            no_ig += 1

        rows.append({
            "hubspot_id": cid,
            "company_name": name,
            "website_url": website,
            "instagram_url": ig,
        })

    # Save CSV
    os.makedirs(os.path.dirname(output_file) or ".", exist_ok=True)
    with open(output_file, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["hubspot_id", "company_name", "website_url", "instagram_url"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nCSV saved: {output_file}")
    print(f"  Total rows: {len(rows)}")
    print(f"  With name: {len(rows) - no_name}")
    print(f"  With website/domain: {len(rows) - no_website}")
    print(f"  With Instagram: {len(rows) - no_ig}")
    print(f"  Missing name: {no_name}")
    print(f"  Missing website: {no_website}")
    print(f"  Missing Instagram: {no_ig}")


if __name__ == "__main__":
    main()
