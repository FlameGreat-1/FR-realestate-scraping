import asyncio
import pandas as pd
import httpx
from prefect import flow, task, get_run_logger
from prefect.tasks import task_input_hash
from .data_models import CompanyInfo
from .pattern_finder import discover_patterns
from .storage import store_company_info
from .input_paths import resolve_input_csv_path

CSV_PATH = resolve_input_csv_path()

@task(retries=2, retry_delay_seconds=5)
async def fetch_html(url: str) -> str:
    logger = get_run_logger()
    async with httpx.AsyncClient(follow_redirects=True, timeout=30.0, verify=False) as client:
        try:
            response = await client.get(url)
            response.raise_for_status()
            logger.info(f"Fetched {url} (status {response.status_code})")
            return response.text
        except Exception as e:
            logger.error(f"Error fetching {url}: {e}")
            return ""

@task
def process_company(row: pd.Series) -> None:
    logger = get_run_logger()
    website = str(row.get('website') or row.get('Website') or row.get('website_url') or "").strip()
    if not website:
        logger.warning(f"No website for {row.get('company_name')}, skipping")
        return
    # Ensure URL has scheme
    if not website.startswith('http'):
        website = f"https://{website}"
    html = asyncio.run(fetch_html(website))
    if not html:
        logger.warning(f"Empty HTML for {website}, skipping")
        return
    patterns = discover_patterns(website, html)
    company = CompanyInfo(
        company_name=row.get('company_name') or row.get('Company') or "",
        website=website,
        contact_url=patterns.get('contact_url'),
        listings_url=patterns.get('listings_url'),
        meta_title=patterns.get('meta_title'),
        meta_description=patterns.get('meta_description'),
        social_links=patterns.get('social_links') or [],
    )
    store_company_info(company.__dict__)
    logger.info(f"Processed {company.company_name}")

@flow(name="realestate-scraper-flow")
def scraper_flow(limit: int = None) -> None:
    logger = get_run_logger()
    if not CSV_PATH.exists():
        logger.error(f"CSV file not found at {CSV_PATH}")
        return
    df = pd.read_csv(CSV_PATH, dtype=str).fillna("")
    logger.info(f"Loaded {len(df)} rows from CSV")
    
    if limit is not None:
        df = df.head(limit)
        logger.info(f"Limiting to {limit} rows for testing")
        
    for _, row in df.iterrows():
        process_company(row)

if __name__ == "__main__":
    scraper_flow()
