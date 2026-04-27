"""Static (HTTPX-driven) listing extractor.

Responsibilities:
    * Aggregate candidate listing URLs from sitemap + homepage links
      + a bounded BFS expansion of hub/index pages.
    * Filter via `listing_filter.classify_url`, with family-aware boost.
    * Fetch each candidate concurrently (bounded), parse, and emit a
      `Listing` whenever a publishable record is produced.
    * Apply per-domain dedup of canonical URLs to avoid double work.

The hub expansion phase is what unlocks franchise sites that publish
only hub anchors on the homepage (Laforet, Nestenn, Guy Hoquet,
Stephane Plaza, MyLogement, ...). It walks at most
`seed_expansion_depth` levels and `max_hub_pages_per_domain` total
hub fetches per domain, so the worst-case cost stays predictable at
55k scale.
"""
from __future__ import annotations

import asyncio
import logging
from collections import deque
from typing import Iterable

from ..config import Settings
from ..fingerprint import Fingerprint
from ..http_client import HttpFetcher
from ..listing_filter import SeedKind, classify_seed, classify_url
from ..models import DomainJob, Listing
from ..seed_discovery import _extract_anchor_hrefs, harvest_homepage_links
from ..sitemap import discover_sitemap_urls
from ..utils.url import (
    canonicalize,
    dedup_key,
    join_url,
    same_registrable_domain,
)
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
            for href in _extract_anchor_hrefs(fingerprint.homepage_html):
                absolute = join_url(fingerprint.final_url or job.url, href)
                if absolute.startswith(("http://", "https://")) and same_registrable_domain(
                    absolute, job.url
                ):
                    homepage_urls.append(absolute)

        seed_urls = list(sitemap_urls) + homepage_urls
        expanded = await self._expand_hubs(job, seed_urls)
        return _rank_and_limit(
            expanded,
            job.url,
            fingerprint.families,
            self._settings.max_listing_urls_per_domain,
        )

    async def _expand_hubs(
        self,
        job: DomainJob,
        seed_urls: Iterable[str],
    ) -> list[str]:
        """BFS over hub pages, returning a deduplicated detail-URL set.

        The seed list is partitioned by `classify_seed` into details
        (kept) and hubs (queued for expansion). Hubs are fetched via
        the shared HttpFetcher so they benefit from per-host limits,
        UA rotation, and retries. Two hard budgets bound the walk:
            * `seed_expansion_depth`     - max BFS levels.
            * `max_hub_pages_per_domain` - max hub HTML fetches.
        """
        max_depth = self._settings.seed_expansion_depth
        hub_budget = self._settings.max_hub_pages_per_domain

        details: dict[str, str] = {}  # canonical_key -> original url
        hub_queue: deque[tuple[str, int]] = deque()
        seen_hubs: set[str] = set()

        def _consider(url: str, depth: int) -> None:
            if not url or not same_registrable_domain(url, job.url):
                return
            kind = classify_seed(url)
            if kind is SeedKind.REJECT:
                return
            canonical = canonicalize(url)
            key = canonical.lower()
            if not key:
                return
            if kind is SeedKind.DETAIL:
                details.setdefault(key, canonical)
                return
            # SeedKind.HUB
            if depth > max_depth:
                return
            if key in seen_hubs:
                return
            seen_hubs.add(key)
            hub_queue.append((canonical, depth))

        for url in seed_urls:
            _consider(url, depth=1)

        if max_depth <= 0 or hub_budget <= 0:
            return list(details.values())

        hubs_fetched = 0
        while hub_queue and hubs_fetched < hub_budget:
            hub_url, depth = hub_queue.popleft()
            hubs_fetched += 1
            outcome = await self._fetcher.fetch(hub_url)
            if (
                not outcome.ok
                or not outcome.is_html_like
                or not outcome.text
            ):
                continue
            base = outcome.final_url or hub_url
            for href in _extract_anchor_hrefs(outcome.text):
                if href.startswith(("mailto:", "tel:", "javascript:", "#")):
                    continue
                absolute = join_url(base, href)
                if not absolute.startswith(("http://", "https://")):
                    continue
                _consider(absolute, depth=depth + 1)

        if hubs_fetched:
            log.debug(
                "static: %s expanded %d hub(s) -> %d detail candidates",
                job.domain, hubs_fetched, len(details),
            )
        return list(details.values())
