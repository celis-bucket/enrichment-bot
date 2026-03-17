"""
Supabase writer for enrichment results.

Replaces Google Sheets as the persistence layer. Uses the lightweight
SupabaseClient from tools/logistics/ (PostgREST, no heavy SDK).

Usage:
    from export.supabase_writer import get_client, upsert_enrichment, check_domain_exists
    client = get_client()
    upsert_enrichment(client, enrichment_result, prediction)
"""

import os
import sys

# Ensure logistics package is importable
_tools_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _tools_dir not in sys.path:
    sys.path.insert(0, _tools_dir)

from logistics.supabase_client import SupabaseClient

TABLE = "enriched_companies"


def get_client() -> SupabaseClient:
    """Return a SupabaseClient using env vars (SUPABASE_URL, SUPABASE_SERVICE_KEY)."""
    return SupabaseClient()


def upsert_enrichment(client: SupabaseClient, enrichment_result, prediction: dict = None) -> dict:
    """
    Upsert a single enrichment result into Supabase.

    Uses domain as the conflict key — re-enriching the same domain overwrites.

    Args:
        client: SupabaseClient instance
        enrichment_result: EnrichmentResult dataclass
        prediction: Optional dict with predicted_orders_p10/p50/p90, prediction_confidence

    Returns:
        The upserted row dict from Supabase
    """
    row = enrichment_result.to_supabase_dict(prediction=prediction)
    # Remove fields not in the Supabase table
    row.pop("id", None)
    row.pop("created_at", None)
    row.pop("updated_at", None)
    result = client.upsert(TABLE, row, on_conflict="domain")
    return result[0] if result else {}


def upsert_enrichment_batch(client: SupabaseClient, rows: list[dict]) -> list[dict]:
    """
    Batch upsert multiple enrichment rows.

    Args:
        client: SupabaseClient instance
        rows: List of dicts (already converted via to_supabase_dict)

    Returns:
        List of upserted row dicts
    """
    for row in rows:
        row.pop("id", None)
        row.pop("created_at", None)
        row.pop("updated_at", None)
    return client.upsert(TABLE, rows, on_conflict="domain")


def check_domain_exists(client: SupabaseClient, domain: str) -> dict:
    """
    Check if a domain already exists in the enriched_companies table.

    Args:
        client: SupabaseClient instance
        domain: Domain to check (e.g. "armatura.com.co")

    Returns:
        Dict with 'exists' (bool), 'domain' (str), and optionally 'last_analyzed' (str)
    """
    domain_clean = domain.lower().strip()
    rows = client.select(
        TABLE,
        columns="domain,updated_at",
        eq={"domain": domain_clean},
        limit=1,
    )
    if rows:
        return {
            "exists": True,
            "domain": domain_clean,
            "last_analyzed": rows[0].get("updated_at"),
        }
    return {"exists": False, "domain": domain_clean}


def read_existing_domains(client: SupabaseClient) -> set[str]:
    """
    Read all domains from the enriched_companies table.

    Used by batch_runner for resume/dedup.

    Returns:
        Set of domain strings
    """
    rows = client.select(TABLE, columns="domain")
    return {r["domain"] for r in rows if r.get("domain")}


def ping(client: SupabaseClient) -> bool:
    """Test connectivity by selecting one row."""
    try:
        client.select(TABLE, limit=1)
        return True
    except Exception:
        return False
