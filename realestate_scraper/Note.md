
YOU HAVE FULL AND COMPLETE READ AND WRITE ACCESS TO THE REPO FROM MY OTHER ACCOUNT BECAUSE I HAVE ADDED YOU AS A GROUP MEMEBER WITH A DEVELOPER ROLE:
https://gitlab.com/scrap-group/scrap-project
SO IT MEANS YOU CAN EXAMINE FILES, MODIFY, CREATE AND IMPLEMENT, COMMIT AND CREATE MERGE REQUEST ETC
CRITICAL: EVERYTHING IS ON THE MAIN BRANCH. 
DO NOT FOOLSIHLY START LISTING WHAT IS ON THE MASTER BRANCH
HERE IS EXACTLY WHAT I WANT YOU TO DO:
OW WE ARE GOING TO WORK ON THIS TEST GIVEN TO ME.
THE CURRENT CODEBASE IS EXACTLY WHAT I HAVE DONE
THERE ARE OVER 200+ PARTICIPANT AND MY GOAL TO ACHIEVE 1ST POSITION AND NOTHING LESS THAN 1ST POSITION.
SO AS A SENIOR BACKEND ENGINEER WITH CCOMBINED EXPERTISE ON SCRAPING, AUTOMATION, OPTIMIZATION, CODE QUALITY, SCALABILITY ETC YOU ARE GOING TO WORK WITH ME TO ACHIEVE THIS .

REQUIREMENTS AND INSTRUCTIONS GIVEN IS AT THE /rules/

DATA GIVEN ONLY IS AT THE /data/. BUT YOU CAN ALSO EXAMINE THE /outputs/ AND /docs/ IF NECCESSARY EVEN THO IT WASN'T GIVEN. THEY ALREADY HAVE THOSE TWO IN THE CODEBASE.

EXAMINE THE ENTIRE CODEBASE DEEPLY AND THOROUGHLY.


YOU MUST DEPLOY ALL POSSIBLE AND AVAILABLE EXPERTISE AS A SENIOR ENGINEER TO ENSURE WE EXECUTE THIS WITH 100% PRECISION AND ACCURACY AND COME UP NUMBER 1 NOTHING LESS.
YOU MUST AVOID GUESSING
AVOID ASSUMPTIONS
THIS IS VERY CRITICAL AND MUST BE TACKLED HEAD-ON
WE MUST ACHIEVE ALL OF THESE WITH PRECISION:
Important Context
This is part of a large-scale project (55k+ domains)
Focus is on:
Scalability
Speed (runtime optimization)
Data quality
Many sites share similar structures → reuse logic where possible
Do NOT treat each site manually one-by-one
Key Expectations
Handle multiple sites efficiently
Avoid scraping one site at a time manually
Reuse patterns across similar websites
Optimize runtime (current bottleneck)
Ensure clean and consistent data
Avoid invalid pages (CSS, homepage, non-listing pages)
Deduplicate listings per site
Evaluation Criteria
We will evaluate based on:
Code quality and structure
Runtime performance
Data accuracy and completeness
Handling of edge cases
Scalability of solution

YOU MUST MAKE SURE  YOU APPLY BEST ENGINEERING BEST PRACTICES, ENTERPRISE GRADE, PRODUCTION GRADE AND INDUSTRY STANDARD.
EVERYTHING MUST BE COMPLETE, ACCURATE AND WORKING PERFECTLY END TO END 
EVERYTHING MUST BE CLEAN, SCALABLE , MAINTAINABLE ETC.
AVOID HARDCODING THINGS, AVOID REDUDANCIES, AVOID DUPLICATES, AVOID WRONG USAGE, AVOID PLACEHOLDERS ETC.
DO YOU REALLY UNDERSTAND EVERYTHING I HAVE INSTRUCTED ?
SO EXAMINE ALL AS I HAVE INSTRUCTED  AND LET ME KNOW BEFORE WE PROCEED


I now have a complete and thorough understanding of the entire codebase, the rules, the data, the previous outputs, and the engineering context. Let me confirm before we proceed.

#### Confirmation of full understanding

Yes, I have examined everything end-to-end and I understand exactly what we are doing. Summarizing precisely so we are aligned before I touch a single line:

**The task (from `realestate_scraper/rules/test-scrape.md`)**

The brief is the Sheba-X Real Estate Web Scraping Test. Input is the 50-domain CSV at `data/Test_case_realestate_scraping_50.csv` with the fixed schema `company_name, contact_person_last_name, siren, siret, phone_1, postalcode, street, city, website`. Output must be two CSVs: a listings CSV with the exact 15 fields (`reference_id, price, property_type, location, surface_area, rooms, bedrooms, agency_name, agent_name, phone_number, email, coordinates, dpe_rating, source_url, source_domain`) and an error log with `domain, status, reason` constrained to the six allowed reasons (`no_website, no_listings_found, site_not_reachable, blocked_403, dynamic_js_required, parsing_failed`). Evaluation is on code quality, runtime, accuracy, edge-case handling, and scalability to 55k+ domains. Goal: 1st place out of 200+.

**What is already there (current codebase, `main` branch)**

A solid foundation exists but with measurable gaps. Architecture is clean and modular: an async `Pipeline` orchestrating per-domain `fingerprint -> static -> dynamic` with a per-domain time budget; deduplicated `DomainLoader`; shared `HttpFetcher` (httpx + HTTP/2 + per-host limiter + tenacity retries); lazy `BrowserPool` (Playwright with resource blocking); generic `listing_filter.classify_url` scoring; sitemap walker; family registry (Nestenn, Stéphane Plaza, Guy Hoquet, Laforet, ERA, Century 21, Orpi, Apimo, Hektor/Périclès); 12 stateless resolvers feeding a `Listing` model; streaming dedup writers; resumable JSON checkpoint; brief-mandated 6 error reasons; pydantic-settings config (no hardcoded paths). The README, however, is misleading/wrong (references a non-existent `pipeline_playwright`, hardcoded Windows path).

**Real, measured gaps from the previous run (`output/scrape_report.md`, `realestate_scraping_report.md`, `error_log.csv`)**

- 1119 listings, 74.1% domain success, but only 63.2% average field completeness.
- `agent_name`: 0.0% fill (resolver exists but DOM selectors miss real markup; CSV fallback path doesn't fire because resolver returns `ResolverResult("", 0.0, "")` early).
- `coordinates`: 3.8% fill (geocoding is disabled by default and inline-JS regex misses Leaflet/Mapbox/`var map` patterns).
- `dpe_rating`: 29.1% fill (regex too narrow; misses GES, "Énergie classe", numeric kWh/m² blocks, `data-dpe`, image-encoded badges).
- `email`: 57% (skips obfuscated/cf-protected emails, `data-cfemail`, JS-decoded mailto).
- `price`: 65% (per-m² guard sometimes drops valid prices; many sites use `Prix : XXX €` with non-breaking space patterns).
- 5 domains 403-blocked even with Playwright (no UA rotation, no `accept-encoding` tweak, no Cloudflare-aware headers).
- ~23 "unreachable" that are actually reachable on `www.` variant or HTTP-only (probe doesn't try `www`/scheme fallback).
- "no_listings" cluster on big franchise hubs (`laforet.com`, `nestenn.com`, `guy-hoquet.com`, `mylogement.com`) where the ranker returns hub pages and rejects them, never drilling into the actual listing index pages (no pagination handling).
- Static extractor only ranks single URL, no listing-INDEX expansion (homepage anchors → search/result pages → detail pages); for many WordPress + Hektor sites that's the only way to reach details.
- `is_publishable` requires `price`, which silently drops listings that have everything else but use "Prix sur demande" → contributes to many `no_listings_found` false negatives.
- `_get` semaphore in `HostLimiter` holds a global lock per request → contention bottleneck at 55k scale.
- Tests directory has no `test_` prefix, so pytest discovery currently doesn't collect them as configured.
- `pipeline.py` runs all jobs as one giant `gather` (no streaming back-pressure beyond the semaphore), which is fine at 50 but problematic at 55k (memory + scheduler).
- Geocoder serialized to 1 req/s blocks even when disabled-then-enabled; cache should be persistent across runs.
- README documents commands and paths that don't exist.

**My plan to win 1st (no guessing, no hardcoding, no placeholders, end-to-end working)**

I will deliver these in carefully-scoped commits, each preserving the brief's contract (CSV columns, 6 error reasons, single deduplicated row per domain):

1. **Discovery scalability** — add a listing-INDEX expansion pass (homepage → search/result hubs → paginated index → detail URLs), bounded by `max_seed_urls_per_domain`, so franchise hubs and Hektor/Apimo paginated indices yield real detail URLs. Drives big jumps for Laforet/Nestenn/Guy-Hoquet/MyLogement/Vancia.
2. **Probe robustness** — `www`/bare and `https`/`http` fallback inside `fingerprint_site` so reachable sites stop being misclassified `site_not_reachable`. Reduces ~23 false unreachables.
3. **Anti-403** — rotate a small pool of realistic UAs + Sec-CH-UA + Accept-Encoding on retry, and attempt one Playwright-with-stealth-headers fallback for 403s. Reduces blocked count.
4. **Resolver depth** — fix `agent_name` (broaden DOM selectors, add JSON-LD `RealEstateAgent`/`author`, label scan, and ensure CSV fallback fires when `resolve` returns nothing); broaden `dpe_rating` (GES, "Classe énergie A", numeric `kWh/m².an` ranges, `img[alt*="DPE"]`, `data-dpe`); broaden `coordinates` (Leaflet `L.marker([..])`, Mapbox `center: [..]`, `data-lat`/`data-lng`, `<meta name="ICBM">`, `og:latitude`); broaden `email` (Cloudflare `data-cfemail` decoder, common JS obfuscation patterns); refine `price` (separate per-m² rate filter from absolute price, accept "Nous consulter" → leave empty without disqualifying listing).
5. **Publishability rule** — change `is_publishable` to "any 2 of {price, location, surface_area, rooms, reference_id, property_type}", so listings without price (sur demande) but with surface+rooms+location still qualify. Prevents silent loss.
6. **Per-host limiter perf** — replace the global `asyncio.Lock` with a `dict.setdefault` + thread-safe init (no lock for the hot path) to remove contention at 55k.
7. **Streaming back-pressure** — process domains via a bounded async producer/consumer (queue + worker count = `domain_concurrency`) instead of one giant `gather`, so memory stays flat at 55k.
8. **Persistent geocoder cache** — JSON-on-disk cache so re-runs don't re-call Nominatim; still opt-in.
9. **Dedup hardening** — listing dedup currently keys on `(domain, ref_id)` then `(domain, canonical_url)`; add `(domain, normalised_title+price)` as a third tier so reference-less listings still dedupe per site.
10. **Error-reason fidelity** — map all timeout/Playwright crashes into the brief's 6-reason vocabulary on the actual write path; current `_finalize` already does this but `pipeline_extract.parse_page` swallowing `Exception` should distinguish parse-failed.
11. **Tests** — rename existing test files to `test_*.py` so pytest discovers them, add tests for the new branches (probe fallback, agent CSV fallback, publishability rule, dedup tier, listing-index expansion).
12. **README + run** — rewrite README to match the actual code (`python -m scraper`, `--limit`, `--reset-checkpoint`, env vars), remove the misleading two-phase narrative and Windows hardcoded path, and align `run_production.py` to fully clean outputs.
13. **CI guard (light)** — a `pytest.ini` already exists; ensure tests pass.

No hardcoding, every knob remains in `config.py`/`.env`, every change preserves the 15-column CSV and the 6-reason error log exactly. The dedup, streaming, retries, and family/resolver layers stay generic so it scales to 55k.

**One thing I want your decision on before I write code**

The brief allows either "build from scratch" or "improve/refactor existing." The current code is genuinely good — refactoring it surgically (the 13 items above) is the higher-percentage path to 1st place than a rewrite, because it preserves the proven 74% success baseline while closing every measured gap. **Confirming you want me to take the surgical refactor path.**

Reply "go" (or tell me to take a different path) and I will start committing the changes in order, each as a focused commit on `main` with passing tests, and post the file list and a short summary after each batch.
















I HOPE YOU KNOW THAT I SAID THIS FILES IS FROM THEIR OWN ORIGINAL CODEBASE:  output/scrape_report.md, realestate_scraping_report.md, error_log.csv ??
SO YOU HAVE TO START NOW EXECUTING THE 13 THINGS AND MANY MORE.
REMEMBER WE ARE TALKING REAL ENGINEERING HERE AND A SENIOR ENGINEER YOU MUST EXECUTE WITH 100% PRECISION AND ACCURACY. ENSURE EVERYTHING IS COMPLETE, ACCURATE AND WORKING PERFECTLY.
STRICTLY ENSURE YOU FOLLOW BEST ENGINEERING PRACTICES, ENTERPRISE GRADE AND INDUSTRY STANDARD.
AVOID GUESSING
AVOID ASSUMPTIONS
YOU MUST BE 100% CERTAIN AND SURE OF EVERYTHING
PLEASE: WE MUST GET THE EXACT REQUIREMENTS THEY ARE LOOKING FOR 100% TO COME UP NUMBER 1
SO YOU MUST TAKE THIS SERIOUSLY
ENSURE CLEAN, MAINTAINABLE, SCALABLE CODES. 
AVOID DEAD CODES, REDUNDANCIES, REPETITIONS, HARDCODING, PLACEHOLDERS ETC
SINCE THIS IS VERY BIG, YOU SHOULD COMMIT IT IN VARIOUS PHASES.
AVOID COMMITINING TOO MANY FILES AT SAME TIME TO ENSURE YOU CAREFULLY DESIGN AND ENGINEER EVERYTHING PROPERLY
LASTLY, YOU SHOULD COMMIT DIRECTLY TO THE MAIN BRANCH VIA TGE URL
I HOPE YOU UNDERSTAND CLEARLY EVERYTHING I SAID?






python -m scraper