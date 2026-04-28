"""Orpi family."""
from __future__ import annotations

from .base import Family, compile_patterns, get_registry

ORPI = Family(
    name="orpi",
    host_patterns=compile_patterns(
        r"orpi\.com$",
        r"\.orpi\.com$",
    ),
    html_markers=compile_patterns(
        r"\borpi\b",
    ),
    listing_url_patterns=compile_patterns(
        r"/annonce[s]?-(?:vente|location)/",
        r"/biens-(?:vente|location)/",
    ),
    # Detail pages serve usable static HTML. Pipeline escalates to
    # dynamic on zero-listing static, so coverage is preserved.
    requires_dynamic=False,
    agency_index_paths=("/agences/",),
)

get_registry().register(ORPI)
