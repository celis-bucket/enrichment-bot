"""
Backfill Potential Scores

Reads all companies from enriched_companies, computes potential scores,
and batch-updates Supabase. Safe to run multiple times (idempotent).

Usage:
    cd tools && python -m scoring.backfill_scores
    cd tools && python -m scoring.backfill_scores --dry-run
"""

import os
import sys
import argparse

_tools_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _tools_dir not in sys.path:
    sys.path.insert(0, _tools_dir)

from scoring.potential_scoring import score_company
from export.supabase_writer import get_client

TABLE = "enriched_companies"

# Columns needed for scoring
SCORE_COLUMNS = (
    "domain,geography,category,"
    "predicted_orders_p90,brand_demand_score,"
    "has_multibrand_stores,multibrand_store_names,"
    "has_own_stores,own_store_count_col,own_store_count_mex,"
    "on_mercadolibre,on_amazon,on_rappi,on_walmart,on_liverpool,on_coppel,"
    "overall_potential_score"
)


def backfill(dry_run: bool = False, force: bool = False):
    """Score all companies and update Supabase."""
    client = get_client()

    # Fetch all companies
    print("Fetching companies from Supabase...")
    rows = client.select(TABLE, columns=SCORE_COLUMNS, limit=5000)
    print(f"Found {len(rows)} companies")

    updated = 0
    skipped = 0
    errors = 0

    for row in rows:
        domain = row.get("domain")
        if not domain:
            continue

        # Skip if already scored (unless --force)
        if not force and row.get("overall_potential_score") is not None:
            skipped += 1
            continue

        try:
            scores = score_company(row)
            tier = scores["potential_tier"]
            overall = scores["overall_potential_score"]

            if dry_run:
                print(f"  [DRY] {domain:40s} -> {tier:15s} overall={overall} "
                      f"size={scores['combined_size_score']} fit={scores['fit_score']}")
            else:
                import requests
                resp = requests.patch(
                    f"{client.rest_url}/{TABLE}",
                    headers=client.headers,
                    params={"domain": f"eq.{domain}"},
                    json=scores,
                    timeout=15,
                )
                resp.raise_for_status()
                print(f"  [OK]  {domain:40s} -> {tier:15s} overall={overall}")

            updated += 1

        except Exception as e:
            print(f"  [ERR] {domain}: {e}")
            errors += 1

    print(f"\nDone: {updated} updated, {skipped} skipped (already scored), {errors} errors")
    if dry_run:
        print("(dry run — no changes written)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backfill potential scores for all companies")
    parser.add_argument("--dry-run", action="store_true", help="Print scores without writing")
    parser.add_argument("--force", action="store_true", help="Re-score even if already scored")
    args = parser.parse_args()

    backfill(dry_run=args.dry_run, force=args.force)
