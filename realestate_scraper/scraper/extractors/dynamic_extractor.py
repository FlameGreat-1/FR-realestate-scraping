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
        the browser pool semaphore, the per-page navigation timeout,
        and a hard per-listing wall-clock cap so one slow URL cannot
        dominate the per-domain runtime.

    Per-listing wall-clock cap:
        Every candidate URL runs inside `asyncio.wait_for(
            timeout=settings.listing_time_budget)`. A URL that does
        not yield within this budget is dropped silently; the other
        119 candidates continue. This is the only safe shape when
        multiple shared resources (browser pool, httpx pool, per-host
        limiter) can interact in unexpected ways.

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
from .pipeline_extract import parse_and_build_listing

log = logging.getLogger(__name__)

_BLOCK_STATUSES: frozenset[int] = frozenset({401, 403, 429})

# Networkidle wait is reserved for the homepage path where JS / WAF
# interstitials redirect to the real homepage. Detail pages return
# clean HTML on `domcontentloaded` and the extra wait is pure cost.
_NETWORK_IDLE_TIMEOUT_MS: int = 2_000
# Brief settle delay between homepage render attempts. A navigation
# race almost always resolves on the second try because the redirect
# / challenge has had time to complete. Detail pages do NOT retry -
# we have 119 alternatives so paying this cost there is wasteful.
_HOMEPAGE_RETRY_SETTLE_SECONDS: float = 0.4


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
        listing_budget = self._settings.listing_time_budget

        async def _process(url: str) -> Optional[Listing]:
            html = await self._get_html(url)
            if not html:
                return None
            # CPU-bound parse + resolver work runs OFF the event loop.
            # selectolax and the regex engine do NOT yield to asyncio,
            # so calling this synchronously here would freeze every
            # other domain coroutine until the call returned. The
            # to_thread handoff lets `asyncio.wait_for` actually
            # fire on the listing_time_budget and lets other
            # coroutines progress while CPU work is in flight.
            return await asyncio.to_thread(
                parse_and_build_listing, url, html, job,
            )

        async def _bounded_process(url: str) -> Optional[Listing]:
            """Per-listing wall-clock guard.

            A single URL must NEVER dominate the per-domain budget,
            even when shared resources (browser pool, httpx pool,
            per-host limiter) interact in unexpected ways. The wait_for
            cap is the architectural guarantee.
            """
            try:
                return await asyncio.wait_for(
                    _process(url), timeout=listing_budget,
                )
            except asyncio.TimeoutError:
                log.debug(
                    "dynamic: listing %s exceeded %.1fs budget, dropping",
                    url, listing_budget,
                )
                return None
            except Exception as exc:  # noqa: BLE001
                log.debug("dynamic: listing %s failed: %s", url, exc)
                return None

        tasks = [
            asyncio.create_task(_bounded_process(url)) for url in candidates
        ]
        try:
            for coro in asyncio.as_completed(tasks):
                try:
                    listing = await coro
                except Exception as exc:  # noqa: BLE001
                    log.debug("dynamic: task crashed: %s", exc)
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
        finally:
            # Structured cancellation: when the domain-level wait_for
            # fires or any exception propagates, every pending task
            # MUST be cancelled. Without this, orphaned tasks hold
            # browser pool slots, httpx connections, and thread pool
            # workers indefinitely, causing cascading hangs across
            # all subsequent domains.
            for task in tasks:
                if not task.done():
                    task.cancel()
            # Give cancelled tasks one event-loop tick to process the
            # CancelledError so their finally blocks (semaphore
            # releases, page closes) actually execute.
            await asyncio.gather(*tasks, return_exceptions=True)
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
        """Single-attempt per-page Playwright render.

        No retry: detail pages have 119 alternatives, and the wall-
        clock cost of a second attempt outweighs the marginal
        coverage gain. Networkidle wait is also disabled here -
        it is only worth the wait on the homepage path where WAF
        interstitials redirect.
        """
        return await self._safe_render(
            url, target_url=url, wait_for_idle=False,
        )

    async def _render_homepage(self, job: DomainJob) -> tuple[str, str]:
        """Render the homepage in Playwright with a single retry.

        Two attempts are used here (and ONLY here) because homepage
        coverage is critical: a missed homepage means missing the
        anchor seed for every detail page. Detail pages have 119
        alternatives so a render miss is harmless.

        Errors return empty strings; the caller falls back to the
        fingerprint's cached HTML so a flaky Playwright launch does
        not cost us all coverage on the domain.
        """
        for attempt in (1, 2):
            html, final_url = await self._safe_render(
                job.url, target_url=job.url,
                wait_for_idle=True, return_final_url=True,
            )
            if html:
                return html, final_url or job.url
            if attempt == 1:
                await asyncio.sleep(_HOMEPAGE_RETRY_SETTLE_SECONDS)
        return "", ""

    async def _safe_render(
        self,
        url: str,
        *,
        target_url: str,
        wait_for_idle: bool = False,
        return_final_url: bool = False,
    ):
        """Render `url` once, returning HTML (and optionally the final URL).

        :param wait_for_idle:
            When True, await `networkidle` (capped at
            `_NETWORK_IDLE_TIMEOUT_MS`) after `domcontentloaded` so
            JS redirects and WAF interstitials resolve before we read
            `page.content()`. Reserved for the homepage path; detail
            pages do not need it and pay only the cost.

        Robustness handles two distinct failure modes:
          * `domcontentloaded` is the primary wait: fast, sufficient
            for the majority of pages.
          * `page.content()` is wrapped in a try/except: a navigation
            race that kills the execution context surfaces as a
            Playwright Error, which we treat as a permanent failure
            for that URL (no retry at the per-detail level).
          * Status >= 400 is no longer fatal. WAF sites (Cloudflare,
            Imperva, ...) routinely serve a 403 interstitial whose
            JS then redirects to the real homepage. We let the
            redirect happen (when `wait_for_idle=True`) and read
            the post-redirect HTML regardless of the initial status.
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
                if wait_for_idle:
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
