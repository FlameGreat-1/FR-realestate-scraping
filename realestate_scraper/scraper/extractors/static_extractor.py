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

from ..config import Settings
from ..fingerprint import Fingerprint
from ..http_client import HttpFetcher
from ..models import DomainJob, Listing
from ..utils.url import dedup_key
from .discovery import CandidateDiscovery
from .pipeline_extract import build_listing, parse_page

log = logging.getLogger(__name__)


class StaticExtractor:
    """Pulls listings using only async HTTP requests."""

    def __init__(self, settings: Settings, fetcher: HttpFetcher) -> None:
        self._settings = settings
        self._fetcher = fetcher
        self._discovery = CandidateDiscovery(settings, fetcher)
        self._listing_sem = asyncio.Semaphore(settings.listing_concurrency)

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

        results: list[Listing] = []
        seen_keys: set[str] = set()
        listing_budget = self._settings.listing_time_budget

        async def _process(url: str) -> Listing | None:
            async with self._listing_sem:
                outcome = await self._fetcher.fetch(url)
            if not outcome.ok or not outcome.is_html_like or not outcome.text:
                return None
            ctx = parse_page(
                outcome.final_url or url,
                outcome.text,
                domain_job=job,
            )
            listing = build_listing(ctx)
            if not listing.is_publishable():
                return None
            return listing

        async def _bounded_process(url: str) -> Listing | None:
            """Per-listing wall-clock guard.

            Mirrors the dynamic extractor's bound (Round 6). A URL
            whose httpx fetch + parse + resolver pipeline does not
            complete inside `listing_time_budget` is dropped
            silently. The other candidates are independent and
            continue.
            """
            try:
                return await asyncio.wait_for(
                    _process(url), timeout=listing_budget,
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
        for coro in asyncio.as_completed(tasks):
            try:
                listing = await coro
            except Exception as exc:  # noqa: BLE001
                # Defensive: any leak from `_bounded_process` must not
                # abort the entire gather. The other candidates are
                # independent.
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
        return results
