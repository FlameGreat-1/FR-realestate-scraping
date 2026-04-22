import asyncio
import httpx
from .domain_manager import deduplicate_domains
from .input_paths import resolve_input_csv_path
from .storage import init_storage, write_listings, write_error
from .extractors.generic import extract_listings_from_domain
import dataclasses

CSV_PATH = resolve_input_csv_path()
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
}


async def probe_site(url: str, client: httpx.AsyncClient) -> int | None:
    for method in ("head", "get"):
        try:
            response = await getattr(client, method)(url, timeout=8.0)
            return response.status_code
        except Exception:
            continue
    return None

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
                probe_status = await probe_site(domain_info['url'], client)
                print(f"  -> No listings via fast method for {domain}. Trying Playwright...")
                from .extractors.playwright_extractor import extract_listings_playwright
                listings = await extract_listings_playwright(domain_info)
            
            if not listings:
                if probe_status in (401, 403, 429):
                    write_error(
                        domain,
                        "blocked",
                        f"HTTP probe returned {probe_status}; Playwright also found no usable listings",
                    )
                elif probe_status is None or probe_status >= 500:
                    write_error(domain, "unreachable", "Site did not respond to HTTP probe and Playwright found no usable listings")
                else:
                    write_error(domain, "no_listings", "Could not find listings on site with either method")
                return

            listings = [listing for listing in listings if getattr(listing, "price", "").strip()]
            if not listings:
                write_error(domain, "no_price", "Listings were found but no reliable price could be extracted")
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
        
    # Bounded concurrency: keep several domains in flight to reduce total runtime.
    semaphore = asyncio.Semaphore(12)
    
    async with httpx.AsyncClient(
        verify=False,
        timeout=20.0,
        follow_redirects=True,
        headers=DEFAULT_HEADERS,
    ) as client:
        # We run all processed domains concurrently now with the semaphore
        tasks = [process_domain(d, client, semaphore) for d in domains_list if d.get('domain')]
        await asyncio.gather(*tasks)
    
    # Final step: Global Deduplication
    print("\nExecuting global deduplication cleanup...")
    deduplicate_final_csv()

if __name__ == "__main__":
    asyncio.run(run_pipeline())
