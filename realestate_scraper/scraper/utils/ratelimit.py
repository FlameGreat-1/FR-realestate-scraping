"""Async per-host concurrency limiter.

Limiting concurrent requests *per host* (not just globally) is what keeps
us polite and avoids self-inflicted 429s when many listings live on the
same agency website.

The limiter is on the hot path of every HTTP request, so it is
deliberately lock-free: `asyncio.Semaphore` construction is cheap and
the event loop is cooperative, so `dict.setdefault` is enough to give
us race-free lazy initialisation per host.
"""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncIterator

from .url import parse_host

_DEFAULT_HOST = "_default_"


class HostLimiter:
    """Bounded concurrency per remote host.

    Designed for 55k+ unique hosts: the per-host semaphore map grows
    monotonically, but each entry is tiny and the lookup is O(1) with
    no global synchronisation.
    """

    __slots__ = ("_per_host", "_semaphores")

    def __init__(self, per_host: int) -> None:
        if per_host < 1:
            raise ValueError("per_host must be >= 1")
        self._per_host = per_host
        self._semaphores: dict[str, asyncio.Semaphore] = {}

    @property
    def per_host(self) -> int:
        return self._per_host

    def _semaphore_for(self, host: str) -> asyncio.Semaphore:
        sem = self._semaphores.get(host)
        if sem is not None:
            return sem
        # `setdefault` is atomic on the single-threaded event loop, so the
        # first coroutine wins and any concurrent caller reuses its result.
        return self._semaphores.setdefault(
            host, asyncio.Semaphore(self._per_host)
        )

    @asynccontextmanager
    async def slot(self, url: str) -> AsyncIterator[None]:
        host = parse_host(url) or _DEFAULT_HOST
        sem = self._semaphore_for(host)
        async with sem:
            yield
