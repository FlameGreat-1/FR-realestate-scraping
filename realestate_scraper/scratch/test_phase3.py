import asyncio
import httpx
import dataclasses
from scraper.pipeline import run_pipeline
from scraper.storage import init_storage, write_listings
from scraper.domain_manager import deduplicate_domains
from scraper.extractors.generic import extract_listings_from_domain

async def test_run():
    init_storage()
    domains_map = deduplicate_domains('c:/Users/abcre/Desktop/Project/F_realestate/FR_realestate_scraping - FR 140 (1).csv')
    test_domains = list(domains_map.values())[:3]
    
    async with httpx.AsyncClient(verify=False, timeout=30.0) as client:
        for domain_info in test_domains:
            print(f"Testing {domain_info['domain']}...")
            try:
                listings = await extract_listings_from_domain(domain_info, client)
                print(f"  -> Found {len(listings)} listings")
                if listings:
                    write_listings([dataclasses.asdict(l) for l in listings])
            except Exception as e:
                print(f"  -> Failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_run())
