import asyncio
from pathlib import Path
from typing import List, Dict, Any
import csv
import dataclasses

from .domain_manager import deduplicate_domains
from .storage import write_listings, ERROR_LOG_CSV
from .extractors.playwright_extractor import extract_listings_playwright

CSV_PATH = Path(__file__).resolve().parents[2] / "FR_realestate_scraping - FR 140 (1).csv"

async def process_playwright_domain(domain_info: dict):
    domain = domain_info['domain']
    print(f"Playwright Action: Processing {domain}...")
    try:
        listings = await extract_listings_playwright(domain_info)
        if not listings:
            print(f"  -> [Playwright] Still no listings for {domain}")
            return
            
        listings_dicts = [dataclasses.asdict(l) for l in listings]
        write_listings(listings_dicts)
        print(f"  -> [Playwright] Rescued {len(listings)} listings for {domain}!")
        
    except Exception as e:
        print(f"  -> [Playwright] Failed: {type(e).__name__} - {e}")

async def run_playwright_pipeline(limit=None):
    if not ERROR_LOG_CSV.exists() or not CSV_PATH.exists():
        print("Missing required output/error_log.csv or original CSV.")
        return
        
    failed_domains = set()
    with ERROR_LOG_CSV.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f, fieldnames=['domain', 'status', 'reason'])
        for row in reader:
            if row['status'] in ('no_listings', 'failed', 'error'):
                failed_domains.add(row['domain'])
                
    if not failed_domains:
        print("No failed domains to process via Playwright!")
        return
        
    print(f"Identified {len(failed_domains)} failed domains. Spinning up Playwright...")
    
    # Retrieve the root domain_info objects
    domains_map = deduplicate_domains(str(CSV_PATH))
    job_queue = [domains_map[d] for d in failed_domains if d in domains_map]
    
    if limit is not None:
        job_queue = job_queue[:limit]
        
    for domain_info in job_queue:
        await process_playwright_domain(domain_info)

if __name__ == "__main__":
    asyncio.run(run_playwright_pipeline())
