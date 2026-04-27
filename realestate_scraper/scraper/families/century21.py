"""Century 21 family."""
from __future__ import annotations

from .base import Family, compile_patterns, get_registry

CENTURY21 = Family(
    name="century21",
    host_patterns=compile_patterns(
        r"century21\.fr$",
        r"\.century21\.fr$",
    ),
    html_markers=compile_patterns(
        r"century\s*21",
    ),
    listing_url_patterns=compile_patterns(
        r"/trouver_logement/",
        r"/annonce[s]?/detail/",
        r"-fp\d{4,}",
    ),
    requires_dynamic=True,
)

get_registry().register(CENTURY21)
