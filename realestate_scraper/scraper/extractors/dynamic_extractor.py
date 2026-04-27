"""Dynamic (Playwright) listing extractor.

Used for sites the fingerprint flagged as `Strategy.DYNAMIC` or that
blocked the static fetcher. Reuses the resolver pipeline so the output
contract is identical to the static path.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Iterable

from ..browser_pool import BrowserPool
from ..config import Settings
from ..fingerprint import Fingerprint
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
    """Pulls listings using a headless Chromium instance."""

    def __init__(self, settings: Settings, browser_pool: BrowserPool) -> None:
        self._settings = settings
        self._pool = browser_pool

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
        nav_timeout_ms = int(self._settings.browser_nav_timeout * 1000)

        async def _process(url: str) -> Listing | None:
            try:
                async with self._pool.page(target_url=url) as page:
                    response = await page.goto(
                        url, wait_until="domcontentloaded", timeout=nav_timeout_ms
                    )
                    if response is None or response.status >= 400:
                        return None
                    html = await page.content()
                    if not html:
                        return None
            except Exception as exc:  # noqa: BLE001
                log.debug("dynamic fetch %s failed: %s", url, exc)
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

    async def _discover_candidates(
        self,
        job: DomainJob,
        fingerprint: Fingerprint,
    ) -> list[str]:
        """Use the browser to render the homepage and harvest links."""
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
                    for href in _extract_anchor_hrefs(html or ""):
                        absolute = join_url(job.url, href)
                        if absolute.startswith(("http://", "https://")):
                            urls.append(absolute)
        except Exception as exc:  # noqa: BLE001
            log.debug("dynamic homepage harvest %s failed: %s", job.url, exc)

        limit = max(
            10,
            self._settings.max_listing_urls_per_domain // _DYNAMIC_LIMIT_DIVISOR,
        )
        return _rank_and_limit(urls, job.url, fingerprint.families, limit)
