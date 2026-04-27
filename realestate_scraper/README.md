# Real Estate Listing Scraper

A scalable, asynchronous Python scraper that extracts a structured
database of property listings from a CSV of real estate agency
websites. Built for the Sheba-X 50-domain test brief and engineered
to scale unchanged to the 55k+ domain target.

## Output contract

The scraper writes three CSVs into `output/` (configurable):

* `listings_consolidated.csv` - one row per deduplicated property
  listing. Exact columns required by the brief, in this order:

  ```
  reference_id, price, property_type, location, surface_area, rooms,
  bedrooms, agency_name, agent_name, phone_number, email, coordinates,
  dpe_rating, source_url, source_domain
  ```

* `error_log.csv` - one row per domain that failed or yielded no
  listings. Columns: `domain, status, reason`. The `reason` value is
  always one of the six the brief mandates:

  ```
  no_website, no_listings_found, site_not_reachable,
  blocked_403, dynamic_js_required, parsing_failed
  ```

* `domain_status_summary.csv` - per-domain timing and strategy
  diagnostics, useful for evaluation and tuning.

## Architecture

A single async pipeline drives every domain through the same
stateless flow:

```
fingerprint  ->  static extractor  -- empty? -->  dynamic extractor
   |                  |                                    |
   |                  +--- bounded BFS over hub/index pages
   |                                                       |
   +-> reachable / blocked / static / dynamic strategy ->  +--> resolvers --> Listing
```

Key building blocks:

* `pipeline.py` - bounded async worker pool (`domain_concurrency`
  workers + a back-pressured queue). Memory is `O(workers)`, not
  `O(domains)`, so the same code runs at 50 and 55k.

* `fingerprint.py` - per-domain reachability probe with `www`/bare and
  `https`/`http` variant fallback. Decides whether the domain needs
  the static path, the dynamic path, or is unreachable.

* `http_client.py` + `headers.py` - shared `httpx.AsyncClient` with
  HTTP/2, per-host concurrency limits, deterministic per-domain UA
  rotation, modern client-hint headers (`Sec-CH-UA`, `Sec-Fetch-*`),
  bounded retries, and a single 403/429 retry with a rotated UA from
  the pool.

* `extractors/static_extractor.py` - candidate URL collection from
  sitemap + homepage links + bounded BFS expansion of hub/index pages
  (depth and total-fetch budgets are config-driven). The classifier
  in `listing_filter.py` distinguishes detail / hub / reject so
  franchise hubs (Laforet, Nestenn, Guy Hoquet, Stephane Plaza, ...)
  produce real detail URLs instead of being thrown away.

* `extractors/dynamic_extractor.py` - Playwright fallback for sites
  the static path cannot read. The Playwright context reuses the
  same UA + client-hint profile the static fetcher would have used
  for the same domain, so the fingerprint is consistent.

* `extractors/pipeline_extract.py` + `resolvers/` - 12 stateless
  field resolvers feeding a `Listing` dataclass. Each resolver runs
  independently; one failing resolver never breaks the others. JSON-LD
  is consulted first, then DOM, then labelled text, then a final
  regex sweep, with confidence scores that decrease at each step.

* `storage.py` - streaming, append-only CSV writers with three-tier
  per-domain dedup: `(domain, reference_id)`, then
  `(domain, canonical_url)`, then a content fingerprint over the
  resolved descriptor fields, so reference-less and
  query-string-collapsed listings still dedupe.

* `checkpoint.py` - JSON resume checkpoint so a crashed run resumes
  from the next unprocessed domain instead of restarting.

* `utils/geocoder.py` - opt-in async geocoder backed by Nominatim,
  with a JSON-on-disk cache that survives across runs.

## Quick start

From the `realestate_scraper/` directory:

```bash
pip install -r requirements.txt
python -m playwright install chromium  # only if ENABLE_PLAYWRIGHT=true
cp .env.example .env                   # adjust as needed
python -m scraper
```

Output appears in `output/` (created automatically).

### CLI flags

| Flag                   | Meaning                                                    |
|------------------------|------------------------------------------------------------|
| `--limit N`            | Process at most `N` domains this run.                      |
| `--keep-outputs`       | Append to existing CSVs instead of truncating.             |
| `--reset-checkpoint`   | Wipe the resume checkpoint before starting.                |
| `--log-level LEVEL`    | Override `LOG_LEVEL` (`DEBUG`, `INFO`, `WARNING`, ...).    |

### Configuration

Every operational knob is in `scraper/config.py` and exposed via
environment variables / `.env`. See `.env.example` for the full list.
There are no hardcoded paths anywhere in the code; the project root
is derived from the package location.

## How the brief's six error reasons are produced

* `no_website` - the input row has no `website` column value (raised
  by `domain_loader.py` before the pipeline runs).
* `site_not_reachable` - the reachability probe found no answering
  variant within the timeout, or the domain timed out against the
  per-domain budget.
* `blocked_403` - the probe or fetcher returned 401/403/429 and the
  UA-rotation retry also failed.
* `dynamic_js_required` - the static path returned no usable HTML and
  the dynamic path is disabled (`ENABLE_PLAYWRIGHT=false`) or also
  failed to render content.
* `parsing_failed` - extraction crashed in a way that does not match
  any of the network markers.
* `no_listings_found` - everything ran to completion but produced no
  publishable listings.

The vocabulary is defined in `scraper/error_codes.py` and is the
single point of truth - any new failure path must map back to one of
these six codes.

## Testing

```bash
pytest -q
```

Unit tests cover every resolver, the URL classifier, the fingerprint
probe, the storage dedup, the domain loader, and the end-to-end
resolver pipeline. Tests use no network access.
