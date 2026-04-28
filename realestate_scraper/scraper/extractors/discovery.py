"""Shared candidate-listing-URL discovery component.

Both the static (httpx-only) and dynamic (Playwright-assisted)
extractors need the same generic discovery pipeline:

    sitemap fetch  +  homepage anchors  +  bounded hub BFS
        ->  classifier-filtered, ranked, deduplicated detail URL list

Keeping this in one place guarantees that the two extractors achieve
the same coverage on a given site - the only thing that should differ
is *how the homepage HTML is obtained*. The static path reuses the
homepage already fetched during fingerprinting; the dynamic path
renders the homepage in Playwright (so Cloudflare cookie negotiation
and JS rendering happen there) and passes the resulting HTML in.

Design rules:
    * No I/O outside the shared HttpFetcher. Sitemap fetches and hub
      fetches go through the same per-host limiter, UA rotation, and
      retry policy as every other request in the pipeline.
    * Two hard budgets cap the worst-case cost per domain:
          - `seed_expansion_depth`     : max BFS levels.
          - `max_hub_pages_per_domain` : max hub HTML fetches.
      These are unchanged from the original static-only implementation.
    * Output is ranked using `listing_filter.classify_url` plus a
      family-aware score boost, then truncated to
      `max_listing_urls_per_domain`.
"""
from __future__ import annotations

import asyncio
import logging
from collections import deque
from typing import Iterable, Optional

from ..config import Settings
from ..http_client import HttpFetcher
from ..listing_filter import SeedKind, classify_seed, classify_url
from ..models import DomainJob
from ..seed_discovery import _extract_anchor_hrefs, harvest_homepage_links
from ..sitemap import discover_sitemap_urls
from ..utils.url import (
    canonicalize,
    join_url,
    same_registrable_domain,
)

log = logging.getLogger(__name__)


def rank_and_limit(
    urls: Iterable[str],
    base_url: str,
    families: tuple,
    limit: int,
) -> list[str]:
    """Filter, score, deduplicate and truncate a candidate URL set.

    Exposed at module scope so test modules and other callers can
    reuse the exact ranking the discovery component applies.
    """
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


class CandidateDiscovery:
    """Build a ranked detail-URL list for a domain via httpx-only I/O."""

    def __init__(self, settings: Settings, fetcher: HttpFetcher) -> None:
        self._settings = settings
        self._fetcher = fetcher

    async def discover(
        self,
        job: DomainJob,
        families: tuple,
        *,
        homepage_html: Optional[str] = None,
        base_url: Optional[str] = None,
    ) -> list[str]:
        """Return a ranked, classifier-filtered detail-URL list for `job`.

        Sitemap discovery and homepage anchor harvest run concurrently;
        their union is then expanded via a bounded BFS over hub pages.

        :param homepage_html: pre-fetched/pre-rendered homepage HTML.
            When provided, the homepage harvest skips the network and
            derives anchors directly from this HTML.
        :param base_url: URL the homepage HTML belongs to (used for
            relative-link resolution). Defaults to `job.url`.
        """
        sitemap_task = asyncio.create_task(
            discover_sitemap_urls(
                job.url,
                self._fetcher,
                max_depth=self._settings.max_sitemap_depth,
            )
        )
        homepage_task = asyncio.create_task(
            self._harvest_homepage(job, homepage_html, base_url)
        )
        sitemap_urls, homepage_urls = await asyncio.gather(
            sitemap_task, homepage_task
        )

        seed_urls = list(sitemap_urls) + list(homepage_urls)
        expanded = await self._expand_hubs(job, seed_urls)
        return rank_and_limit(
            expanded,
            job.url,
            families,
            self._settings.max_listing_urls_per_domain,
        )

    async def _harvest_homepage(
        self,
        job: DomainJob,
        homepage_html: Optional[str],
        base_url: Optional[str],
    ) -> list[str]:
        if homepage_html:
            anchored_base = base_url or job.url
            out: list[str] = []
            for href in _extract_anchor_hrefs(homepage_html):
                absolute = join_url(anchored_base, href)
                if not absolute.startswith(("http://", "https://")):
                    continue
                if not same_registrable_domain(absolute, job.url):
                    continue
                out.append(absolute)
            return out
        _, fresh = await harvest_homepage_links(job.url, self._fetcher)
        return fresh

    async def _expand_hubs(
        self,
        job: DomainJob,
        seed_urls: Iterable[str],
    ) -> list[str]:
        max_depth = self._settings.seed_expansion_depth
        hub_budget = self._settings.max_hub_pages_per_domain

        details: dict[str, str] = {}
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
                "discovery: %s expanded %d hub(s) -> %d detail candidates",
                job.domain, hubs_fetched, len(details),
            )
        return list(details.values())
