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

from concurrent.futures import ThreadPoolExecutor

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

# Hard cap on the post-domain finalize step (CSV writes + checkpoint
# flush). The same value the static and dynamic extractors use for
# their cleanup gathers; sharing it keeps the wall-clock contract
# (`domain_time_budget + _FINALIZE_CAP` worst case) consistent across
# modules.
_FINALIZE_CAP: float = 5.0


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

        from concurrent.futures import ProcessPoolExecutor
        # Dedicated process pool for CPU-bound parse work (selectolax
        # + regex + resolver pipeline). A ThreadPoolExecutor would share
        # the main process's GIL, meaning pathological HTML parsed in C
        # would completely freeze the asyncio event loop for minutes.
        # By using a ProcessPoolExecutor, the heavy C-extensions run in
        # isolated processes, ensuring the orchestrator's event loop
        # timers (wait_for) always fire perfectly on time.
        parse_pool = ProcessPoolExecutor(
            max_workers=self._settings.listing_concurrency,
        )

        async with open_fetcher(self._settings) as fetcher:
            browser_pool = BrowserPool(self._settings)
            await browser_pool.start()
            try:
                static = StaticExtractor(
                    self._settings, fetcher, parse_pool=parse_pool,
                )
                dynamic = DynamicExtractor(
                    self._settings, browser_pool, fetcher,
                    parse_pool=parse_pool,
                )

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
                parse_pool.shutdown(wait=False)

    async def _process_one(
        self,
        job: DomainJob,
        static: StaticExtractor,
        dynamic: DynamicExtractor,
        fetcher,
    ) -> None:
        start = time.perf_counter()
        budget = self._settings.domain_time_budget
        deadline = start + budget
        # The fingerprint is captured up front so the exception arm
        # can distinguish a reachable-host crash from a genuinely
        # unreachable host. Reachable-host crashes map to
        # PARSING_FAILED rather than the network markers in
        # classify_exception.
        fingerprint: Optional[Fingerprint] = None
        try:
            fingerprint = await asyncio.wait_for(
                fingerprint_site(job.url, fetcher),
                timeout=max(0.1, deadline - time.perf_counter()),
            )
            result = await asyncio.wait_for(
                self._scrape_domain(
                    job, static, dynamic, fetcher, fingerprint, deadline,
                ),
                timeout=max(0.1, deadline - time.perf_counter()),
            )
        except asyncio.TimeoutError:
            elapsed = time.perf_counter() - start
            log.warning(
                "domain %s timed out after %.1fs", job.domain, elapsed,
            )
            # Timeout never means unreachable on its own. Differentiate
            # using the fingerprint: a host that never answered the
            # probe is unreachable; a host that did is just slow.
            if fingerprint is None or not fingerprint.reachable:
                reason = ErrorReason.SITE_NOT_REACHABLE
            else:
                reason = ErrorReason.NO_LISTINGS_FOUND
            result = DomainResult(
                domain=job.domain,
                status=DomainStatus.FAILED,
                reason=reason,
                strategy=Strategy.NONE,
            )
        except Exception as exc:  # noqa: BLE001
            log.warning("domain %s crashed: %s", job.domain, exc)
            # Reachable-host crashes are PARSING_FAILED, never
            # SITE_NOT_REACHABLE: the host already answered the probe.
            if fingerprint is not None and fingerprint.reachable:
                reason = ErrorReason.PARSING_FAILED
            else:
                reason = classify_exception(exc)
            result = DomainResult(
                domain=job.domain,
                status=DomainStatus.FAILED,
                reason=reason,
                strategy=Strategy.NONE,
            )
        # Wall-clock contract: the inner extractors cap their gather
        # phases via configurable ratios; finalize is the only
        # remaining work that could push past the budget on a slow
        # disk. Bound it explicitly so an overrun cannot happen.
        # `_FINALIZE_CAP` is the same conservative value the
        # extractors use for their cleanup gathers, so the constants
        # do not diverge across modules.
        result.duration_seconds = time.perf_counter() - start
        try:
            await asyncio.wait_for(
                self._finalize(result), timeout=_FINALIZE_CAP,
            )
        except asyncio.TimeoutError:
            log.warning(
                "domain %s finalize exceeded %.1fs cap, result not flushed",
                job.domain, _FINALIZE_CAP,
            )

    async def _scrape_domain(
        self,
        job: DomainJob,
        static: StaticExtractor,
        dynamic: DynamicExtractor,
        fetcher,
        fingerprint: Fingerprint,
        deadline: float,
    ) -> DomainResult:
        # Give the inner extractors a slightly tighter deadline so they
        # finish gracefully before the outer wait_for throws a hard kill.
        inner_deadline = deadline - 2.0
        budget = self._settings.domain_time_budget
        # Reserve 20% of the domain budget as a minimum threshold for
        # starting a fallback extraction strategy. If the primary
        # strategy consumed most of the budget, attempting a second
        # strategy will almost certainly time out and waste resources.
        min_fallback_budget = budget * 0.20

        log.info("start %s", job.domain)

        def _remaining() -> float:
            return max(0.0, inner_deadline - time.perf_counter())

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

        # Strategy: static-first for all reachable sites.
        #
        # Static extraction uses only httpx (no browser pool slots,
        # no Playwright overhead) and completes in 20-40s. Dynamic
        # extraction renders the homepage in Playwright (~15-30s per
        # browser slot) and then renders each detail page, consuming
        # 60-90s of the 120s domain budget. Running dynamic first
        # for DYNAMIC-fingerprinted sites left no budget for the
        # static fallback, causing cascading timeouts.
        #
        # The only exception is BLOCKED_403: httpx gets rejected by
        # WAF interstitials, so static cannot discover candidates.
        # Those sites go dynamic-first where Playwright can solve
        # the challenge page.

        if fingerprint.failure_reason == ErrorReason.BLOCKED_403:
            # WAF-blocked: dynamic is the only viable path.
            listings = await self._try_dynamic(
                job, dynamic, fingerprint, inner_deadline,
            )
            used = Strategy.DYNAMIC if listings else Strategy.NONE
        else:
            # Static-first: cheap, fast, no browser contention.
            listings = await static.gather_listings(
                job, fingerprint, inner_deadline,
            )
            used = Strategy.STATIC
            if not listings and _remaining() > min_fallback_budget:
                # Static yielded nothing — try dynamic with the
                # remaining budget. ~80s typically remains, enough
                # for a full dynamic gather cycle.
                listings = await self._try_dynamic(
                    job, dynamic, fingerprint, inner_deadline,
                )
                if listings:
                    used = Strategy.HYBRID

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
        deadline: float,
    ) -> list[Listing]:
        if not dynamic.is_available:
            return []
        try:
            return await dynamic.gather_listings(job, fingerprint, deadline)
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

    # Suppress harmless Playwright future cancellation warnings that
    # occur when a domain's browser tab is aggressively severed.
    loop = asyncio.get_running_loop()
    def _suppress_playwright_cancellations(loop, context):
        msg = str(context.get("exception", context.get("message", "")))
        if "TargetClosedError" in msg or "net::ERR_ABORTED" in msg:
            return
        loop.default_exception_handler(context)
    loop.set_exception_handler(_suppress_playwright_cancellations)

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

    # Human-readable summary derived from the three output CSVs.
    # Purely informational; failures are logged and swallowed so
    # they cannot mask a successful run.
    from .report import generate_report
    generate_report(settings)

    # Allow asyncio transports (specifically Playwright's internal
    # subprocess pipe) to cleanly flush their closure events before
    # asyncio.run() destroys the event loop. Prevents the noisy
    # "Exception ignored in ... RuntimeError: Event loop is closed"
    # warning during Python interpreter teardown.
    await asyncio.sleep(0.25)
