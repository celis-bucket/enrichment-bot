"""
Backfill HubSpot Lookup

Runs hubspot_enrich for companies in Supabase that haven't been checked yet
(hubspot_company_id IS NULL and hubspot_contact_exists IS NULL).

Usage:
    cd tools && python -m hubspot.backfill_hubspot
    cd tools && python -m hubspot.backfill_hubspot --dry-run
"""

import os
import sys
import time
import argparse

_tools_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _tools_dir not in sys.path:
    sys.path.insert(0, _tools_dir)

from hubspot.hubspot_lookup import hubspot_enrich
from export.supabase_writer import get_client

TABLE = "enriched_companies"
DELAY_BETWEEN_REQUESTS = 0.2  # seconds


def backfill(dry_run: bool = False):
    """Run HubSpot lookup for companies not yet checked."""
    client = get_client()

    # Fetch companies where HubSpot was never run
    # We check hubspot_contact_exists IS NULL because even companies NOT found
    # in HubSpot get hubspot_contact_exists = 0 after the lookup runs.
    print("Fetching companies without HubSpot data...")
    rows = client.select(
        TABLE,
        columns="domain,company_name,contact_email",
        is_null={"hubspot_contact_exists": True},
        limit=5000,
    )
    print(f"Found {len(rows)} companies to check")

    if not rows:
        print("All companies already have HubSpot data.")
        return

    found = 0
    not_found = 0
    errors = 0

    for i, row in enumerate(rows):
        domain = row.get("domain")
        if not domain:
            continue

        if dry_run:
            print(f"  [{i+1}/{len(rows)}] Would check: {domain}")
            continue

        try:
            result = hubspot_enrich(domain, contact_email=row.get("contact_email"))

            if not result.get("success"):
                print(f"  [{i+1}/{len(rows)}] {domain:40s} -> error: {result.get('error')}")
                errors += 1
                continue

            hs_data = result.get("data", {})
            company_found = hs_data.get("company_found", False)

            # Build PATCH payload
            patch = {
                "hubspot_contact_exists": 1 if hs_data.get("contact_exists") else 0,
            }

            if company_found:
                patch["hubspot_company_id"] = hs_data.get("company_id")
                patch["hubspot_company_url"] = hs_data.get("hubspot_company_url")
                patch["hubspot_deal_count"] = hs_data.get("deal_count", 0)
                patch["hubspot_deal_stage"] = hs_data.get("deal_stage")
                patch["hubspot_lifecycle_label"] = hs_data.get("lifecycle_label")
                patch["hubspot_last_contacted"] = hs_data.get("last_contacted")
                found += 1
                status = f"IN CRM - {hs_data.get('deal_count', 0)} deals"
            else:
                not_found += 1
                status = "not in CRM"

            # PATCH to Supabase
            import requests
            resp = requests.patch(
                f"{client.rest_url}/{TABLE}",
                headers=client.headers,
                params={"domain": f"eq.{domain}"},
                json=patch,
                timeout=15,
            )
            resp.raise_for_status()

            print(f"  [{i+1}/{len(rows)}] {domain:40s} -> {status}")

            # Re-score potential (HubSpot data doesn't affect score, but marks CRM status)
            time.sleep(DELAY_BETWEEN_REQUESTS)

        except Exception as e:
            print(f"  [{i+1}/{len(rows)}] {domain:40s} -> ERROR: {e}")
            errors += 1
            time.sleep(DELAY_BETWEEN_REQUESTS)

    print(f"\nDone: {found} in CRM, {not_found} not in CRM, {errors} errors")
    if dry_run:
        print(f"(dry run -- {len(rows)} companies would be checked)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backfill HubSpot data for unchecked companies")
    parser.add_argument("--dry-run", action="store_true", help="List companies without making API calls")
    args = parser.parse_args()

    backfill(dry_run=args.dry_run)
