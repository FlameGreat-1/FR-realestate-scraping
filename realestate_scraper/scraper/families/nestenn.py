"""Nestenn franchise family.

Nestenn agencies typically live on subdomains of `nestenn.com` (or use
local domains running the same template) and expose detail pages under
`...-ref-NNNNNNNN` slugs.
"""
from __future__ import annotations

from .base import Family, compile_patterns, get_registry

NESTENN = Family(
    name="nestenn",
    host_patterns=compile_patterns(
        r"\bnestenn\.com$",
        r"\.nestenn\.com$",
    ),
    html_markers=compile_patterns(
        r"nestenn",
    ),
    listing_url_patterns=compile_patterns(
        r"-ref-\d{6,}",
        r"/(?:vente|location)/.+-ref-\d+",
    ),
    selectors={
        "price": (".price", "[itemprop='price']", ".property-price"),
        "reference": (".reference", "[data-reference]"),
    },
)

get_registry().register(NESTENN)
