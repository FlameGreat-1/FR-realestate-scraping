import asyncio
import httpx
import dataclasses
from scraper.extractors.generic import extract_listings_from_domain
from scraper.storage import init_storage, write_listings
from scraper.domain_manager import deduplicate_domains

async def test_run():
    init_storage()
    # Deduplicate domains to get metadata (city, postalcode)
    domains_map = deduplicate_domains('c:/Users/abcre/Desktop/Project/F_realestate/FR_realestate_scraping - FR 140 (1).csv')
    
    # Test rhpatrimoine.com specifically as it had listings before
    if 'rhpatrimoine.com' not in domains_map:
        print("Domain not found in map")
        return
        
    target = domains_map['rhpatrimoine.com']
    print(f"Testing {target['domain']} with Phase 3 logic...")
    
    async with httpx.AsyncClient(verify=False, timeout=30.0) as client:
        try:
            listings = await extract_listings_from_domain(target, client)
            print(f"Found {len(listings)} listings")
            if listings:
                write_listings([dataclasses.asdict(l) for l in listings])
                print("Successfully wrote listings to CSV")
        except Exception as e:
            print(f"Extraction failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_run())
