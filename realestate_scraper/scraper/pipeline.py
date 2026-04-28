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
"""
from __future__ import annotations

import asyncio
import logging
import time
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
            log.warning("domain %s timed out", job.domain)
            result = DomainResult(
                domain=job.domain,
                status=DomainStatus.FAILED,
                reason=ErrorReason.SITE_NOT_REACHABLE,
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

        if fingerprint.suggested_strategy == Strategy.STATIC:
            listings = await static.gather_listings(job, fingerprint)
            used = Strategy.STATIC
            if not listings:
                # Static run yielded nothing - try dynamic if available.
                listings = await self._try_dynamic(job, dynamic, fingerprint)
                if listings:
                    used = Strategy.HYBRID
        else:
            listings = await self._try_dynamic(job, dynamic, fingerprint)
            used = Strategy.DYNAMIC if listings else Strategy.NONE
            if not listings and fingerprint.failure_reason != ErrorReason.BLOCKED_403:
                # Last-ditch static attempt for misclassified sites.
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

        await self._enrich(listings)
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

    async def _enrich(self, listings: list[Listing]) -> None:
        if not self._geocoder.enabled:
            return
        for listing in listings:
            if listing.coordinates or not listing.location:
                continue
            value = await self._geocoder.lookup(listing.location)
            if value:
                listing.coordinates = value

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
