import sys
import asyncio
from pathlib import Path

# Add the project root to python path so that 'scraper' is solvable
sys.path.insert(0, str(Path(__file__).resolve().parent))

from scraper.pipeline import run_pipeline

if __name__ == "__main__":
    print("Starting the real-estate scraper pipeline on ALL domains...")
    # Passing limit=None to run on all domains.
    asyncio.run(run_pipeline(limit=None))
