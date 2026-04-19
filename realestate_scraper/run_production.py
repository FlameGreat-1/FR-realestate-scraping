import asyncio
from scraper.pipeline import run_pipeline
import os
from pathlib import Path

async def main():
    print("Starting Unified Real Estate Scraper Production Run...")
    
    # Ensure a clean state for the consolidated run
    output_dir = Path("output")
    if not output_dir.exists():
        output_dir.mkdir()
    
    files_to_clean = [output_dir / "listings_consolidated.csv", output_dir / "error_log.csv"]
    for f in files_to_clean:
        if f.exists():
            f.unlink()
            print(f"Cleared existing {f.name}")
            
    await run_pipeline()
    print("\nProduction Run Complete.")
    print("Output files:")
    print("  - output/listings_consolidated.csv")
    print("  - output/error_log.csv")

if __name__ == "__main__":
    asyncio.run(main())
