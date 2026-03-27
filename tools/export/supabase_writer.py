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


# ===== Feedback =====

FEEDBACK_TABLE = "enrichment_feedback"


def insert_feedback(
    client: SupabaseClient,
    domain: str,
    section: str,
    comment: str,
    suggested_value: str = None,
    created_by: str = "anonymous",
) -> dict:
    """
    Insert a feedback record for an enrichment section.

    Args:
        client: SupabaseClient instance
        domain: Company domain
        section: Section name (overview, instagram, catalog, traffic, meta_ads, contacts, prediction, general)
        comment: Free-form feedback text
        suggested_value: Optional corrected value
        created_by: User identifier

    Returns:
        The inserted row dict from Supabase
    """
    row = {
        "domain": domain.lower().strip(),
        "section": section,
        "comment": comment,
        "created_by": created_by or "anonymous",
    }
    if suggested_value:
        row["suggested_value"] = suggested_value

    result = client.insert(FEEDBACK_TABLE, row)
    return result[0] if result else {}


def get_feedback(client: SupabaseClient, domain: str) -> list[dict]:
    """
    Get all feedback for a domain, newest first.

    Args:
        client: SupabaseClient instance
        domain: Company domain

    Returns:
        List of feedback dicts
    """
    return client.select(
        FEEDBACK_TABLE,
        eq={"domain": domain.lower().strip()},
        order="created_at.desc",
    )


def get_all_unresolved_feedback(client: SupabaseClient) -> list[dict]:
    """
    Get all unresolved feedback across all domains, newest first.

    Returns:
        List of feedback dicts where resolved_at IS NULL
    """
    return client.select(
        FEEDBACK_TABLE,
        is_null={"resolved_at": True},
        order="created_at.desc",
    )


def resolve_feedback(client: SupabaseClient, feedback_id: str, resolved_note: str = None) -> dict:
    """
    Mark a feedback item as resolved.

    Args:
        client: SupabaseClient instance
        feedback_id: UUID of the feedback row
        resolved_note: Optional note explaining the resolution

    Returns:
        The updated row dict from Supabase
    """
    from datetime import datetime, timezone

    data = {"resolved_at": datetime.now(timezone.utc).isoformat()}
    if resolved_note:
        data["resolved_note"] = resolved_note

    result = client.update(FEEDBACK_TABLE, data, eq={"id": feedback_id})
    return result[0] if result else {}
