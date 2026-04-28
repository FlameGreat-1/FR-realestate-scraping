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
    ensure_scheme,
    join_url,
    parse_host,
    parse_registrable_domain,
    same_registrable_domain,
)

# Hard cap on franchise sub-domains harvested per fan-out call. With
# typical agency-network indexes listing 50-200 branches, this keeps
# the per-domain cost bounded at 55k+ scale: 8 extra homepage fetches
# at listing_concurrency capacity.
_MAX_FRANCHISE_SUBDOMAINS: int = 8

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

        # Franchise fan-out: when the root domain produced nothing
        # AND a franchise family declares well-known agency-index
        # paths, harvest the listed sub-domains and feed their
        # homepages into the same pipeline. Only runs on zero
        # candidates so successful root domains pay no extra cost.
        if not expanded:
            franchise_urls = await self._fan_out_franchise_subdomains(
                job, families,
            )
            if franchise_urls:
                expanded = franchise_urls

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

    async def _fan_out_franchise_subdomains(
        self,
        job: DomainJob,
        families: tuple,
    ) -> list[str]:
        """Harvest detail-URL candidates from franchise branch sub-domains.

        The flow:
          1. Pick the first family that declares `agency_index_paths`.
          2. Fetch index paths in declared order until one returns
             usable HTML.
          3. Parse anchors and keep distinct sub-domain hosts under
             the same registrable domain.
          4. For each sub-domain (capped at
             `_MAX_FRANCHISE_SUBDOMAINS`), harvest the homepage
             concurrently through the shared fetcher.
          5. Return the union of harvested URLs.
        Returns an empty list when no family declares paths, when
        every index path fails, or when no sub-domains are found.
        """
        index_paths: tuple[str, ...] = ()
        for family in families or ():
            if family.agency_index_paths:
                index_paths = family.agency_index_paths
                break
        if not index_paths:
            return []

        # Resolve the index path against the registrable domain so
        # the fan-out works regardless of whether the input host is
        # the root (`stephaneplazaimmobilier.com`) or a branch
        # sub-domain (`bordeaux.stephaneplazaimmobilier.com`). The
        # franchise agency index always lives on the root host.
        registrable = parse_registrable_domain(job.url)
        base = (
            f"https://{registrable}/"
            if registrable
            else ensure_scheme(job.url)
        )
        if not base:
            return []

        index_html = ""
        index_final_url = ""
        for path in index_paths:
            target = join_url(base, path)
            outcome = await self._fetcher.fetch(target)
            if (
                outcome.ok
                and outcome.is_html_like
                and outcome.text
            ):
                index_html = outcome.text
                index_final_url = outcome.final_url or target
                break
        if not index_html:
            return []

        root_host = parse_host(job.url)
        seen_hosts: set[str] = set()
        subdomain_urls: list[str] = []
        for href in _extract_anchor_hrefs(index_html):
            absolute = join_url(index_final_url, href)
            if not absolute.startswith(("http://", "https://")):
                continue
            if not same_registrable_domain(absolute, job.url):
                continue
            host = parse_host(absolute)
            if not host or host == root_host:
                continue
            if host in seen_hosts:
                continue
            seen_hosts.add(host)
            # Reduce each branch to its homepage URL; the per-branch
            # harvest below extracts the detail anchors.
            subdomain_urls.append(f"https://{host}/")
            if len(subdomain_urls) >= _MAX_FRANCHISE_SUBDOMAINS:
                break
        if not subdomain_urls:
            return []

        # Harvest each branch homepage concurrently. Per-host
        # concurrency is enforced by the shared limiter.
        outcomes = await asyncio.gather(
            *(self._fetcher.fetch(url) for url in subdomain_urls),
            return_exceptions=True,
        )
        out: list[str] = []
        for branch_url, outcome in zip(subdomain_urls, outcomes):
            if isinstance(outcome, BaseException):
                continue
            if (
                not outcome.ok
                or not outcome.is_html_like
                or not outcome.text
            ):
                continue
            branch_base = outcome.final_url or branch_url
            for href in _extract_anchor_hrefs(outcome.text):
                if href.startswith(("mailto:", "tel:", "javascript:", "#")):
                    continue
                absolute = join_url(branch_base, href)
                if not absolute.startswith(("http://", "https://")):
                    continue
                if not same_registrable_domain(absolute, job.url):
                    continue
                out.append(absolute)
        log.debug(
            "discovery: %s franchise fan-out -> %d branches, %d urls",
            job.domain, len(subdomain_urls), len(out),
        )
        return out

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
        # Fetch all hubs at the same BFS depth concurrently instead of
        # sequentially. This reduces hub expansion from sum(fetch_times)
        # to max(fetch_times) per depth level.
        while hub_queue and hubs_fetched < hub_budget:
            # Drain the current depth level into a batch.
            batch: list[tuple[str, int]] = []
            while hub_queue and hubs_fetched + len(batch) < hub_budget:
                batch.append(hub_queue.popleft())
            if not batch:
                break

            outcomes = await asyncio.gather(
                *(self._fetcher.fetch(hub_url) for hub_url, _ in batch),
                return_exceptions=True,
            )
            hubs_fetched += len(batch)

            for (hub_url, depth), outcome in zip(batch, outcomes):
                if isinstance(outcome, BaseException):
                    continue
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
