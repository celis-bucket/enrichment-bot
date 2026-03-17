"""
Seed companies into Supabase for the Logistics Crisis Monitor.

Purpose: Bulk-insert the initial list of monitored companies.
Inputs: Hardcoded list (edit COMPANIES below) or CSV file
Outputs: Inserted rows in Supabase `companies` table
Dependencies: requests, dotenv

Usage:
    python tools/logistics/seed_companies.py
    python tools/logistics/seed_companies.py --file companies.csv
"""

import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '..', '.env'))

from logistics.supabase_client import SupabaseClient


# Initial company list from the batch test
COMPANIES = [
    {"ig_username": "medipiel", "name": "Medipiel", "country": "CO"},
    {"ig_username": "ollie.colombia", "name": "Ollie Colombia", "country": "CO"},
    {"ig_username": "trendyshopbtanew", "name": "Trendy Shop", "country": "CO"},
    {"ig_username": "lapocionoficial", "name": "La Poción Oficial", "country": "CO"},
    {"ig_username": "savvynutricion", "name": "Savvy Nutrición", "country": "CO"},
    {"ig_username": "divalash.co", "name": "Divalash", "country": "CO"},
    {"ig_username": "beautyboost.col", "name": "Beauty Boost", "country": "CO"},
    {"ig_username": "dynamo_live", "name": "Dynamo Live", "country": "CO"},
    {"ig_username": "undergold_", "name": "Undergold", "country": "CO"},
    {"ig_username": "armaturaco", "name": "Armatura", "country": "CO"},
    {"ig_username": "accesoriosavemaria", "name": "Accesorios Ave María", "country": "CO"},
    {"ig_username": "myhuevos.co", "name": "My Huevos", "country": "CO"},
    {"ig_username": "lummia.col", "name": "Lummia", "country": "CO"},
    {"ig_username": "nipskin.stickwear", "name": "NipSkin Stickwear", "country": "CO"},
    {"ig_username": "flypasscolombia", "name": "Flypass Colombia", "country": "CO"},
    {"ig_username": "maledenim", "name": "Male Denim", "country": "CO"},
    {"ig_username": "vitasei.col", "name": "Vitasei", "country": "CO"},
    {"ig_username": "entrelazosaccesorios", "name": "Entrelazos Accesorios", "country": "CO"},
    {"ig_username": "true_________________", "name": "True", "country": "CO"},
    {"ig_username": "rebel_colombia", "name": "Rebel Colombia", "country": "CO"},
]


def seed_companies(companies: list = None):
    """Insert companies into Supabase. Uses upsert to skip duplicates."""
    client = SupabaseClient()
    companies = companies or COMPANIES

    inserted = 0
    errors = 0

    for company in companies:
        try:
            client.upsert("companies", company, on_conflict="ig_username")
            inserted += 1
            print(f"  + @{company['ig_username']} ({company['name']})")
        except Exception as e:
            errors += 1
            print(f"  ! @{company['ig_username']} ERROR: {e}")

    print(f"\nDone. Upserted: {inserted}, Errors: {errors}")


def seed_from_csv(filepath: str):
    """Read companies from a CSV file (columns: ig_username, name, country)."""
    import csv
    companies = []
    with open(filepath, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            companies.append({
                "ig_username": row["ig_username"].strip().lstrip("@"),
                "name": row["name"].strip(),
                "country": row.get("country", "CO").strip(),
            })
    print(f"Read {len(companies)} companies from {filepath}")
    seed_companies(companies)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Seed companies into Supabase")
    parser.add_argument("--file", help="CSV file with ig_username, name, country columns")
    args = parser.parse_args()

    print("Seeding companies into Supabase...")
    print("=" * 50)

    if args.file:
        seed_from_csv(args.file)
    else:
        print(f"Using hardcoded list ({len(COMPANIES)} companies)\n")
        seed_companies()
