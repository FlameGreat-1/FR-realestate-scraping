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
from .utils.url import probe_variants

log = logging.getLogger(__name__)

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
        retry_on_block: bool = True,
    ) -> FetchOutcome:
        """GET `url` with transient-error retries and optional UA rotation.

        On a 401/403/429 response we retry exactly once with a rotated
        UA profile before returning the (still-blocked) outcome. The
        higher-level pipeline decides whether to escalate to dynamic
        rendering after that.
        """
        if not url:
            return FetchOutcome(
                url=url, status=None, text="",
                final_url=url, content_type="",
                error=ValueError("empty url"),
            )

        outcome = await self._fetch_with_headers(
            url,
            headers=self.headers_for(url),
            timeout=timeout,
        )
        if (
            retry_on_block
            and outcome.status in _BLOCK_STATUSES
        ):
            rotated = self.headers_for(url, attempt=1)
            retried = await self._fetch_with_headers(
                url,
                headers=rotated,
                timeout=timeout,
            )
            # Prefer the retry only if it produced a usable response;
            # otherwise return the original block so the pipeline still
            # classifies it correctly.
            if retried.ok:
                return retried
            if (
                retried.status is not None
                and retried.status not in _BLOCK_STATUSES
            ):
                return retried
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
        # Shorter keepalive: idle connections from processed domains
        # hold pool slots that active domains need. At scale, 30s
        # keepalive on hundreds of hosts wastes connection capacity.
        keepalive_expiry=15.0,
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
    transport = httpx.AsyncHTTPTransport(
        retries=0,
        verify=settings.verify_tls,
        http2=True,
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
        http2=True,
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
