"""Async, cached, opt-in geocoder.

Nominatim is rate-limited to 1 req/s by policy, so we serialize calls
through a lock and cache aggressively. The original implementation
called it synchronously inside the async pipeline, blocking the loop.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Optional

from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeopyError

log = logging.getLogger(__name__)


class AsyncGeocoder:
    """Thin async wrapper over geopy with on-process caching."""

    def __init__(
        self,
        *,
        enabled: bool,
        user_agent: str,
        timeout: float,
    ) -> None:
        self._enabled = enabled
        self._timeout = timeout
        self._cache: dict[str, str] = {}
        self._lock = asyncio.Lock()
        self._geocoder: Optional[Nominatim] = (
            Nominatim(user_agent=user_agent, timeout=timeout) if enabled else None
        )

    @property
    def enabled(self) -> bool:
        return self._enabled and self._geocoder is not None

    async def lookup(self, location: str) -> str:
        if not self.enabled or not location or len(location) < 3:
            return ""
        key = location.strip().lower()
        if key in self._cache:
            return self._cache[key]
        async with self._lock:
            if key in self._cache:
                return self._cache[key]
            try:
                result = await asyncio.to_thread(
                    self._geocoder.geocode, location, timeout=self._timeout
                )
            except (GeocoderTimedOut, GeopyError) as exc:
                log.debug("geocode failed for %r: %s", location, exc)
                self._cache[key] = ""
                return ""
            except Exception as exc:  # noqa: BLE001
                log.debug("geocode error for %r: %s", location, exc)
                self._cache[key] = ""
                return ""
            value = (
                f"{result.latitude}, {result.longitude}" if result else ""
            )
            self._cache[key] = value
            # Be a good Nominatim citizen: 1 req/s.
            await asyncio.sleep(1.0)
            return value
