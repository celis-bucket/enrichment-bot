"""
Lightweight Supabase REST client using requests.

Avoids the heavy `supabase` Python package and its dependency tree.
Talks directly to PostgREST (Supabase's REST API layer).

Usage:
    from logistics.supabase_client import SupabaseClient
    client = SupabaseClient()  # reads from env
    rows = client.select("companies", eq={"is_active": True})
    client.insert("scans", {"company_id": "...", "risk_score": 42})
"""

import os
from typing import Any
import requests


class SupabaseClient:
    """Minimal Supabase REST client (PostgREST wrapper)."""

    def __init__(self, url: str = None, key: str = None):
        self.url = (url or os.getenv("SUPABASE_URL", "")).rstrip("/")
        self.key = key or os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_ANON_KEY")

        if not self.url or not self.key:
            raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_KEY (or SUPABASE_ANON_KEY) required")

        self.rest_url = f"{self.url}/rest/v1"
        self.headers = {
            "apikey": self.key,
            "Authorization": f"Bearer {self.key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        }

    def select(
        self,
        table: str,
        columns: str = "*",
        eq: dict = None,
        gte: dict = None,
        in_: dict = None,
        order: str = None,
        limit: int = None,
    ) -> list[dict]:
        """
        SELECT from a table or view.

        Args:
            table: Table or view name
            columns: Comma-separated column names (default: *)
            eq: Equality filters {column: value}
            gte: Greater-than-or-equal filters {column: value}
            in_: IN filters {column: [values]}
            order: Order clause, e.g. "scanned_at.desc"
            limit: Max rows to return

        Returns:
            List of row dicts
        """
        params = {"select": columns}

        if eq:
            for col, val in eq.items():
                params[col] = f"eq.{val}"

        if gte:
            for col, val in gte.items():
                params[col] = f"gte.{val}"

        if in_:
            for col, vals in in_.items():
                formatted = ",".join(str(v) for v in vals)
                params[col] = f"in.({formatted})"

        if order:
            params["order"] = order

        if limit:
            params["limit"] = str(limit)

        resp = requests.get(
            f"{self.rest_url}/{table}",
            headers=self.headers,
            params=params,
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()

    def insert(self, table: str, data: dict | list[dict]) -> list[dict]:
        """
        INSERT one or more rows into a table.

        Args:
            table: Table name
            data: Single row dict or list of row dicts

        Returns:
            List of inserted rows (with generated fields like id)
        """
        if isinstance(data, dict):
            data = [data]

        resp = requests.post(
            f"{self.rest_url}/{table}",
            headers=self.headers,
            json=data,
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()

    def upsert(self, table: str, data: dict | list[dict], on_conflict: str = None) -> list[dict]:
        """
        UPSERT (insert or update on conflict).

        Args:
            table: Table name
            data: Row(s) to upsert
            on_conflict: Column name for conflict resolution

        Returns:
            List of upserted rows
        """
        if isinstance(data, dict):
            data = [data]

        headers = {**self.headers}
        resolution = f"merge-duplicates"
        if on_conflict:
            headers["Prefer"] = f"return=representation,resolution={resolution}"
        else:
            headers["Prefer"] = f"return=representation,resolution={resolution}"

        params = {}
        if on_conflict:
            params["on_conflict"] = on_conflict

        resp = requests.post(
            f"{self.rest_url}/{table}",
            headers=headers,
            json=data,
            params=params,
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()

    def rpc(self, function_name: str, params: dict = None) -> Any:
        """Call a Supabase RPC function."""
        resp = requests.post(
            f"{self.rest_url}/rpc/{function_name}",
            headers=self.headers,
            json=params or {},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()

    def ping(self) -> bool:
        """Test connectivity by selecting from companies."""
        try:
            self.select("companies", limit=1)
            return True
        except Exception:
            return False
