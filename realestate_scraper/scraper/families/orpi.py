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
    requires_dynamic=True,
)

get_registry().register(ORPI)
