"""Async retry helpers backed by tenacity.

Retries are reserved for *transient* network/HTTP-5xx failures. We never
retry 4xx (client error), 403 (block), or our own application errors.
"""
from __future__ import annotations

from typing import Awaitable, Callable, TypeVar

import httpx
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

T = TypeVar("T")

_RETRYABLE_EXC = (
    httpx.ConnectError,
    httpx.ConnectTimeout,
    httpx.ReadTimeout,
    httpx.WriteTimeout,
    httpx.RemoteProtocolError,
    httpx.PoolTimeout,
)


async def with_retry(
    coro_factory: Callable[[], Awaitable[T]],
    *,
    max_attempts: int,
    backoff: float,
) -> T:
    """Run an async-callable with exponential backoff on transient failures."""
    if max_attempts <= 1:
        return await coro_factory()
    async for attempt in AsyncRetrying(
        reraise=True,
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(multiplier=backoff, min=backoff, max=backoff * 8),
        retry=retry_if_exception_type(_RETRYABLE_EXC),
    ):
        with attempt:
            return await coro_factory()
    raise RuntimeError("unreachable")  # pragma: no cover
