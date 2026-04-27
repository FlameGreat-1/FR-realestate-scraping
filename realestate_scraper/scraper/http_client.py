"""Shared async HTTP client with retry-aware fetch helpers.

A single `httpx.AsyncClient` is reused across the entire run for
connection pooling and HTTP/2 multiplexing. We never construct ad-hoc
clients deep inside the codebase: the pipeline owns the lifecycle, and
the rest of the system receives a `HttpFetcher` handle.
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import AsyncIterator, Optional

import httpx

from .config import Settings
from .utils.ratelimit import HostLimiter
from .utils.retry import with_retry

log = logging.getLogger(__name__)

_NON_HTML_PREFIXES = (
    "image/", "video/", "audio/", "font/", "application/pdf",
    "application/zip", "application/octet-stream",
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
    ) -> None:
        self._client = client
        self._limiter = host_limiter
        self._max_retries = max_retries
        self._retry_backoff = retry_backoff
        self._probe_timeout = probe_timeout
        self._fetch_timeout = fetch_timeout

    @property
    def client(self) -> httpx.AsyncClient:
        return self._client

    async def probe(self, url: str) -> Optional[int]:
        """Cheap reachability probe: try HEAD, fall back to GET."""
        if not url:
            return None
        async with self._limiter.slot(url):
            for method in ("HEAD", "GET"):
                try:
                    response = await self._client.request(
                        method, url, timeout=self._probe_timeout
                    )
                    return response.status_code
                except httpx.HTTPError as exc:
                    log.debug("probe %s %s failed: %s", method, url, exc)
                    continue
        return None

    async def fetch(
        self,
        url: str,
        *,
        timeout: Optional[float] = None,
    ) -> FetchOutcome:
        if not url:
            return FetchOutcome(
                url=url, status=None, text="",
                final_url=url, content_type="",
                error=ValueError("empty url"),
            )

        timeout_value = timeout or self._fetch_timeout

        async def _do() -> httpx.Response:
            async with self._limiter.slot(url):
                return await self._client.get(url, timeout=timeout_value)

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
        keepalive_expiry=30.0,
    )
    timeout = httpx.Timeout(
        connect=min(settings.http_probe_timeout, 8.0),
        read=settings.http_fetch_timeout,
        write=settings.http_fetch_timeout,
        pool=settings.http_fetch_timeout,
    )
    transport = httpx.AsyncHTTPTransport(
        retries=0,
        verify=settings.verify_tls,
        http2=True,
    )

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
        )
        yield fetcher
