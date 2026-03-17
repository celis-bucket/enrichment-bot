"""
Supabase Cron Runner — Weekly Logistics Crisis Monitor

Purpose: Fetch active companies from Supabase, run IG logistics complaint
         analysis for each, write results back to Supabase.
Inputs: Reads companies from Supabase `companies` table
Outputs: Writes to Supabase `scans` and `flagged_comments` tables
Dependencies: requests, anthropic, dotenv

Designed to run as a GitHub Actions cron job every Monday at 3am COT.

Usage:
    python tools/logistics/supabase_cron_runner.py
    python tools/logistics/supabase_cron_runner.py --force   # Ignore weekly dedup
    python tools/logistics/supabase_cron_runner.py --dry-run  # Don't write to Supabase
"""

import os
import sys
import time
from datetime import datetime, timezone, timedelta

from dotenv import load_dotenv

# Add parent dirs to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '..', '.env'))

from logistics.run_single_by_username import run_single_by_username
from logistics.supabase_client import SupabaseClient


def get_active_companies(client: SupabaseClient) -> list:
    """Fetch all active companies from Supabase."""
    return client.select("companies", eq={"is_active": True})


def get_current_week_scans(client: SupabaseClient, company_ids: list) -> set:
    """Get company IDs that already have a scan this ISO week."""
    now = datetime.now(timezone.utc)
    week_start = now - timedelta(days=now.weekday())
    week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)

    if not company_ids:
        return set()

    rows = client.select(
        "scans",
        columns="company_id",
        gte={"scanned_at": week_start.isoformat()},
        in_={"company_id": company_ids},
    )
    return {row["company_id"] for row in rows}


def get_previous_scan(client: SupabaseClient, company_id: str) -> dict | None:
    """Get the most recent completed scan for a company (for delta calculation)."""
    rows = client.select(
        "scans",
        columns="risk_score",
        eq={"company_id": company_id, "status": "completed"},
        order="scanned_at.desc",
        limit=1,
    )
    return rows[0] if rows else None


def write_scan(client: SupabaseClient, company_id: str, result: dict, prev_score: int | None) -> str:
    """Write a scan result to Supabase. Returns the scan ID."""
    analysis = result.get("analysis") or {}

    current_score = analysis.get("risk_score")
    score_delta = None
    if prev_score is not None and current_score is not None:
        score_delta = current_score - prev_score

    scan_data = {
        "company_id": company_id,
        "status": result["status"],
        "risk_score": current_score,
        "risk_level": analysis.get("risk_level"),
        "summary": analysis.get("summary"),
        "posts_analyzed": analysis.get("posts_analyzed"),
        "total_comments_scraped": analysis.get("total_comments_scraped"),
        "brand_replies_excluded": analysis.get("brand_replies_excluded"),
        "comments_analyzed": analysis.get("comments_analyzed"),
        "complaints_found": analysis.get("complaints_found"),
        "complaint_rate_pct": analysis.get("complaint_rate_pct"),
        "category_breakdown": analysis.get("category_breakdown", {}),
        "recency_trend": analysis.get("recency_trend"),
        "recent_complaint_rate": analysis.get("recent_complaint_rate"),
        "older_complaint_rate": analysis.get("older_complaint_rate"),
        "ig_followers": (result.get("instagram") or {}).get("followers"),
        "runtime_sec": (result.get("timings") or {}).get("total_sec"),
        "claude_tokens_used": analysis.get("claude_tokens_used"),
        "error_message": result.get("error"),
        "prev_risk_score": prev_score,
        "score_delta": score_delta,
    }

    inserted = client.insert("scans", scan_data)
    return inserted[0]["id"]


def write_flagged_comments(client: SupabaseClient, scan_id: str, company_id: str, comments: list):
    """Write flagged comments for a scan to Supabase."""
    if not comments:
        return

    rows = []
    for fc in comments:
        rows.append({
            "scan_id": scan_id,
            "company_id": company_id,
            "comment_id": fc.get("comment_id", ""),
            "text": fc.get("text", ""),
            "category": fc.get("category", ""),
            "severity": fc.get("severity", ""),
            "owner": fc.get("owner", ""),
            "comment_timestamp": fc.get("timestamp", ""),
            "likes": fc.get("likes", 0),
            "post_url": fc.get("post_url", ""),
        })

    # Insert in batches of 50
    for i in range(0, len(rows), 50):
        batch = rows[i:i + 50]
        client.insert("flagged_comments", batch)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Weekly logistics crisis scan")
    parser.add_argument("--force", action="store_true", help="Ignore weekly dedup")
    parser.add_argument("--dry-run", action="store_true", help="Don't write to Supabase")
    parser.add_argument("--limit", type=int, help="Max companies to scan")
    args = parser.parse_args()

    batch_start = time.time()
    now = datetime.now(timezone.utc)

    print("=" * 60)
    print("Logistics Crisis Monitor — Weekly Scan")
    print(f"Date: {now.strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"Mode: {'DRY RUN' if args.dry_run else 'LIVE'}")
    print("=" * 60)

    client = SupabaseClient()

    # Test connection
    if not client.ping():
        print("ERROR: Cannot connect to Supabase. Check SUPABASE_URL and keys.")
        sys.exit(1)
    print("Supabase connected.")

    # Fetch active companies
    companies = get_active_companies(client)
    print(f"\nActive companies: {len(companies)}")

    if args.limit:
        companies = companies[:args.limit]
        print(f"Limited to: {args.limit}")

    # Check which already have a scan this week
    company_ids = [c["id"] for c in companies]
    already_scanned = set()
    if not args.force:
        already_scanned = get_current_week_scans(client, company_ids)
        if already_scanned:
            print(f"Already scanned this week: {len(already_scanned)} (skipping)")

    # Filter out already-scanned
    to_scan = [c for c in companies if c["id"] not in already_scanned]
    print(f"To scan: {len(to_scan)}\n")

    if not to_scan:
        print("Nothing to scan. Exiting.")
        return

    # Run analysis for each company
    results_summary = {
        "completed": 0,
        "not_available": 0,
        "errors": 0,
        "skipped": len(already_scanned),
        "alerts": [],
    }

    for i, company in enumerate(to_scan, 1):
        username = company["ig_username"]
        company_id = company["id"]
        print(f"[{i}/{len(to_scan)}] @{username}...", end=" ", flush=True)

        try:
            result = run_single_by_username(username)
            result["instagram"] = result.get("instagram", {})
            status = result["status"]

            if status == "completed":
                analysis = result["analysis"]
                score = analysis["risk_score"]
                complaints = analysis["complaints_found"]
                trend = analysis["recency_trend"]

                prev_scan = get_previous_scan(client, company_id)
                prev_score = prev_scan["risk_score"] if prev_scan else None

                if not args.dry_run:
                    scan_id = write_scan(client, company_id, result, prev_score)
                    write_flagged_comments(
                        client, scan_id, company_id,
                        analysis.get("top_flagged_comments", [])
                    )

                delta_str = ""
                if prev_score is not None:
                    delta = score - prev_score
                    delta_str = f" (delta: {'+' if delta > 0 else ''}{delta})"

                print(f"Score: {score} ({analysis['risk_level']}){delta_str} | "
                      f"Complaints: {complaints} | {result['timings']['total_sec']}s")

                results_summary["completed"] += 1

                if score >= 50 or trend == "worsening":
                    results_summary["alerts"].append({
                        "username": username,
                        "name": company["name"],
                        "score": score,
                        "level": analysis["risk_level"],
                        "trend": trend,
                        "delta": score - prev_score if prev_score is not None else None,
                    })

            elif status == "not_available":
                if not args.dry_run:
                    write_scan(client, company_id, result, None)
                print(f"N/A: {result['error']}")
                results_summary["not_available"] += 1

            else:
                if not args.dry_run:
                    write_scan(client, company_id, result, None)
                print(f"ERROR: {result['error']}")
                results_summary["errors"] += 1

        except Exception as e:
            print(f"EXCEPTION: {e}")
            results_summary["errors"] += 1
            if not args.dry_run:
                try:
                    error_result = {
                        "status": "error",
                        "error": str(e),
                        "analysis": None,
                        "instagram": {},
                        "timings": {},
                    }
                    write_scan(client, company_id, error_result, None)
                except Exception:
                    pass

    # Summary
    total_time = round(time.time() - batch_start, 1)
    print(f"\n{'=' * 60}")
    print(f"SCAN COMPLETE — {total_time}s")
    print(f"  Completed:     {results_summary['completed']}")
    print(f"  Not available: {results_summary['not_available']}")
    print(f"  Errors:        {results_summary['errors']}")
    print(f"  Skipped:       {results_summary['skipped']}")

    if results_summary["alerts"]:
        print(f"\n{'!' * 60}")
        print(f"ALERTS ({len(results_summary['alerts'])} companies):")
        for alert in results_summary["alerts"]:
            delta_str = ""
            if alert["delta"] is not None:
                delta_str = f" | delta: {'+' if alert['delta'] > 0 else ''}{alert['delta']}"
            print(f"  @{alert['username']} ({alert['name']}): "
                  f"Score {alert['score']} ({alert['level']}) | "
                  f"Trend: {alert['trend']}{delta_str}")
    else:
        print("\nNo alerts — all companies within normal range.")

    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
