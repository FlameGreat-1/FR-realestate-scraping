"""Static (HTTPX-driven) listing extractor.

Responsibilities:
    * Delegate candidate-URL discovery to `CandidateDiscovery`.
    * Fetch each candidate concurrently (bounded), parse, and emit a
      `Listing` whenever a publishable record is produced.
    * Apply per-domain dedup of canonical URLs to avoid double work.
    * Enforce a per-listing wall-clock cap so a single slow URL
      cannot dominate the per-domain budget.

Discovery (sitemap + homepage harvest + bounded hub BFS) lives in the
shared `extractors.discovery` module so the dynamic path can reuse
it. The static path passes the homepage HTML cached during
fingerprinting so we never re-fetch it.
"""
from __future__ import annotations

import asyncio
import logging

from concurrent.futures import ThreadPoolExecutor
from typing import Optional

from ..config import Settings
from ..fingerprint import Fingerprint
from ..http_client import HttpFetcher
from ..models import DomainJob, Listing
from ..utils.url import dedup_key
from .discovery import CandidateDiscovery
from .dynamic_extractor import consume_orphan_exception
from .pipeline_extract import parse_and_build_listing

log = logging.getLogger(__name__)


class StaticExtractor:
    """Pulls listings using only async HTTP requests."""

    def __init__(
        self,
        settings: Settings,
        fetcher: HttpFetcher,
        *,
        parse_pool: Optional[ThreadPoolExecutor] = None,
    ) -> None:
        self._settings = settings
        self._fetcher = fetcher
        self._discovery = CandidateDiscovery(settings, fetcher)
        self._listing_sem = asyncio.Semaphore(settings.listing_concurrency)
        # Explicit parse pool: never the loop's default executor.
        # See pipeline.Pipeline.run for the full rationale.
        self._parse_pool = parse_pool

    async def gather_listings(
        self,
        job: DomainJob,
        fingerprint: Fingerprint,
    ) -> list[Listing]:
        candidates = await self._discovery.discover(
            job,
            fingerprint.families,
            homepage_html=fingerprint.homepage_html or None,
            base_url=fingerprint.final_url or job.url,
        )
        if not candidates:
            log.info("static: no candidate listings for %s", job.domain)
            return []
        log.info(
            "static: %s -> %d candidate listing URLs",
            job.domain, len(candidates),
        )

        # Hard wall-clock cap on the entire candidate gather. Mirrors
        # the dynamic extractor's outer cap. Without this the static
        # path can run uncapped on slow Cloudflare-fronted hosts whose
        # httpx fetches all hit fetch_timeout, generating enough loop
        # traffic to starve the pipeline-level wait_for. The ratio is
        # configurable so operators can rebalance against the dynamic
        # ratio when tuning a large corpus; default 0.55 leaves room
        # for the hybrid fallback to engage on zero-listing static.
        gather_budget = (
            self._settings.domain_time_budget
            * self._settings.static_gather_budget_ratio
        )

        results: list[Listing] = []
        seen_keys: set[str] = set()
        listing_budget = self._settings.listing_time_budget

        loop = asyncio.get_running_loop()

        async def _fetch_and_parse(url: str) -> Listing | None:
            """Network + CPU-bound work, no semaphore here.

            The caller holds `_listing_sem` for the full body. We do
            NOT acquire it inside this coroutine because nesting
            `asyncio.wait_for` around `async with semaphore` is a
            documented asyncio anti-pattern (CPython gh-93999): a
            timeout race can leak the slot, draining the semaphore
            and deadlocking every subsequent task on this domain.
            """
            outcome = await self._fetcher.fetch(url)
            if not outcome.ok or not outcome.is_html_like or not outcome.text:
                return None
            return await loop.run_in_executor(
                self._parse_pool,
                parse_and_build_listing,
                outcome.final_url or url,
                outcome.text,
                job,
            )

        async def _bounded_process(url: str) -> Listing | None:
            """Per-listing wall-clock guard.

            Semaphore acquire is OUTSIDE wait_for. wait_for only
            wraps the fetch + parse, so a timeout cancels the work
            but the semaphore __aexit__ always runs on a live task
            and the slot is released cleanly.
            """
            async with self._listing_sem:
                try:
                    return await asyncio.wait_for(
                        _fetch_and_parse(url), timeout=listing_budget,
                    )
                except asyncio.TimeoutError:
                    log.debug(
                        "static: listing %s exceeded %.1fs budget, dropping",
                        url, listing_budget,
                    )
                    return None
                except Exception as exc:  # noqa: BLE001
                    log.debug("static: listing %s failed: %s", url, exc)
                    return None

        tasks = [
            asyncio.create_task(_bounded_process(url)) for url in candidates
        ]

        async def _drain() -> None:
            for coro in asyncio.as_completed(tasks):
                try:
                    listing = await coro
                except Exception as exc:  # noqa: BLE001
                    log.debug("static: task crashed: %s", exc)
                    continue
                if listing is None:
                    continue
                key = (
                    f"{listing.source_domain}|{listing.reference_id}".lower()
                    if listing.reference_id
                    else dedup_key(listing.source_url)
                )
                if key in seen_keys:
                    continue
                seen_keys.add(key)
                results.append(listing)

        try:
            try:
                await asyncio.wait_for(_drain(), timeout=gather_budget)
            except asyncio.TimeoutError:
                log.info(
                    "static: %s gather budget exhausted after %.1fs, "
                    "keeping %d listings",
                    job.domain, gather_budget, len(results),
                )
        finally:
            for task in tasks:
                if not task.done():
                    task.cancel()
            try:
                await asyncio.wait_for(
                    asyncio.gather(*tasks, return_exceptions=True),
                    timeout=5.0,
                )
            except asyncio.TimeoutError:
                pending = [t for t in tasks if not t.done()]
                for task in pending:
                    task.add_done_callback(consume_orphan_exception)
                log.debug(
                    "static: cleanup gather timed out for %s, "
                    "abandoning %d tasks",
                    job.domain, len(pending),
                )
        return results
