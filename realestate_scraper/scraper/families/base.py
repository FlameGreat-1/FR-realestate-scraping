"""Family abstraction and global registry.

A `Family` provides:
    * `matches(html, url, headers)` - cheap fingerprint detection.
    * `listing_url_hints` - regex patterns that boost classifier scores.
    * `selectors` - optional CSS selectors used by the static extractor.

Families never *replace* the generic resolvers; they only *augment*
them. This way an unknown CMS still works, just without the family
bonus.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable, Mapping, Optional, Pattern


@dataclass(slots=True)
class FamilySignals:
    """Inputs available to family detectors at classification time."""

    url: str
    host: str
    html_head: str
    headers: Mapping[str, str]


@dataclass(slots=True)
class Family:
    """A reusable real-estate website family (CMS or franchise)."""

    name: str
    host_patterns: tuple[Pattern[str], ...] = field(default_factory=tuple)
    html_markers: tuple[Pattern[str], ...] = field(default_factory=tuple)
    listing_url_patterns: tuple[Pattern[str], ...] = field(default_factory=tuple)
    requires_dynamic: bool = False
    selectors: Mapping[str, tuple[str, ...]] = field(default_factory=dict)

    def matches(self, signals: FamilySignals) -> bool:
        for pattern in self.host_patterns:
            if pattern.search(signals.host):
                return True
        if signals.html_head:
            for pattern in self.html_markers:
                if pattern.search(signals.html_head):
                    return True
        return False

    def boost_url(self, url: str) -> int:
        if not self.listing_url_patterns or not url:
            return 0
        for pattern in self.listing_url_patterns:
            if pattern.search(url):
                return 3
        return 0


class FamilyRegistry:
    """Process-wide registry of `Family` instances."""

    def __init__(self) -> None:
        self._families: list[Family] = []

    def register(self, family: Family) -> Family:
        self._families.append(family)
        return family

    def all(self) -> tuple[Family, ...]:
        return tuple(self._families)

    def detect(self, signals: FamilySignals) -> Optional[Family]:
        for family in self._families:
            if family.matches(signals):
                return family
        return None

    def detect_many(self, signals: FamilySignals) -> tuple[Family, ...]:
        return tuple(f for f in self._families if f.matches(signals))

    def boost_url(self, url: str, only: Iterable[Family] | None = None) -> int:
        families = tuple(only) if only is not None else self._families
        if not families or not url:
            return 0
        best = 0
        for family in families:
            best = max(best, family.boost_url(url))
        return best


_REGISTRY: FamilyRegistry | None = None


def get_registry() -> FamilyRegistry:
    """Return the lazily-initialised global registry.

    The actual `Family` instances are registered by the family modules
    themselves at import time; importing `scraper.families` triggers the
    side-effect cascade.
    """
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = FamilyRegistry()
        _bootstrap(_REGISTRY)
    return _REGISTRY


def compile_patterns(*sources: str) -> tuple[Pattern[str], ...]:
    """Compile a tuple of regex strings with case-insensitive matching."""
    return tuple(re.compile(src, re.IGNORECASE) for src in sources)


def _bootstrap(registry: FamilyRegistry) -> None:
    # Imports are deferred to avoid circular references; each module
    # registers itself via `registry.register(...)`.
    from . import nestenn  # noqa: F401
    from . import stephane_plaza  # noqa: F401
    from . import guy_hoquet  # noqa: F401
    from . import laforet  # noqa: F401
    from . import era  # noqa: F401
    from . import century21  # noqa: F401
    from . import orpi  # noqa: F401
    from . import apimo  # noqa: F401
    from . import periscope  # noqa: F401
