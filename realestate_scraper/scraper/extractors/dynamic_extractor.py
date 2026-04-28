"""Dynamic (Playwright-assisted) listing extractor.

Used for sites the fingerprint flagged as `Strategy.DYNAMIC` or that
blocked the static fetcher. Reuses the resolver pipeline so the output
contract is identical to the static path.

Design:
    The expensive part of dynamic extraction is *navigation*, not
    parsing. So we minimise it.

    Discovery:
        Playwright is used for one thing only: rendering the
        homepage so JS execution and Cloudflare cookie negotiation
        happen there. The rendered homepage HTML is then fed into
        the shared `CandidateDiscovery` component, which runs the
        same sitemap + anchor + bounded hub BFS pipeline as the
        static path - all over httpx, never touching Chromium for
        discovery itself.

    Detail fetching:
        Each candidate URL is fetched via the shared HttpFetcher
        with the rotated UA + client-hint profile that matches the
        Playwright session. WAF-protected sites typically only
        challenge the homepage; detail pages serve clean HTML once
        the request presents a coherent fingerprint.

    Per-page Playwright escalation:
        If a detail-URL httpx fetch returns 401/403/429, that single
        URL is rendered in Playwright. The escalation is bounded by
        the browser pool semaphore and the per-page navigation
        timeout, so it cannot dominate the runtime.

This keeps Playwright cost proportional to the *blocked subset* of a
domain and gives the dynamic path the same discovery coverage as the
static path, instead of the homepage-anchors-only fallback that was
the Round-1 default.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Optional

from ..browser_pool import BrowserPool
from ..config import Settings
from ..fingerprint import Fingerprint
from ..http_client import FetchOutcome, HttpFetcher
from ..models import DomainJob, Listing
from ..utils.url import dedup_key
from .discovery import CandidateDiscovery
from .pipeline_extract import build_listing, parse_page

log = logging.getLogger(__name__)

_BLOCK_STATUSES: frozenset[int] = frozenset({401, 403, 429})


class DynamicExtractor:
    """Listings extractor that uses Playwright only where it is needed."""

    def __init__(
        self,
        settings: Settings,
        browser_pool: BrowserPool,
        fetcher: HttpFetcher,
    ) -> None:
        self._settings = settings
        self._pool = browser_pool
        self._fetcher = fetcher
        self._discovery = CandidateDiscovery(settings, fetcher)
        self._listing_sem = asyncio.Semaphore(settings.listing_concurrency)

    @property
    def is_available(self) -> bool:
        return self._pool.is_available

    async def gather_listings(
        self,
        job: DomainJob,
        fingerprint: Fingerprint,
    ) -> list[Listing]:
        if not self.is_available:
            return []

        candidates = await self._discover_candidates(job, fingerprint)
        if not candidates:
            log.info("dynamic: no candidate listings for %s", job.domain)
            return []
        log.info(
            "dynamic: %s -> %d candidate listing URLs",
            job.domain, len(candidates),
        )

        results: list[Listing] = []
        seen_keys: set[str] = set()

        async def _process(url: str) -> Optional[Listing]:
            html = await self._get_html(url)
            if not html:
                return None
            ctx = parse_page(url, html, domain_job=job)
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

    async def _get_html(self, url: str) -> str:
        """Try httpx first; escalate to Playwright only on hard blocks."""
        async with self._listing_sem:
            outcome: FetchOutcome = await self._fetcher.fetch(url)
        if outcome.ok and outcome.is_html_like and outcome.text:
            return outcome.text
        if outcome.status is None or outcome.status in _BLOCK_STATUSES:
            html = await self._render_with_playwright(url)
            if html:
                return html
        return ""

    async def _render_with_playwright(self, url: str) -> str:
        """Last-resort per-page Playwright render. Errors swallowed by design."""
        nav_timeout_ms = int(self._settings.browser_nav_timeout * 1000)
        try:
            async with self._pool.page(target_url=url) as page:
                response = await page.goto(
                    url,
                    wait_until="domcontentloaded",
                    timeout=nav_timeout_ms,
                )
                if response is None or response.status >= 400:
                    return ""
                return await page.content() or ""
        except Exception as exc:  # noqa: BLE001
            log.debug("dynamic page render %s failed: %s", url, exc)
            return ""

    async def _render_homepage(self, job: DomainJob) -> tuple[str, str]:
        """Render the homepage in Playwright, return (html, final_url).

        Errors return empty strings; the caller falls back to the
        fingerprint's cached HTML so a flaky Playwright launch does
        not cost us all coverage on the domain.
        """
        nav_timeout_ms = int(self._settings.browser_nav_timeout * 1000)
        try:
            async with self._pool.page(target_url=job.url) as page:
                response = await page.goto(
                    job.url,
                    wait_until="domcontentloaded",
                    timeout=nav_timeout_ms,
                )
                if response is None or response.status >= 400:
                    return "", ""
                html = await page.content()
                return html or "", str(page.url) or job.url
        except Exception as exc:  # noqa: BLE001
            log.debug("dynamic homepage harvest %s failed: %s", job.url, exc)
            return "", ""

    async def _discover_candidates(
        self,
        job: DomainJob,
        fingerprint: Fingerprint,
    ) -> list[str]:
        """Build the full candidate list using the shared discovery.

        Playwright renders the homepage; the rendered HTML feeds the
        same sitemap + anchor + hub-BFS pipeline the static path uses.
        """
        rendered_html, rendered_base = await self._render_homepage(job)

        if not rendered_html:
            # Playwright failed or returned nothing. Fall back to the
            # fingerprint's cached HTML so we never lose discovery
            # coverage to a transient browser failure.
            rendered_html = fingerprint.homepage_html or ""
            rendered_base = fingerprint.final_url or job.url

        return await self._discovery.discover(
            job,
            fingerprint.families,
            homepage_html=rendered_html or None,
            base_url=rendered_base or job.url,
        )
