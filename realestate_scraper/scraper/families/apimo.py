"""Apimo CMS family.

Apimo is a widely-used real estate CMS in France. Detail URLs typically
end in `/<slug>-<numeric_id>` and pages embed `apimo` in script paths
or data attributes.
"""
from __future__ import annotations

from .base import Family, compile_patterns, get_registry

APIMO = Family(
    name="apimo",
    host_patterns=(),
    html_markers=compile_patterns(
        r"apimo",
        r"data-apimo",
        r"/apimo/",
    ),
    listing_url_patterns=compile_patterns(
        r"/(?:vente|location)/[a-z0-9-]+-\d{4,}",
        r"/biens?/[a-z0-9-]+-\d{4,}",
    ),
    selectors={
        "price": (".bien-prix", "[itemprop='price']", ".property-price"),
        "reference": (".reference", "[data-reference]"),
    },
)

get_registry().register(APIMO)
