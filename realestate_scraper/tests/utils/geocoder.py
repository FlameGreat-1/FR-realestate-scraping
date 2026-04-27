from __future__ import annotations

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from scraper.utils.geocoder import AsyncGeocoder


class _ExplodingBackend:
    """Sentinel that fails the test if any geocode call escapes the cache."""

    def geocode(self, *_args, **_kwargs):  # pragma: no cover - must not run
        raise AssertionError("backend was called despite cache hit")


class _StubBackend:
    """Deterministic stand-in for geopy.Nominatim."""

    def __init__(self, results: dict[str, tuple[float, float] | None]) -> None:
        self._results = results
        self.calls: list[str] = []

    def geocode(self, location: str, *_args, **_kwargs):
        self.calls.append(location)
        coords = self._results.get(location.strip().lower())
        if coords is None:
            return None
        lat, lng = coords
        return SimpleNamespace(latitude=lat, longitude=lng)


def _build(
    cache_path: Path,
    backend,
    *,
    enabled: bool = True,
) -> AsyncGeocoder:
    geocoder = AsyncGeocoder(
        enabled=enabled,
        user_agent="test/1.0",
        timeout=1.0,
        cache_path=cache_path,
    )
    # Replace the geopy backend with our stub so the test does no
    # network I/O and is fully deterministic.
    geocoder._geocoder = backend  # noqa: SLF001 - test seam
    # The constructor zero-sleeps in tests via the stub returning
    # immediately; we just neutralise the citizenship sleep so the
    # suite stays fast.
    return geocoder


@pytest.mark.asyncio
async def test_geocoder_cache_load_returns_value_without_calling_backend(
    tmp_path: Path, monkeypatch,
):
    cache_path = tmp_path / ".geocode.json"
    cache_path.write_text(
        json.dumps({"bordeaux": "44.84, -0.58"}), encoding="utf-8",
    )
    geocoder = _build(cache_path, _ExplodingBackend())
    # No sleep (cache hit path does not reach the sleep branch).
    assert await geocoder.lookup("Bordeaux") == "44.84, -0.58"


async def _no_sleep(_delay):  # noqa: D401 - test seam
    """Drop-in replacement for `asyncio.sleep` that never blocks or recurses."""
    return None


@pytest.mark.asyncio
async def test_geocoder_cache_persists_new_entries_atomically(
    tmp_path: Path, monkeypatch,
):
    cache_path = tmp_path / ".geocode.json"
    backend = _StubBackend({"paris": (48.85, 2.35)})
    # Skip the 1-second Nominatim citizenship sleep in tests. We must
    # not delegate to `asyncio.sleep(0)` here: monkeypatch replaces the
    # `sleep` attribute on the shared `asyncio` module object, so any
    # call to `asyncio.sleep` from inside the stub recurses forever.
    monkeypatch.setattr(
        "scraper.utils.geocoder.asyncio.sleep", _no_sleep,
    )
    geocoder = _build(cache_path, backend)

    assert await geocoder.lookup("Paris") == "48.85, 2.35"
    # Persisted to disk.
    written = json.loads(cache_path.read_text(encoding="utf-8"))
    assert written == {"paris": "48.85, 2.35"}

    # Second instance against the same path: served from the persisted
    # cache, backend never invoked.
    second_backend = _ExplodingBackend()
    second = _build(cache_path, second_backend)
    assert await second.lookup("Paris") == "48.85, 2.35"


@pytest.mark.asyncio
async def test_geocoder_cache_tolerates_corrupt_file(tmp_path: Path):
    cache_path = tmp_path / ".geocode.json"
    cache_path.write_text("{ this is not json", encoding="utf-8")
    # Construction must not raise; in-memory cache must start empty.
    geocoder = _build(cache_path, _StubBackend({}))
    # Lookup with a backend miss returns "" without crashing.
    assert await geocoder.lookup("Nowhere-in-particular") == ""


@pytest.mark.asyncio
async def test_geocoder_cache_persists_misses(
    tmp_path: Path, monkeypatch,
):
    cache_path = tmp_path / ".geocode.json"
    backend = _StubBackend({})  # always returns None -> miss
    monkeypatch.setattr(
        "scraper.utils.geocoder.asyncio.sleep", _no_sleep,
    )
    geocoder = _build(cache_path, backend)

    assert await geocoder.lookup("Atlantis") == ""
    written = json.loads(cache_path.read_text(encoding="utf-8"))
    assert written == {"atlantis": ""}

    # A second geocoder against the same path must NOT re-query the
    # backend for a confirmed-empty location.
    second = _build(cache_path, _ExplodingBackend())
    assert await second.lookup("Atlantis") == ""
    assert backend.calls == ["Atlantis"]  # only the first ever called


@pytest.mark.asyncio
async def test_geocoder_disabled_never_touches_cache_path(tmp_path: Path):
    cache_path = tmp_path / ".geocode.json"
    geocoder = AsyncGeocoder(
        enabled=False,
        user_agent="test/1.0",
        timeout=1.0,
        cache_path=cache_path,
    )
    assert not geocoder.enabled
    assert await geocoder.lookup("Anywhere") == ""
    assert not cache_path.exists()
