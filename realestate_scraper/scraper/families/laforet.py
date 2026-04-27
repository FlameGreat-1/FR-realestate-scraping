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
    requires_dynamic=True,
)

get_registry().register(LAFORET)
