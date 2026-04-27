"""Async per-host concurrency limiter.

Limiting concurrent requests *per host* (not just globally) is what keeps
us polite and avoids self-inflicted 429s when many listings live on the
same agency website.
"""
from __future__ import annotations

import asyncio
from collections import defaultdict
from contextlib import asynccontextmanager
from typing import AsyncIterator

from .url import parse_host


class HostLimiter:
    """Bounded concurrency per remote host."""

    def __init__(self, per_host: int) -> None:
        if per_host < 1:
            raise ValueError("per_host must be >= 1")
        self._per_host = per_host
        self._semaphores: dict[str, asyncio.Semaphore] = defaultdict(
            lambda: asyncio.Semaphore(self._per_host)
        )
        self._lock = asyncio.Lock()

    async def _get(self, host: str) -> asyncio.Semaphore:
        async with self._lock:
            return self._semaphores[host]

    @asynccontextmanager
    async def slot(self, url: str) -> AsyncIterator[None]:
        host = parse_host(url) or "_default_"
        sem = await self._get(host)
        async with sem:
            yield
