"""
HubSpot CRM Lookup Tool

Purpose: Check if a company/contacts already exist in HubSpot CRM and get associated deals.
Inputs: Domain name, optional contact email
Outputs: Company match status, deal info, contact existence
Dependencies: requests, python-dotenv

API Endpoints:
  - POST https://api.hubapi.com/crm/v3/objects/companies/search
  - GET  https://api.hubapi.com/crm/v3/objects/contacts/{email}?idProperty=email
  - GET  https://api.hubapi.com/crm/v4/objects/companies/{id}/associations/deals
  - POST https://api.hubapi.com/crm/v3/objects/deals/batch/read
"""

import os
import time
from typing import Dict, Any, Optional, List
import requests
from dotenv import load_dotenv

load_dotenv()

HUBSPOT_API_BASE = "https://api.hubapi.com"
PORTAL_ID = os.getenv("HUBSPOT_PORTAL_ID", "9359507")

# Pipeline stage ID → human-readable name (from GET /crm/v3/pipelines/deals)
STAGE_MAP = {
    # Ventas 2025
    "169596534": "Consideracion",
    "169596535": "Parametrización",
    "169596536": "Onboarding",
    "169596538": "Cierre ganado",
    "169389739": "Cierre Perdido",
    # Adyacent Revenue
    "250408013": "Reunión de contexto",
    "250408014": "Consideración - Adyacentes",
    "250408018": "Propuesta aceptada",
    "250408019": "Propuesta rechazada",
    "957609872": "Dejó E-xperts",
    # Expansión
    "949334555": "Discovery",
    "949334556": "Preparación de propuesta",
    "949334557": "Consideracion",
    "949334560": "Cierre ganado",
    "949334561": "Cierre perdido",
    # Partnership Program
    "36071746": "Evaluando Partnership",
    "36071747": "Partnership Aceptado",
    "36071748": "Aceptacion T&C",
    "36071749": "Kickoff del Programa",
    "36071750": "Partnership Activo con Acompañamiento",
    "38476831": "Autogestion Partnership",
    "36071752": "Cierre perdido Partnership",
    "36107392": "Partnership Desactivado",
}

PIPELINE_MAP = {
    "91926034": "Ventas 2025",
    "147806218": "Adyacent Revenue",
    "644349494": "Expansión",
    "12393386": "Partnership Program",
}

# Stage ordering per pipeline (index = advancement level, higher = more advanced)
STAGE_ORDER = {
    "91926034": ["169596534", "169596535", "169596536", "169596538", "169389739"],
    "147806218": ["250408013", "250408014", "250408018", "250408019", "957609872"],
    "644349494": ["949334555", "949334556", "949334557", "949334560", "949334561"],
    "12393386": ["36071746", "36071747", "36071748", "36071749", "36071750", "38476831", "36071752", "36107392"],
}


LIFECYCLE_LABELS = {
    "subscriber": "Suscriptor",
    "lead": "Lead",
    "marketingqualifiedlead": "Lead Marketing",
    "salesqualifiedlead": "Lead Ventas",
    "opportunity": "Oportunidad",
    "customer": "Cliente",
    "evangelist": "Evangelista",
    "other": "Otro",
}


def _get_token() -> Optional[str]:
    """Get HUBSPOT_TOKEN from environment."""
    return os.getenv("HUBSPOT_TOKEN")


def _headers() -> dict:
    """Build auth headers."""
    token = _get_token()
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


def _api_request(method: str, url: str, json_body: dict = None, params: dict = None, max_retries: int = 2) -> Optional[dict]:
    """Make HubSpot API request with retry on 429."""
    for attempt in range(max_retries + 1):
        try:
            if method == "GET":
                resp = requests.get(url, headers=_headers(), params=params, timeout=15)
            else:
                resp = requests.post(url, headers=_headers(), json=json_body, timeout=15)

            if resp.status_code == 429:
                retry_after = int(resp.headers.get("Retry-After", 2))
                time.sleep(retry_after)
                continue

            if resp.status_code == 404:
                return None

            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.RequestException:
            if attempt < max_retries:
                time.sleep(1)
                continue
            return None
    return None


def _count_associations(company_id: str) -> int:
    """Count total associations (deals + contacts + notes) for a company."""
    total = 0
    for obj_type in ["deals", "contacts", "notes"]:
        url = f"{HUBSPOT_API_BASE}/crm/v4/objects/companies/{company_id}/associations/{obj_type}"
        data = _api_request("GET", url)
        if data and data.get("results"):
            total += len(data["results"])
    return total


def _pick_best_company(results: List[dict]) -> dict:
    """Pick the best company when duplicates exist for the same domain.

    Priority:
      1. Has hubspot_owner_id assigned
      2. Has more associations (deals > contacts > notes)
      3. Most recently created (newer record is usually the canonical one)

    This handles HubSpot duplicate companies (e.g., "Basika" vs "BY BSIKA"
    both with domain bybsika.com).
    """
    if len(results) == 1:
        return results[0]

    # Prefer companies with an owner assigned
    owned = [r for r in results if r.get("properties", {}).get("hubspot_owner_id")]
    if len(owned) == 1:
        return owned[0]

    # Score each candidate by associations (only check if few duplicates)
    candidates = owned if owned else results
    if len(candidates) <= 5:
        scored = []
        for c in candidates:
            assoc_count = _count_associations(c["id"])
            scored.append((assoc_count, c.get("createdAt", ""), c))
        # Sort by: most associations desc, then newest created desc
        scored.sort(key=lambda x: (x[0], x[1]), reverse=True)
        return scored[0][2]

    # Fallback: most recently created
    candidates_sorted = sorted(candidates, key=lambda r: r.get("createdAt", ""), reverse=True)
    return candidates_sorted[0]


def search_company_by_domain(domain: str) -> Dict[str, Any]:
    """
    Search HubSpot for a company matching the given domain.

    Strategy:
      1. EQ match on 'domain' property
      2. If no results, CONTAINS_TOKEN on 'hs_additional_domains'

    Returns:
        {"success": bool, "data": {"found": bool, ...}, "error": str|None}
    """
    token = _get_token()
    if not token:
        return {"success": True, "data": {"found": False}, "error": None}

    url = f"{HUBSPOT_API_BASE}/crm/v3/objects/companies/search"
    properties = ["name", "domain", "website", "hs_additional_domains", "hubspot_owner_id",
                  "lifecyclestage", "notes_last_contacted"]

    # Strategy 1: exact match on domain (fetch up to 10 to handle duplicates)
    body = {
        "filterGroups": [{
            "filters": [{
                "propertyName": "domain",
                "operator": "EQ",
                "value": domain,
            }]
        }],
        "properties": properties,
        "limit": 10,
    }

    def _build_found_result(company: dict, matched_via: str) -> dict:
        cp = company["properties"]
        lifecycle_raw = cp.get("lifecyclestage", "")
        return {
            "success": True,
            "data": {
                "found": True,
                "company_id": company["id"],
                "company_name": cp.get("name", ""),
                "domain_matched": matched_via,
                "hubspot_url": f"https://app.hubspot.com/contacts/{PORTAL_ID}/company/{company['id']}",
                "owner_id": cp.get("hubspot_owner_id", ""),
                "lifecycle_stage": lifecycle_raw,
                "lifecycle_label": LIFECYCLE_LABELS.get(lifecycle_raw, lifecycle_raw or None),
                "last_contacted": cp.get("notes_last_contacted"),
            },
            "error": None,
        }

    data = _api_request("POST", url, json_body=body)
    if data and data.get("total", 0) > 0:
        company = _pick_best_company(data["results"])
        return _build_found_result(company, "domain")

    # Strategy 2: search additional domains
    body["filterGroups"] = [{
        "filters": [{
            "propertyName": "hs_additional_domains",
            "operator": "CONTAINS_TOKEN",
            "value": domain,
        }]
    }]

    data = _api_request("POST", url, json_body=body)
    if data and data.get("total", 0) > 0:
        company = _pick_best_company(data["results"])
        return _build_found_result(company, "hs_additional_domains")

    return {"success": True, "data": {"found": False}, "error": None}


def get_company_deals(company_id: str) -> Dict[str, Any]:
    """
    Get deals associated with a HubSpot company.

    Returns:
        {"success": bool, "data": {"deal_count": int, "deals": [...], "most_advanced_stage": str}, "error": str|None}
    """
    # Step 1: get deal associations
    url = f"{HUBSPOT_API_BASE}/crm/v4/objects/companies/{company_id}/associations/deals"
    assoc_data = _api_request("GET", url)

    if not assoc_data or not assoc_data.get("results"):
        return {
            "success": True,
            "data": {"deal_count": 0, "deals": [], "most_advanced_stage": ""},
            "error": None,
        }

    deal_ids = [str(r["toObjectId"]) for r in assoc_data["results"]]

    # Step 2: batch read deal details
    batch_url = f"{HUBSPOT_API_BASE}/crm/v3/objects/deals/batch/read"
    batch_body = {
        "inputs": [{"id": did} for did in deal_ids],
        "properties": ["dealname", "dealstage", "pipeline", "amount", "closedate"],
    }
    batch_data = _api_request("POST", batch_url, json_body=batch_body)

    deals = []
    best_stage = ""
    best_stage_index = -1

    if batch_data and batch_data.get("results"):
        for deal in batch_data["results"]:
            props = deal.get("properties", {})
            stage_id = props.get("dealstage", "")
            pipeline_id = props.get("pipeline", "")
            stage_name = STAGE_MAP.get(stage_id, stage_id)
            pipeline_name = PIPELINE_MAP.get(pipeline_id, pipeline_id)

            deals.append({
                "id": deal["id"],
                "name": props.get("dealname", ""),
                "stage": stage_name,
                "pipeline": pipeline_name,
                "amount": props.get("amount", ""),
                "closedate": props.get("closedate", ""),
            })

            # Track most advanced stage (across all pipelines)
            order = STAGE_ORDER.get(pipeline_id, [])
            if stage_id in order:
                idx = order.index(stage_id)
                if idx > best_stage_index:
                    best_stage_index = idx
                    best_stage = stage_name

    return {
        "success": True,
        "data": {
            "deal_count": len(deals),
            "deals": deals,
            "most_advanced_stage": best_stage,
        },
        "error": None,
    }


def check_contact_exists(email: str) -> Dict[str, Any]:
    """
    Check if a contact exists in HubSpot by email.

    Returns:
        {"success": bool, "data": {"exists": bool, "contact_id": str|None, "contact_name": str|None}, "error": str|None}
    """
    if not email:
        return {"success": True, "data": {"exists": False}, "error": None}

    token = _get_token()
    if not token:
        return {"success": True, "data": {"exists": False}, "error": None}

    url = f"{HUBSPOT_API_BASE}/crm/v3/objects/contacts/{email}"
    params = {
        "idProperty": "email",
        "properties": "email,firstname,lastname",
    }

    data = _api_request("GET", url, params=params)

    if data and data.get("id"):
        props = data.get("properties", {})
        name_parts = [props.get("firstname", ""), props.get("lastname", "")]
        contact_name = " ".join(p for p in name_parts if p).strip()
        return {
            "success": True,
            "data": {
                "exists": True,
                "contact_id": data["id"],
                "contact_name": contact_name or None,
            },
            "error": None,
        }

    return {"success": True, "data": {"exists": False}, "error": None}


def get_company_detail(company_id: str) -> Dict[str, Any]:
    """
    Fetch extended company info for the HubSpot detail modal.

    Returns rich data: lifecycle, owner, activity dates, deals, contacts.
    """
    token = _get_token()
    if not token:
        return {"success": False, "data": {}, "error": "No HUBSPOT_TOKEN"}

    try:
        # 1. Fetch company with rich properties
        props = (
            "name,domain,createdate,hubspot_owner_id,lifecyclestage,hs_lead_status,"
            "notes_last_contacted,notes_last_updated,num_notes,num_contacted_notes,"
            "num_associated_contacts,num_associated_deals"
        )
        url = f"{HUBSPOT_API_BASE}/crm/v3/objects/companies/{company_id}"
        company = _api_request("GET", url, params={"properties": props})
        if not company:
            return {"success": False, "data": {}, "error": "Company not found"}

        p = company.get("properties", {})

        # 2. Resolve owner name
        owner_name = None
        owner_email = None
        owner_id = p.get("hubspot_owner_id")
        if owner_id:
            owner_data = _api_request("GET", f"{HUBSPOT_API_BASE}/crm/v3/owners/{owner_id}")
            if owner_data:
                first = owner_data.get("firstName", "")
                last = owner_data.get("lastName", "")
                owner_name = f"{first} {last}".strip() or None
                owner_email = owner_data.get("email")

        # 3. Get deals (reuse existing function)
        deals_result = get_company_deals(company_id)
        deals_data = deals_result.get("data", {})

        # 4. Get associated contacts (top 10)
        contacts = []
        contacts_url = f"{HUBSPOT_API_BASE}/crm/v4/objects/companies/{company_id}/associations/contacts"
        assoc = _api_request("GET", contacts_url)
        if assoc and assoc.get("results"):
            contact_ids = [str(r["toObjectId"]) for r in assoc["results"][:10]]
            batch_url = f"{HUBSPOT_API_BASE}/crm/v3/objects/contacts/batch/read"
            batch_body = {
                "inputs": [{"id": cid} for cid in contact_ids],
                "properties": ["firstname", "lastname", "email", "jobtitle"],
            }
            batch = _api_request("POST", batch_url, json_body=batch_body)
            if batch and batch.get("results"):
                for c in batch["results"]:
                    cp = c.get("properties", {})
                    first = cp.get("firstname", "")
                    last = cp.get("lastname", "")
                    name = f"{first} {last}".strip()
                    contacts.append({
                        "name": name or None,
                        "email": cp.get("email"),
                        "title": cp.get("jobtitle"),
                    })

        lifecycle_raw = p.get("lifecyclestage", "")
        lifecycle_label = LIFECYCLE_LABELS.get(lifecycle_raw, lifecycle_raw or None)

        return {
            "success": True,
            "data": {
                "company_name": p.get("name", ""),
                "created_at": p.get("createdate"),
                "lifecycle_stage": lifecycle_raw,
                "lifecycle_label": lifecycle_label,
                "lead_status": p.get("hs_lead_status"),
                "owner_name": owner_name,
                "owner_email": owner_email,
                "last_contacted": p.get("notes_last_contacted"),
                "last_activity": p.get("notes_last_updated"),
                "total_activities": int(p.get("num_notes") or 0),
                "contact_activities": int(p.get("num_contacted_notes") or 0),
                "associated_contacts_count": int(p.get("num_associated_contacts") or 0),
                "deals": deals_data.get("deals", []),
                "deal_count": deals_data.get("deal_count", 0),
                "most_advanced_stage": deals_data.get("most_advanced_stage", ""),
                "contacts": contacts,
                "hubspot_url": f"https://app.hubspot.com/contacts/{PORTAL_ID}/company/{company_id}",
            },
            "error": None,
        }

    except Exception as e:
        return {"success": False, "data": {}, "error": str(e)}


def hubspot_enrich(domain: str, contact_email: Optional[str] = None) -> Dict[str, Any]:
    """
    Main entry point. Orchestrates company search, deal lookup, and contact check.

    Args:
        domain: Clean domain from url_normalizer.extract_domain()
        contact_email: Primary contact email from Apollo (optional)

    Returns:
        {"success": bool, "data": {...}, "error": str|None}
    """
    token = _get_token()
    if not token:
        return {
            "success": True,
            "data": {
                "company_found": False,
                "company_id": None,
                "company_name": None,
                "hubspot_company_url": None,
                "deal_count": 0,
                "deal_stage": None,
                "deals": [],
                "contact_exists": False,
            },
            "error": None,
        }

    try:
        # 1. Search company by domain
        company_result = search_company_by_domain(domain)
        company_data = company_result.get("data", {})

        result_data = {
            "company_found": company_data.get("found", False),
            "company_id": company_data.get("company_id"),
            "company_name": company_data.get("company_name"),
            "hubspot_company_url": company_data.get("hubspot_url"),
            "lifecycle_stage": company_data.get("lifecycle_stage"),
            "lifecycle_label": company_data.get("lifecycle_label"),
            "last_contacted": company_data.get("last_contacted"),
            "deal_count": 0,
            "deal_stage": None,
            "deals": [],
            "contact_exists": False,
        }

        # 2. If company found, get deals
        if company_data.get("found") and company_data.get("company_id"):
            deals_result = get_company_deals(company_data["company_id"])
            deals_data = deals_result.get("data", {})
            result_data["deal_count"] = deals_data.get("deal_count", 0)
            result_data["deal_stage"] = deals_data.get("most_advanced_stage") or None
            result_data["deals"] = deals_data.get("deals", [])

        # 3. Check contact
        if contact_email:
            contact_result = check_contact_exists(contact_email)
            contact_data = contact_result.get("data", {})
            result_data["contact_exists"] = contact_data.get("exists", False)

        return {"success": True, "data": result_data, "error": None}

    except Exception as e:
        return {"success": False, "data": {}, "error": str(e)}


if __name__ == "__main__":
    # Quick test
    import json

    print("=== HubSpot Lookup Tool Test ===\n")

    test_domains = ["magnifica.com.co", "barbaroja.com.co", "dominio-que-no-existe-xyz.com"]

    for domain in test_domains:
        print(f"Domain: {domain}")
        result = hubspot_enrich(domain)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        print()
