"""Async, cached, opt-in geocoder.

Nominatim is rate-limited to 1 req/s by policy, so we serialize calls
through a lock and cache aggressively. The cache is persisted to disk
so that re-runs of the pipeline do not re-issue the same queries -
critical at 55k+ scale where the lookup time would otherwise dominate
any rerun.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Optional

from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeopyError

log = logging.getLogger(__name__)


class AsyncGeocoder:
    """Thin async wrapper over geopy with persistent on-disk caching."""

    def __init__(
        self,
        *,
        enabled: bool,
        user_agent: str,
        timeout: float,
        cache_path: Optional[Path] = None,
    ) -> None:
        self._enabled = enabled
        self._timeout = timeout
        self._cache_path = cache_path
        self._cache: dict[str, str] = {}
        self._lock = asyncio.Lock()
        self._geocoder: Optional[Nominatim] = (
            Nominatim(user_agent=user_agent, timeout=timeout) if enabled else None
        )
        if self._enabled and self._cache_path is not None:
            self._load_cache()

    @property
    def enabled(self) -> bool:
        return self._enabled and self._geocoder is not None

    def _load_cache(self) -> None:
        path = self._cache_path
        if path is None or not path.exists():
            return
        try:
            raw = path.read_text(encoding="utf-8")
            data = json.loads(raw) if raw.strip() else {}
        except (OSError, json.JSONDecodeError) as exc:
            log.debug("geocode cache unreadable at %s: %s", path, exc)
            return
        if isinstance(data, dict):
            # Coerce values to str so a stray non-string never crashes us.
            self._cache = {
                str(key).lower(): str(value)
                for key, value in data.items()
                if isinstance(key, str)
            }

    def _persist_cache_locked(self) -> None:
        """Atomic-rewrite the cache file. Caller must hold `self._lock`."""
        path = self._cache_path
        if path is None:
            return
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                "w",
                encoding="utf-8",
                dir=str(path.parent),
                prefix=path.name + ".",
                suffix=".tmp",
                delete=False,
            ) as tmp:
                json.dump(self._cache, tmp, ensure_ascii=False)
                tmp_path = Path(tmp.name)
            os.replace(tmp_path, path)
        except OSError as exc:
            log.debug("geocode cache write failed at %s: %s", path, exc)

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
                self._persist_cache_locked()
                return ""
            except Exception as exc:  # noqa: BLE001
                log.debug("geocode error for %r: %s", location, exc)
                self._cache[key] = ""
                self._persist_cache_locked()
                return ""
            value = (
                f"{result.latitude}, {result.longitude}" if result else ""
            )
            self._cache[key] = value
            self._persist_cache_locked()
            # Be a good Nominatim citizen: 1 req/s.
            await asyncio.sleep(1.0)
            return value
