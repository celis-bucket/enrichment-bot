"""
Batch Upgrade Lite → Full Enrichment

Purpose: Re-enrich leads that only have lite enrichment with the full pipeline.
Unlike batch_runner.py, this does NOT skip existing domains — it specifically
targets domains that are already in the database with enrichment_type='lite'.

Usage:
  python batch_upgrade_lite.py --owner "Alejandra Gil Rivera" --country Colombia
  python batch_upgrade_lite.py --input domains.txt --country Colombia
  python batch_upgrade_lite.py --owner "Alejandra Gil Rivera" --country Colombia --dry-run 5
"""

import os
import sys
import time
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from orchestrator.run_enrichment import run_enrichment
from export.supabase_writer import get_client as get_supabase_client, upsert_enrichment


def _run_prediction(result):
    """Run orders prediction if model is available."""
    try:
        from orders_estimator.predict import predict_single
        pred = predict_single(result.to_dict())
        if pred and pred.get("predicted_orders_p50"):
            return pred
    except Exception:
        pass
    return None


def get_lite_domains(sb_client, owner: str | None = None) -> list[dict]:
    """Get domains with lite enrichment, optionally filtered by owner."""
    eq = {"source": "hubspot_leads", "enrichment_type": "lite"}
    if owner:
        eq["hs_lead_owner"] = owner
    rows = sb_client.select(
        "enriched_companies",
        columns="domain,geography",
        eq=eq,
    )
    return [r for r in rows if r.get("domain")]


def main():
    parser = argparse.ArgumentParser(description="Upgrade lite-enriched leads to full enrichment")
    parser.add_argument("--owner", default=None, help="Filter by lead owner name")
    parser.add_argument("--input", default=None, help="Path to domain list file (alternative to --owner)")
    parser.add_argument("--country", default="Colombia", help="Country context (default: Colombia)")
    parser.add_argument("--dry-run", type=int, default=0, help="Process only N leads")
    parser.add_argument("--skip-cache", action="store_true", help="Bypass cache")
    parser.add_argument("--batch-id", default=None, help="Custom batch ID")
    args = parser.parse_args()

    batch_id = args.batch_id or f"upgrade-lite-{int(time.time())}"

    print("Connecting to Supabase...", end=" ", flush=True)
    sb_client = get_supabase_client()
    print("OK")

    # Get domains to process
    if args.input and os.path.isfile(args.input):
        with open(args.input) as f:
            domains = [{"domain": line.strip(), "geography": None} for line in f if line.strip()]
    elif args.owner:
        domains = get_lite_domains(sb_client, args.owner)
    else:
        domains = get_lite_domains(sb_client)

    if args.dry_run:
        domains = domains[:args.dry_run]

    total = len(domains)
    print(f"Leads to upgrade: {total}")
    print(f"Batch ID: {batch_id}")
    print(f"Country: {args.country}")
    print("=" * 60)

    stats = {"processed": 0, "succeeded": 0, "failed": 0}
    batch_start = time.time()

    for i, entry in enumerate(domains):
        domain = entry["domain"]
        t0 = time.time()
        print(f"[{i+1}/{total}] {domain}...", end=" ", flush=True)

        try:
            result = run_enrichment(
                domain,
                batch_id=batch_id,
                enable_google_demand=True,
                country=args.country,
                skip_cache=args.skip_cache,
            )
            elapsed = time.time() - t0

            prediction = _run_prediction(result)

            if result.clean_url and result.domain:
                stats["succeeded"] += 1
                status = "OK"
            else:
                stats["failed"] += 1
                status = "FAIL"
            stats["processed"] += 1

            parts = [f"{status} ({elapsed:.1f}s)"]
            if result.platform:
                parts.append(result.platform)
            if result.category:
                parts.append(result.category)
            if result.ig_followers:
                parts.append(f"IG:{result.ig_followers:,}")
            if prediction:
                parts.append(f"P50:{prediction['predicted_orders_p50']}")
            print(" | ".join(parts))

            try:
                upsert_enrichment(sb_client, result, prediction)
                print(f"  >> saved to Supabase")
            except Exception as e:
                print(f"  >> ERROR saving: {e}")

        except Exception as e:
            elapsed = time.time() - t0
            stats["failed"] += 1
            stats["processed"] += 1
            print(f"EXCEPTION ({elapsed:.1f}s): {e}")

    total_time = time.time() - batch_start
    print("=" * 60)
    print(f"Done in {total_time/60:.1f} min")
    print(f"Processed: {stats['processed']}/{total}")
    print(f"Succeeded: {stats['succeeded']}")
    print(f"Failed: {stats['failed']}")


if __name__ == "__main__":
    main()
