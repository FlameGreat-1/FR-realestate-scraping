"""Stéphane Plaza Immobilier franchise family."""
from __future__ import annotations

from .base import Family, compile_patterns, get_registry

STEPHANE_PLAZA = Family(
    name="stephane_plaza",
    host_patterns=compile_patterns(
        r"stephaneplazaimmobilier\.com$",
        r"\.stephaneplazaimmobilier\.com$",
    ),
    html_markers=compile_patterns(
        r"stephane[\s_-]?plaza",
    ),
    listing_url_patterns=compile_patterns(
        r"/biens?/(?:vente|location)/[^/]+/[^/]+",
        r"/annonce[s]?/",
    ),
    requires_dynamic=True,
    selectors={
        "price": (".bien-prix", ".price", "[itemprop='price']"),
    },
)

get_registry().register(STEPHANE_PLAZA)
