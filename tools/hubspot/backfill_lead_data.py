"""
Backfill lead data from HubSpot: stage, owner, created_at, activities, tasks.
Matches by domain first, then falls back to hubspot_company_id.
"""

import os
import sys
import time
from datetime import date
import requests
from dotenv import load_dotenv

load_dotenv()

_TOOLS_DIR = os.path.join(os.path.dirname(__file__), "..")
if _TOOLS_DIR not in sys.path:
    sys.path.insert(0, _TOOLS_DIR)

HUBSPOT_API_BASE = "https://api.hubapi.com"

LEAD_STAGE_MAP = {
    "new-stage-id": "Nuevo",
    "189401210": "Enrichment",
    "attempting-stage-id": "Intentando contactar",
    "connected-stage-id": "Conectado",
    "qualified-stage-id": "Negocio abierto",
    "unqualified-stage-id": "Descartado",
}

ACTIVE_STAGES = {"new-stage-id", "189401210", "attempting-stage-id", "connected-stage-id"}


def _headers():
    return {
        "Authorization": f"Bearer {os.getenv('HUBSPOT_TOKEN')}",
        "Content-Type": "application/json",
    }


def _api_get(url, params=None, retries=2):
    for attempt in range(retries + 1):
        try:
            resp = requests.get(url, headers=_headers(), params=params, timeout=15)
            if resp.status_code == 429:
                wait = int(resp.headers.get("Retry-After", 10))
                print(f"    Rate limited, waiting {wait}s...")
                time.sleep(wait)
                continue
            return resp
        except Exception:
            if attempt < retries:
                time.sleep(2)
    return None


def _api_post(url, json_body, retries=2):
    for attempt in range(retries + 1):
        try:
            resp = requests.post(url, headers=_headers(), json=json_body, timeout=15)
            if resp.status_code == 429:
                wait = int(resp.headers.get("Retry-After", 10))
                print(f"    Rate limited, waiting {wait}s...")
                time.sleep(wait)
                continue
            return resp
        except Exception:
            if attempt < retries:
                time.sleep(2)
    return None


def fetch_all_active_leads():
    """Fetch all active leads with owner, stage, company_id."""
    all_leads = []
    after = None

    while True:
        body = {
            "filterGroups": [{"filters": [{"propertyName": "hs_pipeline_stage", "operator": "IN", "values": list(ACTIVE_STAGES)}]}],
            "properties": ["hs_lead_name", "hs_primary_company_id", "hs_pipeline_stage",
                           "hs_lead_label", "hubspot_owner_id", "hs_associated_company_domain", "hs_createdate"],
            "limit": 100,
        }
        if after:
            body["after"] = after

        resp = _api_post(f"{HUBSPOT_API_BASE}/crm/v3/objects/0-136/search", body)
        if not resp or resp.status_code != 200:
            break

        data = resp.json()
        for r in data.get("results", []):
            p = r.get("properties", {})
            domain = (p.get("hs_associated_company_domain") or "").strip().lower()
            if domain.startswith("www."):
                domain = domain[4:]
            company_id = p.get("hs_primary_company_id") or ""

            if not domain and not company_id:
                continue

            all_leads.append({
                "domain": domain,
                "company_id": company_id,
                "lead_stage": LEAD_STAGE_MAP.get(p.get("hs_pipeline_stage", ""), p.get("hs_pipeline_stage", "")),
                "lead_label": p.get("hs_lead_label") or "",
                "owner_id": p.get("hubspot_owner_id") or "",
                "created_at": (p.get("hs_createdate") or "")[:10],
            })

        paging = data.get("paging", {}).get("next", {})
        after = paging.get("after")
        if not after:
            break
        time.sleep(0.2)

    # Deduplicate by company_id (prefer first occurrence)
    seen_cids = set()
    seen_domains = set()
    unique = []
    for l in all_leads:
        key = l["company_id"] or l["domain"]
        if key and key not in seen_cids and l["domain"] not in seen_domains:
            seen_cids.add(key)
            if l["domain"]:
                seen_domains.add(l["domain"])
            unique.append(l)
    return unique


def resolve_owners(owner_ids):
    """Resolve owner IDs to names."""
    owners = {}
    for oid in owner_ids:
        if not oid:
            continue
        resp = _api_get(f"{HUBSPOT_API_BASE}/crm/v3/owners/{oid}")
        if resp and resp.status_code == 200:
            o = resp.json()
            owners[oid] = f"{o.get('firstName', '')} {o.get('lastName', '')}".strip()
        time.sleep(0.1)
    return owners


def fetch_company_activity_and_tasks(company_ids):
    """
    Batch fetch activity data and open tasks for companies.
    Returns: {company_id: {last_activity_date, activity_count, open_tasks_count}}
    """
    results = {}
    batch_size = 100
    today = date.today().isoformat()

    # Step 1: Batch read company activity properties
    print("  Fetching company activity properties...")
    for i in range(0, len(company_ids), batch_size):
        batch = company_ids[i:i + batch_size]
        resp = _api_post(f"{HUBSPOT_API_BASE}/crm/v3/objects/companies/batch/read", {
            "inputs": [{"id": cid} for cid in batch],
            "properties": ["notes_last_updated", "num_notes"],
        })
        if resp and resp.status_code == 200:
            for company in resp.json().get("results", []):
                cid = company.get("id", "")
                p = company.get("properties", {})
                last_activity = (p.get("notes_last_updated") or "")[:10]
                activity_count = int(p.get("num_notes") or 0)
                results[cid] = {
                    "last_activity_date": last_activity if last_activity else None,
                    "activity_count": activity_count,
                    "open_tasks_count": 0,
                }
        time.sleep(0.3)
        if (i + batch_size) % 300 == 0:
            print(f"    {min(i + batch_size, len(company_ids))}/{len(company_ids)} activity data fetched")

    # Step 2: Fetch open tasks per company
    print("  Fetching tasks for companies...")
    for idx, cid in enumerate(company_ids):
        try:
            resp = _api_get(f"{HUBSPOT_API_BASE}/crm/v4/objects/companies/{cid}/associations/tasks")
            if not resp or resp.status_code != 200:
                continue

            task_ids = [str(r.get("toObjectId")) for r in resp.json().get("results", []) if r.get("toObjectId")]
            if not task_ids:
                continue

            # Batch read task details
            tresp = _api_post(f"{HUBSPOT_API_BASE}/crm/v3/objects/tasks/batch/read", {
                "inputs": [{"id": tid} for tid in task_ids[:20]],
                "properties": ["hs_task_status", "hs_task_due_date"],
            })
            if not tresp or tresp.status_code != 200:
                continue

            open_count = 0
            for task in tresp.json().get("results", []):
                tp = task.get("properties", {})
                status = tp.get("hs_task_status", "")
                due = (tp.get("hs_task_due_date") or "")[:10]
                if status != "COMPLETED" and due and due >= today:
                    open_count += 1

            if cid in results:
                results[cid]["open_tasks_count"] = open_count
            else:
                results[cid] = {"last_activity_date": None, "activity_count": 0, "open_tasks_count": open_count}

        except Exception:
            pass

        time.sleep(0.3)
        if (idx + 1) % 50 == 0:
            print(f"    {idx + 1}/{len(company_ids)} tasks fetched")

    return results


def fetch_last_lost_deal_dates(client):
    """For companies with Cierre Perdido, get the most recent closedate."""
    rows = client.select("enriched_companies", columns="domain,hubspot_company_id,hubspot_deal_stage", eq={"source": "hubspot_leads"})
    lost_domains = {}
    for r in rows:
        if r.get("hubspot_deal_stage") and "perdido" in r["hubspot_deal_stage"].lower():
            cid = r.get("hubspot_company_id")
            if cid:
                lost_domains[r["domain"]] = cid

    print(f"  {len(lost_domains)} companies with Cierre Perdido, fetching dates...")
    dates = {}
    items = list(lost_domains.items())

    for i, (domain, cid) in enumerate(items):
        try:
            resp = _api_get(f"{HUBSPOT_API_BASE}/crm/v4/objects/companies/{cid}/associations/deals")
            if not resp or resp.status_code != 200:
                continue
            deal_ids = [r.get("toObjectId") for r in resp.json().get("results", []) if r.get("toObjectId")]
            if not deal_ids:
                continue

            resp2 = _api_post(f"{HUBSPOT_API_BASE}/crm/v3/objects/deals/batch/read", {
                "properties": ["dealstage", "closedate"],
                "inputs": [{"id": str(did)} for did in deal_ids[:20]],
            })
            if not resp2 or resp2.status_code != 200:
                continue

            latest_date = None
            for deal in resp2.json().get("results", []):
                dp = deal.get("properties", {})
                if dp.get("dealstage") in ("169389739", "949334561", "36071752"):
                    cd = dp.get("closedate", "")
                    if cd and (not latest_date or cd > latest_date):
                        latest_date = cd
            if latest_date:
                dates[domain] = latest_date[:10]
        except Exception:
            pass
        time.sleep(0.5)
        if (i + 1) % 20 == 0:
            print(f"    {i+1}/{len(items)} processed, {len(dates)} dates found")

    return dates


def _patch_supabase(domain, update):
    """PATCH a single row in Supabase by domain."""
    sb_url = os.getenv("SUPABASE_URL")
    sb_key = os.getenv("SUPABASE_SERVICE_KEY")
    resp = requests.patch(
        f"{sb_url}/rest/v1/enriched_companies?domain=eq.{domain}",
        headers={"apikey": sb_key, "Authorization": f"Bearer {sb_key}",
                 "Content-Type": "application/json", "Prefer": "return=representation"},
        json=update,
        timeout=10,
    )
    return resp.ok and resp.json()


def main():
    from export.supabase_writer import get_client

    print("Backfill Lead Data v2")
    print("=" * 60)

    client = get_client()

    # Step 1: Fetch leads
    print("Fetching active leads from HubSpot...")
    leads = fetch_all_active_leads()
    print(f"  {len(leads)} unique active leads")

    # Step 2: Resolve owners
    owner_ids = set(l["owner_id"] for l in leads if l["owner_id"])
    print(f"Resolving {len(owner_ids)} owners...")
    owners = resolve_owners(owner_ids)
    print(f"  Resolved {len(owners)} owners")

    # Step 3: Get last lost deal dates
    print("Fetching last lost deal dates...")
    lost_dates = fetch_last_lost_deal_dates(client)
    print(f"  {len(lost_dates)} lost deal dates found")

    # Step 4: Fetch activity + tasks for all company IDs
    company_ids = list(set(l["company_id"] for l in leads if l["company_id"]))
    print(f"Fetching activity and tasks for {len(company_ids)} companies...")
    activity_data = fetch_company_activity_and_tasks(company_ids)
    print(f"  Got activity data for {len(activity_data)} companies")

    # Step 5: Build lookups from Supabase
    print("Building Supabase lookups...")
    existing = client.select("enriched_companies", columns="domain,hubspot_company_id", eq={"source": "hubspot_leads"})
    sb_by_domain = {r["domain"].lower(): r["domain"] for r in existing if r.get("domain")}
    sb_by_cid = {}
    for r in existing:
        cid = r.get("hubspot_company_id")
        if cid and r.get("domain"):
            sb_by_cid[str(cid)] = r["domain"]
    print(f"  {len(sb_by_domain)} by domain, {len(sb_by_cid)} by company_id")

    # Step 6: Update
    print("Updating Supabase...")
    updated = 0
    not_found = 0

    for lead in leads:
        ld = lead["domain"].lower() if lead["domain"] else ""
        cid = lead["company_id"]

        # Match by domain first, then by company_id
        matched_domain = None
        if ld and ld in sb_by_domain:
            matched_domain = sb_by_domain[ld]
        elif ld and ld.startswith("www.") and ld[4:] in sb_by_domain:
            matched_domain = sb_by_domain[ld[4:]]
        elif ld and f"www.{ld}" in sb_by_domain:
            matched_domain = sb_by_domain[f"www.{ld}"]
        elif cid and str(cid) in sb_by_cid:
            matched_domain = sb_by_cid[str(cid)]

        if not matched_domain:
            not_found += 1
            continue

        owner_name = owners.get(lead["owner_id"], "")
        lost_date = lost_dates.get(matched_domain.lower(), "") or lost_dates.get(ld, "")
        act = activity_data.get(cid, {})

        update = {
            "hs_lead_stage": lead["lead_stage"],
            "hs_lead_label": lead["lead_label"],
        }
        if owner_name:
            update["hs_lead_owner"] = owner_name
        if lost_date:
            update["hs_last_lost_deal_date"] = lost_date
        if lead.get("created_at"):
            update["hs_lead_created_at"] = lead["created_at"]
        if act.get("last_activity_date"):
            update["hs_last_activity_date"] = act["last_activity_date"]
        if act.get("activity_count") is not None:
            update["hs_activity_count"] = act["activity_count"]
        if act.get("open_tasks_count") is not None:
            update["hs_open_tasks_count"] = act["open_tasks_count"]

        if _patch_supabase(matched_domain, update):
            updated += 1
        else:
            not_found += 1

    print(f"\nDone: {updated} updated, {not_found} not matched")


if __name__ == "__main__":
    main()
