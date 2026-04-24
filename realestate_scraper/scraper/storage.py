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
    if not LISTINGS_CSV.exists():
        return
    
    with LISTINGS_CSV.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    if not rows:
        return

    initial_count = len(rows)
    seen_ref = set()
    seen_url = set()
    deduped = []

    for row in rows:
        domain = row.get("domain", "")
        reference_id = row.get("reference_id", "").strip()
        url = row.get("url", "").strip()

        if reference_id:
            ref_key = (domain, reference_id)
            if ref_key in seen_ref:
                continue
            seen_ref.add(ref_key)
        elif url:
            url_key = (domain, url)
            if url_key in seen_url:
                continue
            seen_url.add(url_key)

        deduped.append(row)

    final_count = len(deduped)
    with LISTINGS_CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=LISTINGS_HEADERS)
        writer.writeheader()
        writer.writerows(deduped)
    print(f"Global Deduplication: Reduced {initial_count} -> {final_count} listings.")
