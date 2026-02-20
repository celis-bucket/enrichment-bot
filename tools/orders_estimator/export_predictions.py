"""
Google Sheets prediction export for the Orders Estimator.

Appends prediction columns to an existing enrichment Google Sheet,
or writes predictions to a new worksheet tab.
"""

import os
import sys
from datetime import datetime
from typing import Dict, Any, Optional

import pandas as pd

_TOOLS_DIR = os.path.join(os.path.dirname(__file__), "..")
if _TOOLS_DIR not in sys.path:
    sys.path.insert(0, _TOOLS_DIR)

from export.google_sheets_writer import (
    get_gspread_client,
    create_or_open_spreadsheet,
    append_rows,
)
from .config import PREDICTION_COLUMNS


EXPORT_HEADERS = [
    "domain",
    "predicted_orders_p10",
    "predicted_orders_p50",
    "predicted_orders_p90",
    "prediction_confidence",
    "model_version",
    "predicted_at",
]

BUFFER_SIZE = 10


def export_to_google_sheet(
    predictions_df: pd.DataFrame,
    spreadsheet_url: str,
    worksheet_name: str = "predictions",
    domain_column: str = "domain",
) -> Dict[str, Any]:
    """
    Write predictions to a worksheet tab in an existing enrichment Google Sheet.

    Args:
        predictions_df: DataFrame with domain + prediction columns.
        spreadsheet_url: Existing enrichment sheet URL.
        worksheet_name: Tab name for predictions.
        domain_column: Column to use as key.

    Returns:
        {success, data: {sheet_url, rows_written, worksheet_name}, error}
    """
    try:
        client = get_gspread_client()
        sheet_result = create_or_open_spreadsheet(
            client,
            spreadsheet_url=spreadsheet_url,
            worksheet_name=worksheet_name,
        )

        if not sheet_result["success"]:
            return sheet_result

        worksheet = sheet_result["data"]["worksheet"]
        sheet_url = sheet_result["data"]["sheet_url"]

        # Write headers if first row is empty
        first_row = worksheet.row_values(1)
        if not first_row:
            worksheet.append_row(EXPORT_HEADERS, value_input_option="USER_ENTERED")

        # Prepare rows
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
        rows = []
        for _, row in predictions_df.iterrows():
            rows.append([
                row.get(domain_column, ""),
                int(row.get("predicted_orders_p10", 0)),
                int(row.get("predicted_orders_p50", 0)),
                int(row.get("predicted_orders_p90", 0)),
                row.get("prediction_confidence", ""),
                row.get("model_version", ""),
                now_str,
            ])

        # Write in buffered chunks
        total_written = 0
        for i in range(0, len(rows), BUFFER_SIZE):
            chunk = rows[i:i + BUFFER_SIZE]
            result = append_rows(worksheet, chunk)
            if not result["success"]:
                return {
                    "success": False,
                    "data": {"rows_written": total_written},
                    "error": result["error"],
                }
            total_written += result["data"]["rows_written"]

        print(f"  Exported {total_written} predictions to '{worksheet_name}' tab")
        return {
            "success": True,
            "data": {
                "sheet_url": sheet_url,
                "rows_written": total_written,
                "worksheet_name": worksheet_name,
            },
            "error": None,
        }

    except Exception as e:
        return {
            "success": False,
            "data": {},
            "error": f"Export error: {str(e)}",
        }


def read_enrichment_from_sheet(
    spreadsheet_url: str,
    worksheet_name: Optional[str] = None,
) -> pd.DataFrame:
    """
    Read enrichment data from a Google Sheet into a DataFrame.

    Args:
        spreadsheet_url: Google Sheet URL.
        worksheet_name: Specific tab to read from (default: first sheet).

    Returns:
        DataFrame with enrichment data.
    """
    client = get_gspread_client()

    spreadsheet = client.open_by_url(spreadsheet_url)
    if worksheet_name:
        worksheet = spreadsheet.worksheet(worksheet_name)
    else:
        worksheet = spreadsheet.sheet1

    data = worksheet.get_all_records()
    df = pd.DataFrame(data)

    # Replace empty strings with NaN for numeric columns
    df = df.replace("", pd.NA)

    return df
