import asyncio
import sys
import os
import pandas as pd
from pathlib import Path
from dataclasses import asdict

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scraper.domain_manager import deduplicate_domains
from scraper.extractors.generic import extract_listings_from_domain
from scraper.storage import write_listings, init_storage
import httpx

async def live_run():
    print("=== Phase 3 Live Verification Execution ===")
    print("Mandated Fields: location, coordinates, email")
    init_storage()
    
    csv_path = r'c:\Users\abcre\Desktop\Project\F_realestate\FR_realestate_scraping - FR 140 (1).csv'
    domains_map, no_website_entries = deduplicate_domains(csv_path)
    print(f"Deduplicated to {len(domains_map)} unique domains out of original CSV.")
    
    # Take 5 diverse domains to show breadth, prioritized by likely success
    target_domains = [
        "rhpatrimoine.com", 
        "agence-centrale-immobilier.fr",
        "immobilier-pays-basque.com"
    ]
    
    active_domains = [domains_map[d] for d in target_domains if d in domains_map]
    
    all_extracted = []
    
    async with httpx.AsyncClient(verify=False, timeout=30.0, follow_redirects=True) as client:
        for domain_info in active_domains:
            print(f"\n--- Harvesting: {domain_info['domain']} ---")
            try:
                listings = await extract_listings_from_domain(domain_info, client)
                # Cap for visual feedback in logs
                to_show = listings[:3]
                if not listings:
                    print(f" [!] No listings found for {domain_info['domain']}")
                    continue
                    
                for l in to_show:
                    print(f" [+] Found: {l.property_type or 'Listing'} in {l.location or 'Unknown'}")
                    print(f"     Coord: {l.coordinates or 'MISSING'}")
                    print(f"     Email: {l.email or 'MISSING'}")
                
                all_extracted.extend(listings)
                # Write after each domain
                if listings:
                    listings_dicts = [asdict(l) for l in listings]
                    write_listings(listings_dicts)
                    print(f" [OK] Committed {len(listings)} listings for {domain_info['domain']} to CSV.")
            except Exception as e:
                print(f" [!] Error on {domain_info['domain']}: {e}")

    if all_extracted:
        df = pd.DataFrame([asdict(l) for l in all_extracted])
        print("\n=== FINAL FILL-RATE REPORT ===")
        for col in ['location', 'coordinates', 'email']:
            # Non-empty and not None
            fill = df[col].apply(lambda x: bool(str(x).strip())).sum() / len(df) * 100
            print(f" - {col:12}: {fill:6.1f}%")
        print(f"Total yields: {len(all_extracted)}")
        print(f"\nData saved to: output/listings_consolidated.csv")

if __name__ == "__main__":
    asyncio.run(live_run())
