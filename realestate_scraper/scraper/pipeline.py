import asyncio
import httpx
from pathlib import Path
from .domain_manager import deduplicate_domains
from .storage import init_storage, write_listings, write_error
from .extractors.generic import extract_listings_from_domain
import dataclasses

CSV_PATH = Path(__file__).resolve().parents[2] / "FR_realestate_scraping - FR 140 (1).csv"

async def process_domain(domain_info: dict, client: httpx.AsyncClient, semaphore: asyncio.Semaphore):
    async with semaphore:
        domain = domain_info['domain']
        print(f"Processing {domain}...")
        try:
            # Phase 1: Heuristic / Fast extraction
            listings = await extract_listings_from_domain(domain_info, client)
            
            # Phase 2: Playwright fallback — but only if site is reachable
            if not listings:
                # Quick reachability probe (8s) before spending 40s on Playwright
                try:
                    probe = await client.head(domain_info['url'], timeout=8.0)
                    reachable = probe.status_code < 500
                except Exception:
                    reachable = False

                if not reachable:
                    write_error(domain, "unreachable", "Site did not respond to HTTP probe — skipping Playwright")
                    print(f"  -> Unreachable, skipping Playwright for {domain}")
                    return

                print(f"  -> No listings via fast method for {domain}. Trying Playwright...")
                from .extractors.playwright_extractor import extract_listings_playwright
                listings = await extract_listings_playwright(domain_info)
            
            if not listings:
                write_error(domain, "no_listings", "Could not find listings on site with either method")
                return
                
            # Convert to dicts for CSV
            listings_dicts = [dataclasses.asdict(l) for l in listings]
            write_listings(listings_dicts)
            print(f"  -> Found {len(listings)} listings for {domain}")
            
        except httpx.RequestError as e:
            write_error(domain, "failed", str(e))
            print(f"  -> Failed (Network): {e}")
        except Exception as e:
            write_error(domain, "error", str(e))
            print(f"  -> Error: {e}")

async def run_pipeline(limit=None):
    from .storage import deduplicate_final_csv
    init_storage()
    if not CSV_PATH.exists():
        print(f"CSV missing: {CSV_PATH}")
        return
        
    domains_map, no_website_entries = deduplicate_domains(str(CSV_PATH))
    print(f"Deduplicated to {len(domains_map)} unique domains out of original CSV.")
    
    # Log entries with no website as requested
    for agency in no_website_entries:
        write_error(agency, "no_website", "Initial input had no website URL")
    
    domains_list = list(domains_map.values())
    if limit is not None:
        domains_list = domains_list[:limit]
        
    # Bounded concurrency: 3 sites at a time
    semaphore = asyncio.Semaphore(3)
    
    async with httpx.AsyncClient(verify=False, timeout=20.0, follow_redirects=True) as client:
        # We run all processed domains concurrently now with the semaphore
        tasks = [process_domain(d, client, semaphore) for d in domains_list if d.get('domain')]
        await asyncio.gather(*tasks)
    
    # Final step: Global Deduplication
    print("\nExecuting global deduplication cleanup...")
    deduplicate_final_csv()

if __name__ == "__main__":
    asyncio.run(run_pipeline())
