# Real Estate Listing Scraper

A robust, two-phased, asynchronous web scraper designed to extract a unified database of property listings from thousands of real estate agencies. 

## 🏗️ Architecture

The pipeline processes input CSVs through a rigorous deduplication process and automatically assigns individual domains to highly targeted extraction modules.

### Component Breakdown
* `domain_manager.py`: Deduplicates input rows directly into unique domains to prevent overlapping loads. Merges any missing default agency contact info. 
* `storage.py`: Generates the structured output (`listings_consolidated.csv` for data points and `error_log.csv` for reporting failures).
* `extractors/base.py`: Unifies the scraped variables to a structured `Listing` dataclass model format.

To ensure both maximum speed **and** maximum completion, the scraper operates in two distinct phases:

### Phase 1: High-Speed Static Execution (`run_scraper.py`)
This runs the primary `HTTPX` payload handler. It actively scans remote servers for index paths and `sitemap.xml` entries, crawling through raw backend HTML. 

* **JSON-LD Prioritization:** Intelligently extracts deeply embedded schema protocols (like `@type: Product`) for highly accurate pricing variables, rendering localized CSS patterns mostly obsolete.
* **Strict URL Execution:** Leverages strict nested regex bounding on `.path` endpoints to deliberately void false positive articles and corporate blog queries natively.
* **Outputs**: All failed sites, JavaScript-dependent sites, and Cloudflare-blocked nodes are dumped automatically to the root `error_log.csv`. 

### Phase 2: Dynamic JS Hand-off (`python -m scraper.pipeline_playwright`)
Bypassing manual curation completely, this pipeline ingests the `error_log.csv` failures and routes them dynamically through an automated, headless Chromium browser instance via **Playwright**.

* Rendered data triggers, Cloudflare intercepts, and hidden payload logic are automatically bypassed.
* **Phone Recognition Engine:** Deploys strict regex evaluation loops across the dynamically updated `document.body.innerText` to reveal hidden telephony endpoints standardizing to `+33` protocols. 

## 🚀 Execution Guide

1. Place your target file containing your target domains named `FR_realestate_scraping - FR 140 (1).csv` inside the parent directory (`c:/Users/abcre/Desktop/Project/F_realestate/`).

> [!NOTE]
> The target location paths can be customized globally by altering `CSV_PATH` inside `scraper/pipeline.py` and `scraper/pipeline_playwright.py`.

### Step 1: Run Core Extraction
Run the ultra-fast static `HTTPX` scanner across all available domains to extract up to 60% of all simple websites instantly.

```bash
python run_scraper.py
```

### Step 2: Rescue Blocked Domains
Once Phase 1 completes, initialize the secondary crawler to intercept all failed inputs. 

```bash
python -m scraper.pipeline_playwright
```

## 📊 Outputs 

Check the system generated `output/` directory for your data:
- `listings_consolidated.csv`: The clean, flat rows containing all extracted `reference_id, price, location, types, rooms, etc`.
- `error_log.csv`: The diagnostics record denoting why an individual network block failed to yield property listings. 
