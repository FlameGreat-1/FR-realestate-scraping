import csv
from pathlib import Path
from typing import Dict, List, Any

OUTPUT_DIR = Path(__file__).resolve().parents[1] / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

LISTINGS_CSV = OUTPUT_DIR / "listings_consolidated.csv"
ERROR_LOG_CSV = OUTPUT_DIR / "error_log.csv"

LISTINGS_HEADERS = [
    "reference_id", "domain", "price", "property_type", "location", 
    "surface_area", "rooms", "bedrooms", "agency_name", 
    "agent_name", "phone", "email", "coordinates", "dpe_rating", "url"
]

ERROR_HEADERS = [
    "domain", "status", "reason"
]

def init_storage():
    # Always write headers (run_production clears the files before calling this)
    with LISTINGS_CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=LISTINGS_HEADERS)
        writer.writeheader()
    
    with ERROR_LOG_CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=ERROR_HEADERS)
        writer.writeheader()

def write_listings(listings: List[Dict[str, Any]]) -> None:
    if not listings:
        return
    with LISTINGS_CSV.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=LISTINGS_HEADERS, extrasaction='ignore')
        for row in listings:
            writer.writerow(row)

def write_error(domain: str, status: str, reason: str = "") -> None:
    with ERROR_LOG_CSV.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=ERROR_HEADERS)
        writer.writerow({
            "domain": domain,
            "status": status,
            "reason": reason
        })

def deduplicate_final_csv():
    import pandas as pd
    if not LISTINGS_CSV.exists():
        return
    
    df = pd.read_csv(LISTINGS_CSV, dtype=str).fillna("")
    if df.empty:
        return
        
    initial_count = len(df)
    
    # Strategy 1: Unique Reference IDs per domain
    # Some sites might reuse IDs across domains, so we keep (domain, reference_id) unique
    if 'reference_id' in df.columns:
        # Create a helper key for rows that have a reference_id
        # For rows without reference_id, we'll keep them for Strategy 2
        df_with_id = df[df['reference_id'] != ""]
        df_no_id = df[df['reference_id'] == ""]
        
        df_with_id = df_with_id.drop_duplicates(subset=['domain', 'reference_id'], keep='first')
        df = pd.concat([df_with_id, df_no_id])

    # Strategy 2: Exact row identity when a reference ID is missing.
    # Avoid collapsing distinct listings just because they share the same price/location mix.
    if 'url' in df.columns:
        df = df.drop_duplicates(subset=['domain', 'url'], keep='first')

    final_count = len(df)
    df.to_csv(LISTINGS_CSV, index=False, encoding='utf-8')
    print(f"Global Deduplication: Reduced {initial_count} -> {final_count} listings.")
