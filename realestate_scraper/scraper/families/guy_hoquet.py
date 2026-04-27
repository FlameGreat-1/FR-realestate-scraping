"""Guy Hoquet franchise family."""
from __future__ import annotations

from .base import Family, compile_patterns, get_registry

GUY_HOQUET = Family(
    name="guy_hoquet",
    host_patterns=compile_patterns(
        r"guy-hoquet\.com$",
        r"\.guy-hoquet\.com$",
    ),
    html_markers=compile_patterns(
        r"guy[\s_-]?hoquet",
    ),
    listing_url_patterns=compile_patterns(
        r"/biens?/(?:vente|location)/",
        r"/annonce[s]?/",
    ),
    requires_dynamic=True,
)

get_registry().register(GUY_HOQUET)
