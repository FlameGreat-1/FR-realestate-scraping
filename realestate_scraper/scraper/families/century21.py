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
    # Detail pages serve usable static HTML; only search results
    # require JS. Pipeline escalates to dynamic on zero-listing static.
    requires_dynamic=False,
    agency_index_paths=("/agences/",),
)

get_registry().register(CENTURY21)
