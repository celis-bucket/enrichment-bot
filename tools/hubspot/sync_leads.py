"""
HubSpot Leads Sync Tool

Purpose: Fetch leads from HubSpot Lead object (0-136), get associated company data,
         and run lite enrichment for new leads.
Dependencies: hubspot_lookup, export_leads_csv, run_enrichment_lite, supabase_writer
"""

import os
import sys
import time
from typing import Dict, Any, Optional, List, Callable

import requests
from dotenv import load_dotenv

load_dotenv()

_TOOLS_DIR = os.path.join(os.path.dirname(__file__), "..")
if _TOOLS_DIR not in sys.path:
    sys.path.insert(0, _TOOLS_DIR)

HUBSPOT_API_BASE = "https://api.hubapi.com"
LEAD_OBJECT_TYPE = "0-136"

# Lead pipeline stages (from GET /crm/v3/pipelines/0-136)
LEAD_STAGE_MAP = {
    "new-stage-id": "Nuevo",
    "189401210": "Enrichment",
    "attempting-stage-id": "Intentando contactar",
    "connected-stage-id": "Conectado",
    "qualified-stage-id": "Negocio abierto",
    "unqualified-stage-id": "Descartado",
}

# Stages eligible for new lite enrichment
ACTIVE_STAGES = {
    "new-stage-id",
    "189401210",
    "attempting-stage-id",
    "connected-stage-id",
}

# All stages to sync (includes inactive — to update stage changes in Supabase)
ALL_SYNC_STAGES = {
    "new-stage-id",
    "189401210",
    "attempting-stage-id",
    "connected-stage-id",
    "qualified-stage-id",
    "unqualified-stage-id",
}

LEAD_PROPERTIES = [
    "hs_lead_name",
    "hs_primary_company_id",
    "hs_pipeline_stage",
    "hs_lead_label",
    "hs_associated_company_domain",
    "hs_associated_company_name",
]

COMPANY_PROPERTIES = ["name", "domain", "website", "instagram", "instagram_new"]


def _get_token() -> Optional[str]:
    return os.getenv("HUBSPOT_TOKEN")


def _headers() -> dict:
    token = _get_token()
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


def _api_request(method: str, url: str, json_body: dict = None, params: dict = None) -> Optional[dict]:
    """HubSpot API request with retry on 429."""
    for attempt in range(3):
        try:
            if method == "GET":
                resp = requests.get(url, headers=_headers(), params=params, timeout=30)
            else:
                resp = requests.post(url, headers=_headers(), json=json_body, timeout=30)

            if resp.status_code == 429:
                retry_after = int(resp.headers.get("Retry-After", 5))
                time.sleep(retry_after)
                continue

            if resp.status_code == 404:
                return None

            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.RequestException as e:
            if attempt < 2:
                time.sleep(2)
                continue
            return None
    return None


def fetch_all_leads(on_progress: Callable = None) -> Dict[str, Any]:
    """
    Fetch all leads from HubSpot Lead pipeline (all stages).
    Includes Descartado and Negocio abierto so we can update stage changes in Supabase.

    Returns:
        {success, data: {leads: [...], total_fetched, active_count}, error}
    """
    if not _get_token():
        return {"success": False, "data": {}, "error": "HUBSPOT_TOKEN not set"}

    all_leads = []
    after = None
    page = 0

    # Fetch all pipeline stages to keep Supabase in sync
    filter_groups = [{
        "filters": [{
            "propertyName": "hs_pipeline_stage",
            "operator": "IN",
            "values": list(ALL_SYNC_STAGES),
        }]
    }]

    while True:
        page += 1
        body = {
            "filterGroups": filter_groups,
            "properties": LEAD_PROPERTIES,
            "limit": 100,
        }
        if after:
            body["after"] = after

        data = _api_request("POST", f"{HUBSPOT_API_BASE}/crm/v3/objects/{LEAD_OBJECT_TYPE}/search", json_body=body)

        if not data:
            break

        results = data.get("results", [])
        for r in results:
            props = r.get("properties", {})
            company_id = props.get("hs_primary_company_id")
            stage = props.get("hs_pipeline_stage", "")

            if not company_id:
                continue

            all_leads.append({
                "lead_id": r.get("id"),
                "company_id": company_id,
                "company_name": props.get("hs_associated_company_name") or "",
                "domain": props.get("hs_associated_company_domain") or "",
                "lead_stage": LEAD_STAGE_MAP.get(stage, stage),
                "lead_label": props.get("hs_lead_label") or "",
                "lead_name": props.get("hs_lead_name") or "",
            })

        if on_progress:
            on_progress(f"Fetched {len(all_leads)} leads (page {page})")

        # Pagination
        paging = data.get("paging", {})
        next_page = paging.get("next", {})
        after = next_page.get("after")
        if not after:
            break

        time.sleep(0.2)

    # Deduplicate by company_id (keep first occurrence = most recent lead)
    seen = set()
    unique_leads = []
    for lead in all_leads:
        cid = lead["company_id"]
        if cid not in seen:
            seen.add(cid)
            unique_leads.append(lead)

    return {
        "success": True,
        "data": {
            "leads": unique_leads,
            "total_fetched": len(all_leads),
            "unique_companies": len(unique_leads),
        },
        "error": None,
    }


def fetch_company_details(company_ids: List[str]) -> Dict[str, dict]:
    """
    Batch read company details from HubSpot.
    Returns: {company_id: {name, website_url, instagram_url}}
    """
    url = f"{HUBSPOT_API_BASE}/crm/v3/objects/companies/batch/read"
    results = {}
    batch_size = 100

    for i in range(0, len(company_ids), batch_size):
        batch = company_ids[i:i + batch_size]
        body = {
            "properties": COMPANY_PROPERTIES,
            "inputs": [{"id": cid} for cid in batch],
        }

        data = _api_request("POST", url, json_body=body)
        if not data:
            continue

        for company in data.get("results", []):
            cid = company.get("id", "")
            props = company.get("properties", {})

            name = (props.get("name") or "").strip()
            domain = (props.get("domain") or "").strip()
            website = (props.get("website") or "").strip()
            ig = (props.get("instagram") or "").strip()
            ig_username = (props.get("instagram_new") or "").strip()

            if not website and domain:
                website = f"https://{domain}"
            if not ig and ig_username:
                ig = f"https://instagram.com/{ig_username}"

            results[cid] = {
                "name": name,
                "domain": domain,
                "website_url": website,
                "instagram_url": ig,
            }

        time.sleep(0.3)

    return results


def sync_leads(
    on_progress: Callable = None,
    skip_cache: bool = False,
    max_enrich: int = 0,
) -> Dict[str, Any]:
    """
    Full sync: fetch leads from HubSpot, enrich new ones, update existing.

    Args:
        on_progress: Callback for progress updates (message: str)
        skip_cache: Bypass cache for lite enrichment
        max_enrich: Max new leads to enrich (0 = all). Useful for testing.

    Returns:
        Summary dict with stats
    """
    from orchestrator.run_enrichment_lite import run_enrichment_lite
    from export.supabase_writer import get_client, upsert_enrichment
    from core.url_normalizer import normalize_url, extract_domain

    def _progress(msg):
        if on_progress:
            on_progress(msg)
        print(f"  {msg}")

    _progress("Connecting to Supabase...")
    try:
        sb_client = get_client()
    except Exception as e:
        return {"success": False, "error": f"Supabase connection failed: {e}"}

    # Step 1: Fetch leads from HubSpot
    _progress("Fetching leads from HubSpot...")
    leads_result = fetch_all_leads(on_progress=_progress)
    if not leads_result["success"]:
        return {"success": False, "error": leads_result.get("error")}

    leads = leads_result["data"]["leads"]
    _progress(f"Found {len(leads)} unique active leads")

    # Step 2: Get company details
    company_ids = [l["company_id"] for l in leads]
    _progress(f"Fetching company details for {len(company_ids)} companies...")
    company_details = fetch_company_details(company_ids)
    _progress(f"Got details for {len(company_details)} companies")

    # Step 3: Check existing domains in Supabase
    _progress("Reading existing domains from Supabase...")
    existing_rows = sb_client.select(
        "enriched_companies",
        columns="domain,enrichment_type,source",
    )
    existing_domains = {}
    for r in existing_rows:
        d = r.get("domain")
        if d:
            existing_domains[d.lower()] = {
                "enrichment_type": r.get("enrichment_type"),
                "source": r.get("source"),
            }

    # Step 4: Classify leads
    to_enrich = []
    to_update = []
    skipped = 0

    # Reverse map to check if a stage is active (eligible for new enrichment)
    _active_stage_names = {LEAD_STAGE_MAP[s] for s in ACTIVE_STAGES if s in LEAD_STAGE_MAP}

    for lead in leads:
        cid = lead["company_id"]
        company = company_details.get(cid, {})
        website = company.get("website_url", "")
        ig = company.get("instagram_url", "")
        name = company.get("name") or lead.get("company_name", "")

        # Resolve domain
        domain = None
        if website:
            norm = normalize_url(website)
            if norm["success"]:
                domain = extract_domain(norm["data"]["url"])
        if not domain and company.get("domain"):
            domain = company["domain"].lower()

        is_active_stage = lead["lead_stage"] in _active_stage_names

        if domain and domain.lower() in existing_domains:
            # Already in DB — always update stage/label to keep in sync
            to_update.append({
                "domain": domain,
                "hs_lead_stage": lead["lead_stage"],
                "hs_lead_label": lead["lead_label"],
                "source": "hubspot_leads",
            })
        elif is_active_stage:
            # New lead in active stage — enrich it
            to_enrich.append({
                "company_name": name,
                "website_url": website,
                "instagram_url": ig,
                "lead_stage": lead["lead_stage"],
                "lead_label": lead["lead_label"],
            })
        else:
            skipped += 1  # New lead in Descartado/Negocio abierto — skip

    _progress(f"To enrich: {len(to_enrich)} new, To update: {len(to_update)}, Skipped (full): {skipped}")

    # Step 5: Update existing records with lead stage/label
    if to_update:
        _progress(f"Updating {len(to_update)} existing records...")
        for row in to_update:
            try:
                sb_client.upsert("enriched_companies", row, on_conflict="domain")
            except Exception:
                pass
        _progress(f"Updated {len(to_update)} records")

    # Step 6: Enrich new leads
    if max_enrich > 0:
        to_enrich = to_enrich[:max_enrich]

    enriched = 0
    failed = 0

    for i, lead in enumerate(to_enrich):
        _progress(f"Enriching [{i+1}/{len(to_enrich)}] {lead['company_name'][:30]}...")

        try:
            result = run_enrichment_lite(
                company_name=lead["company_name"],
                website_url=lead["website_url"],
                instagram_url=lead["instagram_url"],
                skip_cache=skip_cache,
            )

            # Set lead-specific fields
            result.source = "hubspot_leads"
            result.hs_lead_stage = lead["lead_stage"]
            result.hs_lead_label = lead["lead_label"]

            if result.domain:
                upsert_enrichment(sb_client, result)
                enriched += 1
            else:
                failed += 1

        except Exception as e:
            failed += 1
            _progress(f"  ERROR: {e}")

    summary = {
        "success": True,
        "total_leads": len(leads),
        "new_enriched": enriched,
        "updated": len(to_update),
        "skipped_full": skipped,
        "failed": failed,
        "total_to_enrich": len(to_enrich),
    }

    _progress(f"Sync complete: {enriched} enriched, {len(to_update)} updated, {skipped} skipped, {failed} failed")
    return summary


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Sync HubSpot leads + lite enrichment")
    parser.add_argument("--max-enrich", type=int, default=0, help="Max new leads to enrich (0=all)")
    parser.add_argument("--skip-cache", action="store_true", help="Bypass cache")
    args = parser.parse_args()

    print("HubSpot Leads Sync")
    print("=" * 60)

    result = sync_leads(max_enrich=args.max_enrich, skip_cache=args.skip_cache)
    print()
    print("=" * 60)
    for k, v in result.items():
        print(f"  {k}: {v}")
