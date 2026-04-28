"""Centralised, environment-driven configuration.

No hardcoded paths or magic numbers anywhere else in the codebase. Every
operational knob is exposed here and can be overridden via environment
variables or a `.env` file at the project root.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT: Path = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    """Strongly-typed runtime configuration."""

    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Input / Output ---
    input_csv: str = Field(default="data/Test_case_realestate_scraping_50.csv")
    output_dir: str = Field(default="output")
    listings_csv_name: str = Field(default="listings_consolidated.csv")
    error_log_csv_name: str = Field(default="error_log.csv")
    domain_summary_csv_name: str = Field(default="domain_status_summary.csv")
    checkpoint_file_name: str = Field(default=".checkpoint.json")
    geocode_cache_name: str = Field(default=".geocode_cache.json")

    # --- Concurrency ---
    # Rebalanced after the browser-pool-bound MR.
    # Math at the observed ~50% dynamic-strategy rate on this corpus:
    #   queued borrows = domain_concurrency * 0.5 * (1 homepage + 3 esc)
    #   queue depth    = queued / browser_concurrency
    #   tail latency   = depth * ~30s render
    # 8 domains * 4 borrows / 6 contexts = 5.3 -> ~2.7 deep queue,
    # ~81s tail. Fits within domain_time_budget * 0.7 = 84s. Total
    # throughput is unchanged because the 8-domain run finishes a
    # ~50% larger fraction of starts vs the 12-domain run.
    domain_concurrency: int = Field(default=8, ge=1, le=256)
    per_host_concurrency: int = Field(default=6, ge=1, le=64)
    listing_concurrency: int = Field(default=24, ge=1, le=256)
    browser_concurrency: int = Field(default=6, ge=1, le=32)

    # --- Timeouts ---
    http_probe_timeout: float = Field(default=6.0, gt=0)
    http_fetch_timeout: float = Field(default=10.0, gt=0)
    # 120s covers: fingerprint (~3s) + discovery (~8s) + detail phase.
    # Detail phase worst case: 120 URLs / 24 concurrent * 10s = 50s.
    # Total worst case: ~61s, leaving 59s headroom for slow hosts and
    # Playwright escalation. At 55k+ scale: (55000 / 12) * 120s = 153h
    # worst case, but checkpoint resume makes this a non-issue.
    domain_time_budget: float = Field(default=120.0, gt=0)
    browser_nav_timeout: float = Field(default=15.0, gt=0)

    # --- Limits ---
    # 80 candidates balances coverage and speed: 80 / 6 per-host * 10s
    # fetch = 133s worst case, but real-world latency is lower since
    # most fetches complete in 1-2s. The ranking in
    # discovery.rank_and_limit puts highest-scoring URLs first, so 80
    # captures the bulk of legitimate listings without the tail of
    # diminishing-return URLs that 120 included.
    max_listing_urls_per_domain: int = Field(default=80, ge=1)
    max_seed_urls_per_domain: int = Field(default=80, ge=1)
    max_sitemap_depth: int = Field(default=2, ge=1, le=5)
    seed_expansion_depth: int = Field(default=2, ge=0, le=4)
    max_hub_pages_per_domain: int = Field(default=12, ge=0, le=128)
    # Hard wall-clock cap on processing a single listing URL (httpx
    # + optional Playwright fallback + parse + resolver pipeline).
    # A URL that does not yield within this budget is dropped; the
    # other candidates continue. 10s is aligned with the fetch timeout
    # so a URL that times out on fetch is dropped immediately rather
    # than consuming additional budget on parse attempts.
    listing_time_budget: float = Field(default=10.0, gt=0)

    # --- Behaviour ---
    verify_tls: bool = Field(default=False)
    follow_redirects: bool = Field(default=True)
    user_agent: str = Field(
        default=(
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        )
    )
    accept_language: str = Field(default="fr-FR,fr;q=0.9,en;q=0.7")
    enable_playwright: bool = Field(default=True)
    # Geocoding fills `coordinates` for listings whose pages did not
    # ship lat/lng in any in-page form. The CoordinatesResolver still
    # extracts coordinates from json-ld / meta / data-attrs / leaflet /
    # mapbox / map iframes - geocoding only handles the residual case
    # of pages with no embedded coordinates at all.
    #
    # Default OFF because the post-pass runs serially through
    # Nominatim's 1-req/s policy and at 55k+ scale dominates total
    # runtime. Operators who need geocoded output flip this on
    # explicitly via the ENABLE_GEOCODING environment variable.
    enable_geocoding: bool = Field(default=False)
    geocoder_user_agent: str = Field(default="realestate_scraper/1.0")
    geocoder_timeout: float = Field(default=3.0, gt=0)
    # Hard wall-clock cap on the geocoder POST-PASS (after every
    # domain has finished scraping). When exhausted, listings whose
    # coordinates were not yet resolved stay empty - partial coverage
    # is preferable to an unbounded run. 60 s lets ~60 unique cold
    # lookups complete on a fully cold cache, while leaving cache-
    # warm runs effectively free.
    geocoder_post_pass_budget: float = Field(default=60.0, ge=0)
    # Deprecated: kept on the model so old .env files do not crash on
    # load. The geocoder no longer runs on the per-domain hot path,
    # so this setting has no effect. Will be removed in a future
    # round.
    geocoder_enrichment_budget: float = Field(default=0.0, ge=0)

    # --- Retries ---
    # 1 retry covers transient socket / TLS errors. Persistent
    # failures are handled by the dynamic-extractor escalation path
    # rather than re-issuing the same failing request multiple times.
    http_max_retries: int = Field(default=1, ge=0, le=10)
    http_retry_backoff: float = Field(default=0.5, ge=0)

    # --- Logging ---
    log_level: str = Field(default="INFO")
    log_json: bool = Field(default=False)

    # --- Resume ---
    resume: bool = Field(default=True)

    # --- Derived helpers (never overridden directly) ---
    @property
    def project_root(self) -> Path:
        return PROJECT_ROOT

    @property
    def input_csv_path(self) -> Path:
        path = Path(self.input_csv)
        return path if path.is_absolute() else PROJECT_ROOT / path

    @property
    def output_dir_path(self) -> Path:
        path = Path(self.output_dir)
        return path if path.is_absolute() else PROJECT_ROOT / path

    @property
    def listings_csv_path(self) -> Path:
        return self.output_dir_path / self.listings_csv_name

    @property
    def error_log_csv_path(self) -> Path:
        return self.output_dir_path / self.error_log_csv_name

    @property
    def domain_summary_csv_path(self) -> Path:
        return self.output_dir_path / self.domain_summary_csv_name

    @property
    def checkpoint_path(self) -> Path:
        return self.output_dir_path / self.checkpoint_file_name

    @property
    def geocode_cache_path(self) -> Path:
        return self.output_dir_path / self.geocode_cache_name

    @property
    def default_headers(self) -> dict[str, str]:
        return {
            "User-Agent": self.user_agent,
            "Accept": (
                "text/html,application/xhtml+xml,application/xml;"
                "q=0.9,*/*;q=0.8"
            ),
            "Accept-Language": self.accept_language,
        }


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a process-wide cached Settings instance."""
    return Settings()
