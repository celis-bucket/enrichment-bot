"""
Fetch all unresolved feedback from Supabase, organized by section.

Produces a structured prompt for Claude Code to review and plan fixes.

Usage:
    cd tools && python -m feedback.fetch_unresolved
"""

import os
import sys

_tools_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _tools_dir not in sys.path:
    sys.path.insert(0, _tools_dir)

from export.supabase_writer import get_client, get_all_unresolved_feedback

SECTION_NAMES = {
    "overview": "Company Overview (Analyze)",
    "instagram": "Instagram Data (Analyze)",
    "catalog": "Product Catalog (Analyze)",
    "contacts": "Contacts / Apollo (Analyze)",
    "meta_ads": "Meta Ads (Analyze)",
    "prediction": "Order Predictions (Analyze)",
    "traffic": "Traffic & Demand (Analyze)",
    "hubspot": "HubSpot CRM (Analyze)",
    "tiktok_ads": "TikTok Ads (Analyze)",
    "general": "General (Analyze)",
    "retail": "Retail Channels (Retail)",
    "leads": "Leads Dashboard",
}


def fetch_unresolved_feedback() -> dict:
    """
    Fetch all unresolved feedback, group by section, and generate a prompt.

    Returns:
        {'success': bool, 'data': {'by_section': dict, 'total': int, 'prompt': str}, 'error': str|None}
    """
    try:
        client = get_client()
        rows = get_all_unresolved_feedback(client)

        if not rows:
            return {
                "success": True,
                "data": {"by_section": {}, "total": 0, "prompt": "No hay feedback pendiente."},
                "error": None,
            }

        # Group by section
        by_section = {}
        for row in rows:
            section = row.get("section", "unknown")
            by_section.setdefault(section, []).append({
                "id": row.get("id"),
                "domain": row.get("domain"),
                "comment": row.get("comment"),
                "suggested_value": row.get("suggested_value"),
                "created_by": row.get("created_by", "anonymous"),
                "created_at": row.get("created_at"),
            })

        # Build prompt
        prompt = _build_prompt(by_section, len(rows))

        return {
            "success": True,
            "data": {"by_section": by_section, "total": len(rows), "prompt": prompt},
            "error": None,
        }
    except Exception as e:
        return {"success": False, "data": {}, "error": str(e)}


def _build_prompt(by_section: dict, total: int) -> str:
    """Build a structured prompt for Claude Code review."""
    lines = [
        f"Necesito revisar y actuar sobre {total} items de feedback de usuarios del Enrichment Agent.",
        "Para cada item, determina si requiere: fix de código, corrección de datos, o descarte.",
        "",
    ]

    for section, items in by_section.items():
        display_name = SECTION_NAMES.get(section, section.title())
        lines.append(f"## {display_name} ({len(items)} items)")
        lines.append("")

        for item in items:
            domain = item["domain"] or "unknown"
            date = (item["created_at"] or "")[:10]
            lines.append(f"### {domain} — {date}")
            lines.append(f"**Feedback**: {item['comment']}")
            suggested = item.get("suggested_value") or "Ninguno"
            lines.append(f"**Valor sugerido**: {suggested}")
            lines.append(f"**Reportado por**: {item['created_by']}")
            lines.append(f"**ID**: {item['id']}")
            lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("Para cada item responde:")
    lines.append("1. Acción requerida (código / datos / descartar)")
    lines.append("2. Archivos a modificar (si aplica)")
    lines.append("3. Prioridad (alta / media / baja)")

    return "\n".join(lines)


if __name__ == "__main__":
    result = fetch_unresolved_feedback()
    if result["success"]:
        total = result["data"]["total"]
        print(f"\n{'='*60}")
        print(f"Feedback pendiente: {total} items")
        print(f"{'='*60}\n")
        if total > 0:
            by_section = result["data"]["by_section"]
            for section, items in by_section.items():
                display = SECTION_NAMES.get(section, section)
                print(f"  {display}: {len(items)} items")
            print(f"\n{'='*60}")
            print("PROMPT PARA CLAUDE CODE:")
            print(f"{'='*60}\n")
            print(result["data"]["prompt"])
    else:
        print(f"Error: {result['error']}")
