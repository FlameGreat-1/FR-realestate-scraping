"""Shared async HTTP client with retry-aware fetch helpers.

A single `httpx.AsyncClient` is reused across the entire run for
connection pooling and HTTP/2 multiplexing. We never construct ad-hoc
clients deep inside the codebase: the pipeline owns the lifecycle, and
the rest of the system receives a `HttpFetcher` handle.

Anti-block layer:
    * Per-host User-Agent and client-hint headers are picked
      deterministically from a small curated pool (`headers.py`) so
      different domains get different fingerprints without breaking
      HTTP/2 reuse for any individual host.
    * On 403/429 the fetcher retries exactly once with a rotated
      profile before giving up; further fallback (Playwright) is
      handled higher up the stack.
"""
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import AsyncIterator, Mapping, Optional

import httpx

from .config import Settings
from .headers import (
    BrowserProfile,
    build_headers,
    profile_for_url,
    rotated_profile,
)
from .utils.ratelimit import HostLimiter
from .utils.retry import with_retry
from .utils.url import parse_host, probe_variants

log = logging.getLogger(__name__)


# Per-host fast-fail threshold: after this many consecutive
# 401/403/429 responses, every subsequent fetch on the same host
# returns immediately with a synthetic 403 outcome. Prevents the
# static path from spending the per-domain budget on a host that
# is hard-blocking httpx fetches. The dynamic extractor's Playwright
# escalation path is unaffected because it does not go through this
# fetcher for its detail render.
_HOST_BLOCK_THRESHOLD: int = 3


class _HostBlockTracker:
    """Tracks consecutive 401/403/429 per host.

    No locking: dict mutations are atomic on the single-threaded
    event loop. Counters reset on any successful response.
    """

    __slots__ = ("_counts",)

    def __init__(self) -> None:
        self._counts: dict[str, int] = {}

    def is_blocked(self, host: str) -> bool:
        return self._counts.get(host, 0) >= _HOST_BLOCK_THRESHOLD

    def record_block(self, host: str) -> None:
        self._counts[host] = self._counts.get(host, 0) + 1

    def record_ok(self, host: str) -> None:
        if host in self._counts:
            self._counts[host] = 0

_NON_HTML_PREFIXES = (
    "image/", "video/", "audio/", "font/", "application/pdf",
    "application/zip", "application/octet-stream",
)
_BLOCK_STATUSES: frozenset[int] = frozenset({401, 403, 429})
_DEFAULT_ACCEPT = (
    "text/html,application/xhtml+xml,application/xml;q=0.9,"
    "image/avif,image/webp,*/*;q=0.8"
)


@dataclass(slots=True)
class FetchOutcome:
    """Result of a single HTTP GET attempt."""

    url: str
    status: Optional[int]
    text: str
    final_url: str
    content_type: str
    error: Optional[BaseException] = None

    @property
    def ok(self) -> bool:
        return self.status is not None and 200 <= self.status < 400

    @property
    def is_html_like(self) -> bool:
        ct = (self.content_type or "").lower()
        if not ct:
            return bool(self.text)
        if any(ct.startswith(prefix) for prefix in _NON_HTML_PREFIXES):
            return False
        return (
            "html" in ct
            or "xml" in ct
            or "text/plain" in ct
            or ct.startswith("text/")
        )


@dataclass(slots=True)
class ProbeResult:
    """Reachability probe outcome across one or more URL variants."""

    status_code: Optional[int]
    final_url: str

    @property
    def reachable(self) -> bool:
        return self.status_code is not None


class HttpFetcher:
    """Thin facade around `httpx.AsyncClient` that adds limits and retries."""

    def __init__(
        self,
        client: httpx.AsyncClient,
        *,
        host_limiter: HostLimiter,
        max_retries: int,
        retry_backoff: float,
        probe_timeout: float,
        fetch_timeout: float,
        accept_language: str,
    ) -> None:
        self._client = client
        self._limiter = host_limiter
        self._max_retries = max_retries
        self._retry_backoff = retry_backoff
        self._probe_timeout = probe_timeout
        self._fetch_timeout = fetch_timeout
        self._accept_language = accept_language
        self._block_tracker = _HostBlockTracker()

    @property
    def client(self) -> httpx.AsyncClient:
        return self._client

    @property
    def probe_timeout(self) -> float:
        return self._probe_timeout

    def headers_for(
        self,
        url: str,
        *,
        attempt: int = 0,
    ) -> dict[str, str]:
        """Build the request headers for `url`.

        `attempt=0` returns the primary profile for the host;
        `attempt>=1` rotates to a different profile (used after a 403).
        """
        profile: BrowserProfile = (
            profile_for_url(url)
            if attempt <= 0
            else rotated_profile(url, attempt)
        )
        return build_headers(
            profile,
            accept=_DEFAULT_ACCEPT,
            accept_language=self._accept_language,
        )

    async def probe(self, url: str) -> ProbeResult:
        """Reachability probe with www/scheme variant fallback.

        All variants are probed concurrently; the first successful
        response wins. This reduces worst-case probe time from
        N * timeout to max(timeout) for unreachable hosts.
        """
        if not url:
            return ProbeResult(status_code=None, final_url=url)

        variants = probe_variants(url)
        if not variants:
            return ProbeResult(status_code=None, final_url=url)

        async def _try(candidate: str) -> tuple[str, Optional[int]]:
            status = await self._probe_single(candidate)
            return candidate, status

        tasks = [asyncio.create_task(_try(v)) for v in variants]
        try:
            for coro in asyncio.as_completed(tasks):
                candidate, status = await coro
                if status is not None:
                    return ProbeResult(status_code=status, final_url=candidate)
        finally:
            for task in tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
        return ProbeResult(status_code=None, final_url=url)

    async def _probe_single(self, url: str) -> Optional[int]:
        """Send one ranged GET probe to a specific URL.

        Many WAFs return 405 on HEAD but serve GET, so a HEAD-first
        scheme always paid the doubled round-trip cost on those hosts.
        We instead issue one GET with a 2 KB Range header, which is
        cheap on the wire (truncated body), still tells us whether the
        host answers, and keeps redirect/auth semantics intact.
        """
        headers = dict(self.headers_for(url))
        headers["Range"] = "bytes=0-2047"
        async with self._limiter.slot(url):
            try:
                response = await self._client.request(
                    "GET",
                    url,
                    timeout=self._probe_timeout,
                    headers=headers,
                )
                return response.status_code
            except httpx.HTTPError as exc:
                log.debug("probe GET %s failed: %s", url, exc)
                return None

    async def fetch(
        self,
        url: str,
        *,
        timeout: Optional[float] = None,
        retry_on_block: bool = True,  # kept for ABI; ignored
    ) -> FetchOutcome:
        """GET `url` once and update the per-host block tracker.

        Per-host fast-fail: once a host has produced
        _HOST_BLOCK_THRESHOLD consecutive non-OK responses (any of:
        401/403/429, network error, connect timeout, read timeout),
        every subsequent fetch on that host returns a synthetic 403
        without touching the network. Resets on any successful
        response.

        The previous per-fetch UA-rotation retry on 403/429 is
        removed: at threshold=3 it just doubled the wait per
        blocked URL (40 URLs * 10s * 2 attempts = 133s wasted on a
        fully-blocked host) without producing successes. The dynamic
        extractor's Playwright escalation path is the correct
        recovery for hard blocks; this fetcher's job is to fail
        fast and let the caller decide.
        """
        if not url:
            return FetchOutcome(
                url=url, status=None, text="",
                final_url=url, content_type="",
                error=ValueError("empty url"),
            )

        host = parse_host(url)
        if host and self._block_tracker.is_blocked(host):
            return FetchOutcome(
                url=url, status=403, text="",
                final_url=url, content_type="",
            )

        outcome = await self._fetch_with_headers(
            url,
            headers=self.headers_for(url),
            timeout=timeout,
        )

        if host:
            # Tracker increments ONLY on explicit hard blocks. Network
            # timeouts, non-HTML responses, 404s and 5xx are NOT block
            # signals - they are normal-traffic outcomes that real
            # detail-page lists produce in clusters of 3+ all the time
            # (stale sitemap URLs, PDF brochures, JSON micro-endpoints,
            # transient backend flap). Counting them as blocks (MR !25
            # original implementation) blacklisted working hosts
            # mid-run and broke previously-passing domains.
            if outcome.status in _BLOCK_STATUSES:
                self._block_tracker.record_block(host)
            elif outcome.ok:
                self._block_tracker.record_ok(host)
            # Any other outcome (network error, non-HTML, 404, 5xx)
            # leaves the counter untouched: not a confirmed block, not
            # a confirmed success.
        return outcome

    async def _fetch_with_headers(
        self,
        url: str,
        *,
        headers: Mapping[str, str],
        timeout: Optional[float],
    ) -> FetchOutcome:
        timeout_value = timeout or self._fetch_timeout

        async def _do() -> httpx.Response:
            async with self._limiter.slot(url):
                return await self._client.get(
                    url, timeout=timeout_value, headers=headers
                )

        try:
            response = await with_retry(
                _do,
                max_attempts=max(1, self._max_retries + 1),
                backoff=self._retry_backoff,
            )
        except BaseException as exc:  # noqa: BLE001
            log.debug("fetch %s failed: %s", url, exc)
            return FetchOutcome(
                url=url, status=None, text="",
                final_url=url, content_type="",
                error=exc,
            )

        ct = response.headers.get("content-type", "")
        text = ""
        if 200 <= response.status_code < 400:
            try:
                text = response.text
            except Exception as exc:  # noqa: BLE001
                log.debug("decoding %s failed: %s", url, exc)
                text = ""
        return FetchOutcome(
            url=url,
            status=response.status_code,
            text=text,
            final_url=str(response.url),
            content_type=ct,
        )


@asynccontextmanager
async def open_fetcher(settings: Settings) -> AsyncIterator[HttpFetcher]:
    """Context-managed `HttpFetcher` bound to a single `AsyncClient`."""
    limits = httpx.Limits(
        max_keepalive_connections=settings.domain_concurrency * 4,
        max_connections=settings.domain_concurrency * 8,
        # Short keepalive: idle connections from processed domains hold
        # pool slots that active domains need, AND a server-side-closed
        # idle connection that gets reused before httpx notices the
        # close raises read errors. 5s amortises TLS handshake within
        # one domain's listing burst without lingering across domains.
        keepalive_expiry=5.0,
    )
    timeout = httpx.Timeout(
        connect=min(settings.http_probe_timeout, 6.0),
        read=settings.http_fetch_timeout,
        write=settings.http_fetch_timeout,
        # Pool timeout is deliberately shorter than fetch timeout.
        # A request that cannot acquire a connection within 5s should
        # fail fast so the per-listing wall-clock guard can drop it
        # and move on, rather than blocking silently in the pool queue.
        pool=5.0,
    )
    # HTTP/2 is deliberately OFF.
    #
    # httpx + h2 + asymmetric server-side close (common on Cloudflare
    # and Imperva-fronted hosts in the input set) produces unrecoverable
    # hpack errors:
    #
    #   Invalid input ConnectionInputs.SEND_SETTINGS in state
    #   ConnectionState.CLOSED
    #
    # The error is per-connection but crashes the calling coroutine,
    # which - at high domain_concurrency - removes the entire domain
    # from the run. HTTP/1.1 with keepalive gives equivalent real-world
    # throughput at our concurrency (per_host=6, listing=24): the
    # multiplexing win is negligible at 6 concurrent requests per host,
    # and the dominant cost is TLS handshake, which keepalive already
    # amortises identically under H1.1.
    transport = httpx.AsyncHTTPTransport(
        retries=0,
        verify=settings.verify_tls,
        http2=False,
    )

    # The client itself does not hold the per-request UA: each call to
    # `fetch`/`probe` injects its own headers so we can rotate per host.
    # We still set a sane default header set for any internal httpx
    # request (e.g. redirect target lookups) that bypass our wrappers.
    async with httpx.AsyncClient(
        headers=settings.default_headers,
        follow_redirects=settings.follow_redirects,
        limits=limits,
        timeout=timeout,
        transport=transport,
        verify=settings.verify_tls,
        http2=False,
    ) as client:
        host_limiter = HostLimiter(settings.per_host_concurrency)
        fetcher = HttpFetcher(
            client,
            host_limiter=host_limiter,
            max_retries=settings.http_max_retries,
            retry_backoff=settings.http_retry_backoff,
            probe_timeout=settings.http_probe_timeout,
            fetch_timeout=settings.http_fetch_timeout,
            accept_language=settings.accept_language,
        )
        yield fetcher
