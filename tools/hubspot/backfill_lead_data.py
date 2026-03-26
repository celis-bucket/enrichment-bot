"""
Backfill lead stage, owner, and last lost deal date for existing leads.
One-time script to populate hs_lead_stage, hs_lead_label, hs_lead_owner from HubSpot.
"""

import os
import sys
import time
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


def fetch_all_active_leads():
    """Fetch all active leads with owner and stage."""
    all_leads = []
    after = None

    while True:
        body = {
            "filterGroups": [{"filters": [{"propertyName": "hs_pipeline_stage", "operator": "IN", "values": list(ACTIVE_STAGES)}]}],
            "properties": ["hs_lead_name", "hs_primary_company_id", "hs_pipeline_stage", "hs_lead_label", "hubspot_owner_id", "hs_associated_company_domain", "hs_createdate"],
            "limit": 100,
        }
        if after:
            body["after"] = after

        resp = requests.post(f"{HUBSPOT_API_BASE}/crm/v3/objects/0-136/search", headers=_headers(), json=body, timeout=30)
        if resp.status_code != 200:
            print(f"Error: {resp.status_code}")
            break

        data = resp.json()
        for r in data.get("results", []):
            p = r.get("properties", {})
            domain = (p.get("hs_associated_company_domain") or "").strip().lower()
            if not domain:
                continue
            # Remove www. prefix for matching
            if domain.startswith("www."):
                domain = domain[4:]
            all_leads.append({
                "domain": domain,
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

    # Deduplicate by domain
    seen = set()
    unique = []
    for l in all_leads:
        if l["domain"] not in seen:
            seen.add(l["domain"])
            unique.append(l)
    return unique


def resolve_owners(owner_ids):
    """Resolve owner IDs to names."""
    owners = {}
    for oid in owner_ids:
        if not oid:
            continue
        resp = requests.get(f"{HUBSPOT_API_BASE}/crm/v3/owners/{oid}", headers=_headers(), timeout=10)
        if resp.status_code == 200:
            o = resp.json()
            name = f"{o.get('firstName', '')} {o.get('lastName', '')}".strip()
            owners[oid] = name
        time.sleep(0.1)
    return owners


def fetch_last_lost_deal_dates(company_ids_by_domain):
    """For companies with Cierre Perdido, get the most recent closedate."""
    from export.supabase_writer import get_client
    client = get_client()

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
            # Get deals for this company
            resp = requests.get(
                f"{HUBSPOT_API_BASE}/crm/v4/objects/companies/{cid}/associations/deals",
                headers=_headers(), timeout=15
            )
            if resp.status_code == 429:
                retry_after = int(resp.headers.get("Retry-After", 10))
                print(f"    Rate limited, waiting {retry_after}s...")
                time.sleep(retry_after)
                resp = requests.get(
                    f"{HUBSPOT_API_BASE}/crm/v4/objects/companies/{cid}/associations/deals",
                    headers=_headers(), timeout=15
                )
            if resp.status_code != 200:
                continue

            deal_ids = [r.get("toObjectId") for r in resp.json().get("results", []) if r.get("toObjectId")]
            if not deal_ids:
                continue

            # Batch read deals
            resp2 = requests.post(
                f"{HUBSPOT_API_BASE}/crm/v3/objects/deals/batch/read",
                headers=_headers(),
                json={"properties": ["dealstage", "closedate", "dealname"], "inputs": [{"id": str(did)} for did in deal_ids[:20]]},
                timeout=15
            )
            if resp2.status_code == 429:
                retry_after = int(resp2.headers.get("Retry-After", 10))
                print(f"    Rate limited, waiting {retry_after}s...")
                time.sleep(retry_after)
                continue
            if resp2.status_code != 200:
                continue

            # Find most recent Cierre Perdido
            latest_date = None
            for deal in resp2.json().get("results", []):
                dp = deal.get("properties", {})
                stage = dp.get("dealstage", "")
                # Cierre Perdido stage IDs
                if stage in ("169389739", "949334561", "36071752"):
                    cd = dp.get("closedate", "")
                    if cd and (not latest_date or cd > latest_date):
                        latest_date = cd

            if latest_date:
                dates[domain] = latest_date[:10]  # Just the date part

        except Exception as e:
            print(f"    Error for {domain}: {e}")

        # Slower pace to avoid rate limits
        time.sleep(0.5)
        if (i + 1) % 20 == 0:
            print(f"    {i+1}/{len(items)} processed, {len(dates)} dates found")

    return dates


def main():
    from export.supabase_writer import get_client

    print("Backfill Lead Data")
    print("=" * 60)

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
    lost_dates = fetch_last_lost_deal_dates({})
    print(f"  {len(lost_dates)} lost deal dates found")

    # Step 4: Update Supabase
    print("Updating Supabase...")
    client = get_client()

    # Build lookup of existing domains in Supabase
    existing = client.select("enriched_companies", columns="domain", eq={"source": "hubspot_leads"})
    sb_domains = {r["domain"].lower(): r["domain"] for r in existing if r.get("domain")}
    print(f"  {len(sb_domains)} existing lead domains in Supabase")

    updated = 0
    not_found = 0

    for lead in leads:
        # Match domain: try exact, then with www., then without www.
        ld = lead["domain"].lower()
        matched_domain = None
        if ld in sb_domains:
            matched_domain = sb_domains[ld]
        elif ld.startswith("www.") and ld[4:] in sb_domains:
            matched_domain = sb_domains[ld[4:]]
        elif f"www.{ld}" in sb_domains:
            matched_domain = sb_domains[f"www.{ld}"]

        if not matched_domain:
            not_found += 1
            continue

        owner_name = owners.get(lead["owner_id"], "")
        lost_date = lost_dates.get(matched_domain.lower(), "") or lost_dates.get(ld, "")

        update = {
            "domain": matched_domain,
            "hs_lead_stage": lead["lead_stage"],
            "hs_lead_label": lead["lead_label"],
        }
        if owner_name:
            update["hs_lead_owner"] = owner_name
        if lost_date:
            update["hs_last_lost_deal_date"] = lost_date
        if lead.get("created_at"):
            update["hs_lead_created_at"] = lead["created_at"]

        try:
            import requests as _req
            sb_url = os.getenv("SUPABASE_URL")
            sb_key = os.getenv("SUPABASE_SERVICE_KEY")
            patch_resp = _req.patch(
                f"{sb_url}/rest/v1/enriched_companies?domain=eq.{matched_domain}",
                headers={"apikey": sb_key, "Authorization": f"Bearer {sb_key}", "Content-Type": "application/json", "Prefer": "return=representation"},
                json={k: v for k, v in update.items() if k != "domain"},
                timeout=10,
            )
            if patch_resp.ok and patch_resp.json():
                updated += 1
            else:
                not_found += 1
        except Exception as e:
            not_found += 1

    print(f"\nDone: {updated} updated, {not_found} not matched")


if __name__ == "__main__":
    main()
