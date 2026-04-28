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
    # Detail pages serve usable static HTML. Pipeline escalates to
    # dynamic on zero-listing static, so coverage is preserved.
    requires_dynamic=False,
    selectors={
        "price": (".bien-prix", ".price", "[itemprop='price']"),
    },
)

get_registry().register(STEPHANE_PLAZA)
