"""Laforet Immobilier family."""
from __future__ import annotations

from .base import Family, compile_patterns, get_registry

LAFORET = Family(
    name="laforet",
    host_patterns=compile_patterns(
        r"laforet\.com$",
        r"\.laforet\.com$",
    ),
    html_markers=compile_patterns(
        r"laforet",
    ),
    listing_url_patterns=compile_patterns(
        r"/(?:acheter|louer)/[^/]+/[^/]+",
        r"/annonce[s]?/",
    ),
    # Detail pages serve usable static HTML; only the search results
    # screen is JS-heavy. The pipeline still escalates to Playwright if
    # the static path returns zero listings, so we lose no coverage.
    requires_dynamic=False,
    agency_index_paths=("/agences-immobilieres/",),
)

get_registry().register(LAFORET)
