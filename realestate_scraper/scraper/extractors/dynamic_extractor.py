"""Dynamic (Playwright-assisted) listing extractor.

Used for sites the fingerprint flagged as `Strategy.DYNAMIC` or that
blocked the static fetcher. Reuses the resolver pipeline so the output
contract is identical to the static path.

Design:
    The expensive part of dynamic extraction is *navigation*, not
    parsing. So we minimise it:

    1. Use Playwright to render the homepage and harvest anchors.
       This is the only step that genuinely needs JS or Cloudflare
       cookie negotiation.
    2. Fetch every detail URL via the shared HttpFetcher (httpx) with
       the rotated UA + client-hint profile. Most WAF-protected sites
       only challenge the homepage; detail pages serve clean HTML to
       a request that already presents a coherent fingerprint.
    3. If a single detail URL returns 401/403/429 via httpx, escalate
       only that URL to Playwright. The escalation is bounded by the
       browser pool semaphore and the per-page navigation timeout, so
       it cannot dominate the runtime.

This keeps the Playwright cost proportional to the *blocked subset*
of a domain instead of the full candidate set.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Iterable, Optional

from ..browser_pool import BrowserPool
from ..config import Settings
from ..fingerprint import Fingerprint
from ..http_client import FetchOutcome, HttpFetcher
from ..listing_filter import classify_url
from ..models import DomainJob, Listing
from ..seed_discovery import _extract_anchor_hrefs
from ..utils.url import (
    canonicalize,
    dedup_key,
    join_url,
    same_registrable_domain,
)
from .pipeline_extract import build_listing, parse_page

log = logging.getLogger(__name__)

_DYNAMIC_LIMIT_DIVISOR = 3
_BLOCK_STATUSES: frozenset[int] = frozenset({401, 403, 429})


def _rank_and_limit(
    urls: Iterable[str],
    base_url: str,
    families: tuple,
    limit: int,
) -> list[str]:
    seen: set[str] = set()
    scored: list[tuple[int, str]] = []
    for raw in urls:
        if not raw or not same_registrable_domain(raw, base_url):
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


class DynamicExtractor:
    """Pulls listings using a headless Chromium instance for discovery only."""

    def __init__(
        self,
        settings: Settings,
        browser_pool: BrowserPool,
        fetcher: HttpFetcher,
    ) -> None:
        self._settings = settings
        self._pool = browser_pool
        self._fetcher = fetcher
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

    async def _discover_candidates(
        self,
        job: DomainJob,
        fingerprint: Fingerprint,
    ) -> list[str]:
        """Render the homepage in a browser, then harvest its anchors."""
        urls: list[str] = []
        nav_timeout_ms = int(self._settings.browser_nav_timeout * 1000)
        try:
            async with self._pool.page(target_url=job.url) as page:
                response = await page.goto(
                    job.url,
                    wait_until="domcontentloaded",
                    timeout=nav_timeout_ms,
                )
                if response is not None and response.status < 400:
                    html = await page.content()
                    base = str(page.url) or job.url
                    for href in _extract_anchor_hrefs(html or ""):
                        absolute = join_url(base, href)
                        if absolute.startswith(("http://", "https://")):
                            urls.append(absolute)
        except Exception as exc:  # noqa: BLE001
            log.debug("dynamic homepage harvest %s failed: %s", job.url, exc)

        # If Playwright is unavailable or the rendered homepage was
        # empty, fall back to whatever the fingerprint already captured.
        if not urls and fingerprint.homepage_html:
            base = fingerprint.final_url or job.url
            for href in _extract_anchor_hrefs(fingerprint.homepage_html):
                absolute = join_url(base, href)
                if absolute.startswith(("http://", "https://")):
                    urls.append(absolute)

        limit = max(
            10,
            self._settings.max_listing_urls_per_domain // _DYNAMIC_LIMIT_DIVISOR,
        )
        return _rank_and_limit(urls, job.url, fingerprint.families, limit)
