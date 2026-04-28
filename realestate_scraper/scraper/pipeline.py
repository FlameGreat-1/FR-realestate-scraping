"""End-to-end orchestrator.

Responsibilities:
    * Load and dedupe input domains via `DomainLoader`.
    * Initialise output writers and the resume checkpoint.
    * Open a single shared `HttpFetcher` and (optionally) `BrowserPool`.
    * For each domain, fingerprint -> static -> dynamic fallback,
      enforcing a per-domain time budget.
    * Translate every failure mode into one of the six brief-mandated
      error reason codes.
    * Stream listings, errors, and the per-domain summary as we go.
    * After every domain completes, run a SINGLE geocoder post-pass
      to fill missing coordinates - never on the per-domain hot path,
      so a globally-rate-limited service cannot block any domain.
"""
from __future__ import annotations

import asyncio
import csv
import logging
import os
import tempfile
import time
from pathlib import Path
from typing import Optional

from .browser_pool import BrowserPool
from .checkpoint import Checkpoint
from .config import Settings, get_settings
from .domain_loader import DomainLoader, LoaderError
from .error_codes import ErrorReason, classify_exception
from .extractors.dynamic_extractor import DynamicExtractor
from .extractors.static_extractor import StaticExtractor
from .fingerprint import Fingerprint, fingerprint_site
from .http_client import open_fetcher
from .logging_setup import configure_logging
from .models import (
    DomainJob,
    DomainResult,
    DomainStatus,
    LISTING_FIELDS,
    Listing,
    Strategy,
)
from .storage import OutputBundle, build_output_bundle
from .utils.geocoder import AsyncGeocoder

log = logging.getLogger(__name__)


class Pipeline:
    """Concurrent per-domain orchestrator."""

    def __init__(
        self,
        settings: Settings,
        bundle: OutputBundle,
        checkpoint: Checkpoint,
    ) -> None:
        self._settings = settings
        self._bundle = bundle
        self._checkpoint = checkpoint
        self._geocoder = AsyncGeocoder(
            enabled=settings.enable_geocoding,
            user_agent=settings.geocoder_user_agent,
            timeout=settings.geocoder_timeout,
            cache_path=settings.geocode_cache_path,
        )

    async def run(self, jobs: list[DomainJob]) -> None:
        """Drive a fixed-size worker pool over `jobs`.

        Memory and scheduler cost are bounded by `domain_concurrency`,
        not by the input size. This is what makes the pipeline scale
        from 50 domains to 55k+ without changing topology.
        """
        if not jobs:
            log.warning("no domains to process")
            return

        worker_count = max(1, min(self._settings.domain_concurrency, len(jobs)))
        # Bound the queue at 2x worker count so the producer applies
        # back-pressure if the workers fall behind, instead of buffering
        # the entire job list in memory.
        queue: asyncio.Queue = asyncio.Queue(maxsize=worker_count * 2)

        async with open_fetcher(self._settings) as fetcher:
            browser_pool = BrowserPool(self._settings)
            # Pre-warm the Chromium browser process ONCE before any
            # worker spawns. The lazy-on-first-borrow shape charged
            # the launch cost (~1-3 s) to whichever domain happened
            # to acquire the browser pool first - that is wrong
            # engineering at any scale. Failure here is non-fatal:
            # `is_available` returns False and the dynamic path
            # gracefully degrades to the static-only fallback that
            # the rest of the pipeline already handles.
            await browser_pool.start()
            try:
                static = StaticExtractor(self._settings, fetcher)
                dynamic = DynamicExtractor(self._settings, browser_pool, fetcher)

                async def _producer() -> None:
                    for job in jobs:
                        await queue.put(job)
                    # One sentinel per worker for graceful shutdown.
                    for _ in range(worker_count):
                        await queue.put(None)

                async def _worker() -> None:
                    while True:
                        job = await queue.get()
                        try:
                            if job is None:
                                return
                            await self._process_one(
                                job, static, dynamic, fetcher,
                            )
                        finally:
                            queue.task_done()

                await asyncio.gather(
                    _producer(),
                    *[_worker() for _ in range(worker_count)],
                    return_exceptions=False,
                )
            finally:
                await browser_pool.close()

    async def _process_one(
        self,
        job: DomainJob,
        static: StaticExtractor,
        dynamic: DynamicExtractor,
        fetcher,
    ) -> None:
        start = time.perf_counter()
        try:
            result = await asyncio.wait_for(
                self._scrape_domain(job, static, dynamic, fetcher),
                timeout=self._settings.domain_time_budget,
            )
        except asyncio.TimeoutError:
            elapsed = time.perf_counter() - start
            log.warning(
                "domain %s timed out after %.1fs", job.domain, elapsed,
            )
            # A timeout does NOT mean the site is unreachable. The site
            # may have responded fine during fingerprinting but the
            # detail-fetching phase ran out of budget. Classify as
            # NO_LISTINGS_FOUND so the error log accurately reflects
            # that the site was reachable but we couldn't extract in
            # time. Genuinely unreachable sites are caught earlier by
            # the fingerprint probe and never reach the timeout path.
            result = DomainResult(
                domain=job.domain,
                status=DomainStatus.FAILED,
                reason=ErrorReason.NO_LISTINGS_FOUND,
                strategy=Strategy.NONE,
            )
        except Exception as exc:  # noqa: BLE001
            log.warning("domain %s crashed: %s", job.domain, exc)
            result = DomainResult(
                domain=job.domain,
                status=DomainStatus.FAILED,
                reason=classify_exception(exc),
                strategy=Strategy.NONE,
            )
        result.duration_seconds = time.perf_counter() - start
        await self._finalize(result)

    async def _scrape_domain(
        self,
        job: DomainJob,
        static: StaticExtractor,
        dynamic: DynamicExtractor,
        fetcher,
    ) -> DomainResult:
        domain_start = time.perf_counter()
        budget = self._settings.domain_time_budget
        # Reserve 20% of the domain budget as a minimum threshold for
        # starting a fallback extraction strategy. If the primary
        # strategy consumed most of the budget, attempting a second
        # strategy will almost certainly time out and waste resources.
        min_fallback_budget = budget * 0.20

        log.info("start %s", job.domain)
        fingerprint = await fingerprint_site(job.url, fetcher)

        if (
            fingerprint.failure_reason == ErrorReason.SITE_NOT_REACHABLE
            and fingerprint.suggested_strategy == Strategy.NONE
        ):
            return DomainResult(
                domain=job.domain,
                status=DomainStatus.FAILED,
                reason=ErrorReason.SITE_NOT_REACHABLE,
                strategy=Strategy.NONE,
            )

        listings: list[Listing] = []
        used = Strategy.NONE

        def _remaining() -> float:
            return budget - (time.perf_counter() - domain_start)

        if fingerprint.suggested_strategy == Strategy.STATIC:
            listings = await static.gather_listings(job, fingerprint)
            used = Strategy.STATIC
            if not listings and _remaining() > min_fallback_budget:
                # Static run yielded nothing and we have enough budget
                # left for a meaningful dynamic attempt.
                listings = await self._try_dynamic(job, dynamic, fingerprint)
                if listings:
                    used = Strategy.HYBRID
        else:
            listings = await self._try_dynamic(job, dynamic, fingerprint)
            used = Strategy.DYNAMIC if listings else Strategy.NONE
            if (
                not listings
                and fingerprint.failure_reason != ErrorReason.BLOCKED_403
                and _remaining() > min_fallback_budget
            ):
                # Last-ditch static attempt for misclassified sites,
                # only if we have enough budget remaining.
                static_listings = await static.gather_listings(job, fingerprint)
                if static_listings:
                    listings = static_listings
                    used = Strategy.STATIC

        if not listings:
            reason = self._reason_for_empty(fingerprint, dynamic.is_available)
            return DomainResult(
                domain=job.domain,
                status=DomainStatus.FAILED,
                reason=reason,
                strategy=used,
            )

        # Cache-only enrichment: synchronous, lock-free, zero network.
        # Cold geocoder lookups are deferred to the post-run pass.
        self._enrich_from_cache(listings)
        accepted = await self._bundle.listings.write_many(listings)
        return DomainResult(
            domain=job.domain,
            status=DomainStatus.SUCCESS,
            listing_count=accepted,
            strategy=used,
        )

    async def _try_dynamic(
        self,
        job: DomainJob,
        dynamic: DynamicExtractor,
        fingerprint: Fingerprint,
    ) -> list[Listing]:
        if not dynamic.is_available:
            return []
        try:
            return await dynamic.gather_listings(job, fingerprint)
        except Exception as exc:  # noqa: BLE001
            log.debug("dynamic extractor crashed for %s: %s", job.domain, exc)
            return []

    @staticmethod
    def _reason_for_empty(
        fingerprint: Fingerprint, dynamic_available: bool
    ) -> ErrorReason:
        if fingerprint.failure_reason == ErrorReason.BLOCKED_403:
            return ErrorReason.BLOCKED_403
        if fingerprint.suggested_strategy == Strategy.DYNAMIC and not dynamic_available:
            return ErrorReason.DYNAMIC_JS_REQUIRED
        if fingerprint.failure_reason == ErrorReason.SITE_NOT_REACHABLE:
            return ErrorReason.SITE_NOT_REACHABLE
        return ErrorReason.NO_LISTINGS_FOUND

    def _enrich_from_cache(self, listings: list[Listing]) -> None:
        """Synchronous cache-only fill of missing coordinates.

        Pure in-memory work: no lock acquisition, no network call.
        Listings whose `location` was already resolved in a prior run
        (or earlier in this run) get coordinates instantly. Listings
        whose location has never been seen are left empty here and
        picked up by the post-run geocoder pass.

        Removed from `_scrape_domain`'s critical path because the
        async `lookup()` path takes a process-global lock and sleeps
        1 s per cold call - serialised across all concurrent domains.
        At 12-domain concurrency that lock queue routinely exceeds
        the per-domain time budget. The post-run pass solves it.
        """
        if not self._geocoder.enabled or not listings:
            return
        for listing in listings:
            if listing.coordinates or not listing.location:
                continue
            cached = self._geocoder.lookup_cached(listing.location)
            if cached:
                listing.coordinates = cached

    async def run_geocode_post_pass(self) -> None:
        """Single-coroutine post-pass that fills missing coordinates.

        Reads the listings CSV streaming, deduplicates the missing
        locations globally, resolves them serially through the
        geocoder (which already enforces the 1-req/s policy via its
        internal lock), then atomically rewrites the listings CSV
        with the resolved values. Hard wall-clock budget caps the
        total time so a fully cold cache cannot stall indefinitely.

        This is the ONLY place network-bound geocoding runs. Per-
        domain workers never touch the geocoder lock.
        """
        if not self._geocoder.enabled:
            return
        budget = self._settings.geocoder_post_pass_budget
        if budget <= 0:
            log.info("geocode post-pass skipped: budget is zero")
            return

        path = self._settings.listings_csv_path
        if not path.exists() or path.stat().st_size == 0:
            return

        # Pass 1: scan CSV streaming, collect unique missing locations.
        unique_missing: dict[str, str] = {}
        try:
            with path.open("r", newline="", encoding="utf-8") as fh:
                reader = csv.DictReader(fh)
                for row in reader:
                    coords = (row.get("coordinates") or "").strip()
                    location = (row.get("location") or "").strip()
                    if coords or not location:
                        continue
                    key = location.lower()
                    if key in unique_missing:
                        continue
                    # First serve from the persisted cache to avoid
                    # any rate-limited call we don't strictly need.
                    cached = self._geocoder.lookup_cached(location)
                    if cached:
                        unique_missing[key] = cached
                        continue
                    if self._geocoder.is_cached(location):
                        unique_missing[key] = ""
                        continue
                    unique_missing[key] = ""  # placeholder; resolved below
        except OSError as exc:
            log.warning("geocode post-pass: cannot read %s: %s", path, exc)
            return

        # Filter to the locations that genuinely need a network call.
        needs_network = [
            key for key, value in unique_missing.items()
            if not value and not self._geocoder.is_cached(key)
        ]
        if not needs_network and not any(unique_missing.values()):
            log.info("geocode post-pass: nothing to do")
            return

        # Pass 2: resolve cold lookups serially under the wall-clock
        # budget. We deliberately run them in ONE coroutine so the
        # geocoder's internal lock and the 1-req/s sleep are the only
        # serialisation - no contention from N parallel domain workers.
        loop = asyncio.get_event_loop()
        deadline = loop.time() + budget
        resolved_count = 0
        skipped_count = 0
        for key in needs_network:
            remaining = deadline - loop.time()
            if remaining <= 0:
                skipped_count = len(needs_network) - resolved_count
                log.info(
                    "geocode post-pass: budget exhausted, %d unresolved",
                    skipped_count,
                )
                break
            try:
                value = await asyncio.wait_for(
                    self._geocoder.lookup(key),
                    timeout=remaining,
                )
            except asyncio.TimeoutError:
                skipped_count = len(needs_network) - resolved_count
                log.info(
                    "geocode post-pass: per-call timeout, %d unresolved",
                    skipped_count,
                )
                break
            except Exception as exc:  # noqa: BLE001
                log.debug("geocode post-pass lookup error %r: %s", key, exc)
                continue
            if value:
                unique_missing[key] = value
                resolved_count += 1

        # Pass 3: rewrite the CSV, in place, atomically.
        applied = self._rewrite_listings_with_coords(path, unique_missing)
        log.info(
            "geocode post-pass: resolved=%d skipped=%d listings_updated=%d",
            resolved_count, skipped_count, applied,
        )

    @staticmethod
    def _rewrite_listings_with_coords(
        path: Path, location_to_coords: dict[str, str],
    ) -> int:
        """Stream-read the listings CSV and stream-write a new copy.

        Memory cost is O(1) in the listing count. Atomicity via
        tempfile + os.replace: a crash mid-rewrite leaves the
        original file intact.

        Returns the number of rows that received a new coordinate
        value.
        """
        if not location_to_coords:
            return 0
        applied = 0
        try:
            with path.open("r", newline="", encoding="utf-8") as src:
                reader = csv.DictReader(src)
                fieldnames = reader.fieldnames or list(LISTING_FIELDS)
                with tempfile.NamedTemporaryFile(
                    "w",
                    encoding="utf-8",
                    newline="",
                    dir=str(path.parent),
                    prefix=path.name + ".",
                    suffix=".tmp",
                    delete=False,
                ) as tmp:
                    writer = csv.DictWriter(
                        tmp,
                        fieldnames=fieldnames,
                        extrasaction="ignore",
                        quoting=csv.QUOTE_MINIMAL,
                    )
                    writer.writeheader()
                    for row in reader:
                        coords = (row.get("coordinates") or "").strip()
                        location = (row.get("location") or "").strip()
                        if not coords and location:
                            new_value = location_to_coords.get(location.lower())
                            if new_value:
                                row["coordinates"] = new_value
                                applied += 1
                        writer.writerow(row)
                    tmp_path = Path(tmp.name)
            os.replace(tmp_path, path)
        except OSError as exc:
            log.warning("geocode post-pass rewrite failed: %s", exc)
            return 0
        return applied

    async def _finalize(self, result: DomainResult) -> None:
        await self._bundle.summary.record(result)
        if result.reason is not None:
            await self._bundle.errors.record(
                result.domain,
                result.reason,
                status=result.status.value,
            )
        await self._checkpoint.mark(result.domain)
        log.info(
            "done %s status=%s listings=%d strategy=%s reason=%s in %.1fs",
            result.domain,
            result.status.value,
            result.listing_count,
            result.strategy.value,
            result.reason.value if result.reason else "",
            result.duration_seconds,
        )


async def run_pipeline(
    *,
    limit: Optional[int] = None,
    truncate_outputs: bool = True,
    reset_checkpoint: bool = False,
) -> None:
    """Top-level entrypoint used by `run_scraper.py` and `run_production.py`."""
    settings = get_settings()
    configure_logging(level=settings.log_level, json_format=settings.log_json)

    bundle = build_output_bundle(
        listings_path=settings.listings_csv_path,
        errors_path=settings.error_log_csv_path,
        summary_path=settings.domain_summary_csv_path,
    )
    await bundle.initialize(truncate=truncate_outputs)

    checkpoint = Checkpoint(settings.checkpoint_path, enabled=settings.resume)
    if reset_checkpoint:
        await checkpoint.reset()
    await checkpoint.load()

    try:
        loader = DomainLoader(settings.input_csv_path)
        jobs, no_website = loader.load()
    except LoaderError as exc:
        log.error("input load failed: %s", exc)
        return

    for agency in no_website:
        await bundle.errors.record(
            (agency or "unknown").lower(),
            ErrorReason.NO_WEBSITE,
            status="failed",
        )

    pending = [job for job in jobs if not checkpoint.has(job.domain)]
    log.info(
        "loaded %d jobs (%d pending after checkpoint)",
        len(jobs), len(pending),
    )
    if limit is not None:
        pending = pending[:limit]

    if not pending:
        log.info("nothing to do")
        return

    pipeline = Pipeline(settings, bundle, checkpoint)
    await pipeline.run(pending)
    log.info(
        "finished: %d listings written",
        bundle.listings.written,
    )

    # Geocoder post-pass: runs ONCE after every domain has finished,
    # on a single coroutine. Never on the per-domain hot path.
    await pipeline.run_geocode_post_pass()
