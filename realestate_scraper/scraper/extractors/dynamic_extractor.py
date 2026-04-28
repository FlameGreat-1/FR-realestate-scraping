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

# Opportunistic post-domcontentloaded settle wait. Capped low enough
# that a slow site cannot dominate the per-domain budget, and high
# enough to let JS redirects / WAF interstitials complete before we
# read `page.content()` (which is what causes the "Execution context
# destroyed" race when the wait is omitted).
_NETWORK_IDLE_TIMEOUT_MS: int = 2_000
# Brief settle delay between render attempts. A navigation race
# almost always resolves on the second try because the redirect /
# challenge has had time to complete.
_RETRY_SETTLE_SECONDS: float = 0.4


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
        """Last-resort per-page Playwright render with race-safe content read."""
        for attempt in (1, 2):
            html = await self._safe_render(url, target_url=url)
            if html:
                return html
            if attempt == 1:
                # Brief settle delay before retrying. A navigation race
                # almost always resolves on the second attempt because
                # the redirect / WAF challenge has had time to complete.
                await asyncio.sleep(_RETRY_SETTLE_SECONDS)
        return ""

    async def _render_homepage(self, job: DomainJob) -> tuple[str, str]:
        """Render the homepage in Playwright, return (html, final_url).

        Errors return empty strings; the caller falls back to the
        fingerprint's cached HTML so a flaky Playwright launch does
        not cost us all coverage on the domain.
        """
        for attempt in (1, 2):
            html, final_url = await self._safe_render(
                job.url, target_url=job.url, return_final_url=True,
            )
            if html:
                return html, final_url or job.url
            if attempt == 1:
                await asyncio.sleep(_RETRY_SETTLE_SECONDS)
        return "", ""

    async def _safe_render(
        self,
        url: str,
        *,
        target_url: str,
        return_final_url: bool = False,
    ):
        """Render `url` once, returning HTML (and optionally the final URL).

        Layered waits handle two distinct failure modes:
          * `domcontentloaded` is the primary wait: fast, sufficient
            for the majority of pages.
          * `networkidle` is an opportunistic secondary wait capped at
            `_NETWORK_IDLE_TIMEOUT_MS`. It lets JS redirects and WAF
            interstitials resolve before we read `page.content()`,
            which is what eliminates the "Execution context
            destroyed" race observed on Round 3.
          * `page.content()` is wrapped in a try/except: a navigation
            race that kills the execution context surfaces as a
            Playwright Error, and the caller will retry once.
          * Status >= 400 is no longer fatal. WAF sites (Cloudflare,
            Imperva, ...) routinely serve a 403 interstitial whose
            JS then redirects to the real homepage. We let the
            redirect happen (via the networkidle wait) and read the
            post-redirect HTML regardless of the initial status.
        """
        nav_timeout_ms = int(self._settings.browser_nav_timeout * 1000)
        try:
            async with self._pool.page(target_url=target_url) as page:
                try:
                    await page.goto(
                        url,
                        wait_until="domcontentloaded",
                        timeout=nav_timeout_ms,
                    )
                except Exception as exc:  # noqa: BLE001
                    log.debug("dynamic goto %s failed: %s", url, exc)
                    return ("", "") if return_final_url else ""
                # Opportunistic networkidle wait. A timeout is fine -
                # we proceed with whatever DOM is available.
                try:
                    await page.wait_for_load_state(
                        "networkidle", timeout=_NETWORK_IDLE_TIMEOUT_MS,
                    )
                except Exception:  # noqa: BLE001
                    pass
                try:
                    html = await page.content()
                except Exception as exc:  # noqa: BLE001
                    log.debug(
                        "dynamic content() %s failed (race): %s",
                        url, exc,
                    )
                    return ("", "") if return_final_url else ""
                final_url = ""
                try:
                    final_url = str(page.url) or url
                except Exception:  # noqa: BLE001
                    final_url = url
                if return_final_url:
                    return html or "", final_url
                return html or ""
        except Exception as exc:  # noqa: BLE001
            log.debug("dynamic page session %s failed: %s", url, exc)
            return ("", "") if return_final_url else ""

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
