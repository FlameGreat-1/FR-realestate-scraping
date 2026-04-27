"""Static (HTTPX-driven) listing extractor.

Responsibilities:
    * Aggregate candidate listing URLs from sitemap + homepage links.
    * Filter via `listing_filter.classify_url`, with family-aware boost.
    * Fetch each candidate concurrently (bounded), parse, and emit a
      `Listing` whenever a publishable record is produced.
    * Apply per-domain dedup of canonical URLs to avoid double work.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Iterable

from ..config import Settings
from ..fingerprint import Fingerprint
from ..http_client import HttpFetcher
from ..listing_filter import classify_url
from ..models import DomainJob, Listing
from ..seed_discovery import harvest_homepage_links
from ..sitemap import discover_sitemap_urls
from ..utils.url import canonicalize, dedup_key, same_registrable_domain
from .pipeline_extract import build_listing, parse_page

log = logging.getLogger(__name__)


def _rank_and_limit(
    urls: Iterable[str],
    base_url: str,
    families: tuple,
    limit: int,
) -> list[str]:
    seen: set[str] = set()
    scored: list[tuple[int, str]] = []
    for raw in urls:
        if not raw:
            continue
        if not same_registrable_domain(raw, base_url):
            continue
        canonical = canonicalize(raw)
        key = canonical.lower()
        if not key or key in seen:
            continue
        seen.add(key)
        verdict = classify_url(canonical)
        if not verdict.accepted:
            continue
        score = verdict.score
        for family in families or ():
            score += family.boost_url(canonical)
        scored.append((score, canonical))
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [url for _, url in scored[:limit]]


class StaticExtractor:
    """Pulls listings using only async HTTP requests."""

    def __init__(self, settings: Settings, fetcher: HttpFetcher) -> None:
        self._settings = settings
        self._fetcher = fetcher
        self._listing_sem = asyncio.Semaphore(settings.listing_concurrency)

    async def gather_listings(
        self,
        job: DomainJob,
        fingerprint: Fingerprint,
    ) -> list[Listing]:
        candidates = await self._collect_candidates(job, fingerprint)
        if not candidates:
            log.info("static: no candidate listings for %s", job.domain)
            return []
        log.info(
            "static: %s -> %d candidate listing URLs",
            job.domain, len(candidates),
        )

        results: list[Listing] = []
        seen_keys: set[str] = set()

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

        tasks = [asyncio.create_task(_process(url)) for url in candidates]
        for coro in asyncio.as_completed(tasks):
            listing = await coro
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

    async def _collect_candidates(
        self,
        job: DomainJob,
        fingerprint: Fingerprint,
    ) -> list[str]:
        sitemap_urls = await discover_sitemap_urls(
            job.url,
            self._fetcher,
            max_depth=self._settings.max_sitemap_depth,
        )

        homepage_urls: list[str] = []
        if not sitemap_urls or len(sitemap_urls) < 5:
            _, homepage_urls = await harvest_homepage_links(job.url, self._fetcher)
        elif fingerprint.homepage_html:
            # Reuse what we already fetched during fingerprinting.
            from ..seed_discovery import _extract_anchor_hrefs
            from ..utils.url import join_url, same_registrable_domain
            for href in _extract_anchor_hrefs(fingerprint.homepage_html):
                absolute = join_url(fingerprint.final_url or job.url, href)
                if absolute.startswith(("http://", "https://")) and same_registrable_domain(
                    absolute, job.url
                ):
                    homepage_urls.append(absolute)

        merged = list(sitemap_urls) + homepage_urls
        return _rank_and_limit(
            merged,
            job.url,
            fingerprint.families,
            self._settings.max_listing_urls_per_domain,
        )
