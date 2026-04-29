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
from concurrent.futures import ThreadPoolExecutor
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


def consume_orphan_exception(task: asyncio.Task) -> None:
    """Done-callback that retrieves an abandoned task's exception.

    Called only on tasks that the cleanup gather abandoned because
    they did not honour cancellation within the 5s window. Reading
    the exception (and discarding it) marks the future as retrieved
    so the asyncio garbage collector does not emit the cosmetic
    `Future exception was never retrieved` warning.

    Shared between the static and dynamic extractors; the symbol
    is module-public so the cross-module import is intentional.
    """
    if task.cancelled():
        return
    try:
        task.exception()
    except (asyncio.CancelledError, asyncio.InvalidStateError):
        pass

# Post-domcontentloaded settle for homepage renders. Cloudflare and
# Imperva interstitials redirect via short JS timer; 300ms is enough
# for the redirect to fire and is far cheaper than waiting on
# networkidle (2s every time, rarely converts).
_HOMEPAGE_SETTLE_SECONDS: float = 0.3


# Hard cap on TOTAL Playwright escalations from detail-page fetches
# within a single gather_listings call. With 4 browser contexts and
# 12 concurrent domains, 6/domain produced ~72 potential queued
# borrows on the 4-slot semaphore - queue depth alone exceeded the
# per-domain budget. 3 keeps it at ~36, drainable inside budget.
_MAX_DETAIL_ESCALATION_BUDGET: int = 3


class DynamicExtractor:
    """Listings extractor that uses Playwright only where it is needed."""

    def __init__(
        self,
        settings: Settings,
        browser_pool: BrowserPool,
        fetcher: HttpFetcher,
        *,
        parse_pool: Optional[ThreadPoolExecutor] = None,
    ) -> None:
        self._settings = settings
        self._pool = browser_pool
        self._fetcher = fetcher
        self._discovery = CandidateDiscovery(settings, fetcher)
        self._listing_sem = asyncio.Semaphore(settings.listing_concurrency)
        # Explicit parse pool: never the loop's default executor.
        # The loop's default pool is shared with Playwright's chromium
        # IPC; mixing parse jobs onto it stalls the driver pipe.
        self._parse_pool = parse_pool

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

        discovery_budget = (
            self._settings.domain_time_budget
            * self._settings.discovery_budget_ratio
        )
        try:
            candidates = await asyncio.wait_for(
                self._discover_candidates(job, fingerprint),
                timeout=discovery_budget,
            )
        except asyncio.TimeoutError:
            log.info(
                "dynamic: %s discovery budget exhausted after %.0fs",
                job.domain, discovery_budget,
            )
            candidates = []
        if not candidates:
            log.info("dynamic: no candidate listings for %s", job.domain)
            return []
        log.info(
            "dynamic: %s -> %d candidate listing URLs",
            job.domain, len(candidates),
        )

        # Hard wall-clock cap on the entire candidate gather. The
        # pipeline-level domain_time_budget is the contract, but the
        # loop's timer wheel can be starved by chromium IPC traffic
        # under heavy browser-pool contention; an inner cap here
        # guarantees we hand control back regardless. The ratio is
        # configurable so operators can rebalance against the static
        # ratio when tuning a large corpus.
        gather_budget = (
            self._settings.domain_time_budget
            * self._settings.dynamic_gather_budget_ratio
        )

        results: list[Listing] = []
        seen_keys: set[str] = set()
        listing_budget = self._settings.listing_time_budget
        loop = asyncio.get_running_loop()

        # Mutable counter shared across all _get_html calls in this
        # gather. Tracks total Playwright escalation attempts so we
        # can enforce the per-domain budget without a racy semaphore.
        escalation_count: list[int] = [0]

        async def _fetch_and_parse(url: str) -> Optional[Listing]:
            """Network + CPU-bound work, no listing_sem here.

            See static_extractor for the rationale: semaphore acquire
            must be OUTSIDE wait_for to avoid the cancellation race
            that leaks slots (CPython gh-93999).

            Note `_get_html` still acquires `_listing_sem` internally
            for its httpx fetch step. That is by design: the inner
            acquire is short-lived and not wrapped by a wait_for that
            covers the acquire itself - the outer _bounded_process
            handles the budget.
            """
            html = await self._get_html(url, escalation_count)
            if not html:
                return None
            return await loop.run_in_executor(
                self._parse_pool,
                parse_and_build_listing,
                url, html, job,
            )

        async def _bounded_process(url: str) -> Optional[Listing]:
            """Per-listing wall-clock guard.

            wait_for wraps only the fetch + parse, never a semaphore
            acquire that would race on cancellation.
            """
            try:
                return await asyncio.wait_for(
                    _fetch_and_parse(url), timeout=listing_budget,
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

        async def _drain() -> None:
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

        try:
            try:
                await asyncio.wait_for(_drain(), timeout=gather_budget)
            except asyncio.TimeoutError:
                log.info(
                    "dynamic: %s gather budget exhausted after %.1fs, "
                    "keeping %d listings",
                    job.domain, gather_budget, len(results),
                )
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
            # Give cancelled tasks a bounded window to process the
            # CancelledError. Playwright's internal futures can hang
            # indefinitely after TargetClosedError, so we cap the
            # cleanup at 5s. Abandoned tasks' resources are reclaimed
            # by the browser pool's context-discard logic.
            try:
                await asyncio.wait_for(
                    asyncio.gather(*tasks, return_exceptions=True),
                    timeout=5.0,
                )
            except asyncio.TimeoutError:
                # Cleanup window expired before every task ack'd the
                # cancellation. Some Playwright futures complete after
                # this point with an unretrieved exception, producing
                # the `Future exception was never retrieved` warning.
                # Attach a callback that consumes the exception when
                # the future eventually settles, so the asyncio gc
                # warning does not fire.
                pending = [t for t in tasks if not t.done()]
                for task in pending:
                    task.add_done_callback(consume_orphan_exception)
                log.debug(
                    "dynamic: cleanup gather timed out for %s, "
                    "abandoning %d tasks",
                    job.domain, len(pending),
                )
        return results

    async def _get_html(
        self, url: str, escalation_count: list[int],
    ) -> str:
        """Try httpx first; escalate to Playwright only on hard blocks.

        Escalation is gated by a per-call budget counter so a domain
        whose httpx fetches all fail cannot monopolise the browser pool.
        Once _MAX_DETAIL_ESCALATION_BUDGET URLs have attempted Playwright,
        all further escalations are skipped immediately.

        escalation_count is a single-element list used as a mutable
        counter shared across all concurrent _get_html calls within
        one gather_listings invocation. List mutation is atomic on
        the single-threaded event loop.
        """
        async with self._listing_sem:
            outcome: FetchOutcome = await self._fetcher.fetch(url)
        if outcome.ok and outcome.is_html_like and outcome.text:
            return outcome.text
        if outcome.status is None or outcome.status in _BLOCK_STATUSES:
            if escalation_count[0] >= _MAX_DETAIL_ESCALATION_BUDGET:
                return ""
            escalation_count[0] += 1
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
        """Render the homepage in Playwright once.

        No retry. The fingerprint module already cached the homepage
        HTML before we got here, and `_discover_candidates` falls back
        to it whenever this returns empty. The previous two-attempt
        scheme paid up to one full nav_timeout per failed first
        attempt and at 12 concurrent dynamic domains was the dominant
        browser-pool queuing cost.
        """
        html, final_url = await self._safe_render(
            job.url, target_url=job.url,
            wait_for_idle=True, return_final_url=True,
        )
        if html:
            return html, final_url or job.url
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
        # Total budget = pool acquire (capped at browser_nav_timeout)
        # + nav (capped at browser_nav_timeout) + small overhead. 2x
        # leaves room for both phases. Anything longer is the symptom
        # we are guarding against.
        total_budget = self._settings.browser_nav_timeout * 2

        async def _do_render():
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
                    # Cheap settle for JS-redirect interstitials.
                    try:
                        await asyncio.sleep(_HOMEPAGE_SETTLE_SECONDS)
                    except asyncio.CancelledError:
                        raise
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

        try:
            return await asyncio.wait_for(_do_render(), timeout=total_budget)
        except asyncio.TimeoutError:
            log.debug(
                "dynamic render %s exceeded %.1fs total budget",
                url, total_budget,
            )
            return ("", "") if return_final_url else ""
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
