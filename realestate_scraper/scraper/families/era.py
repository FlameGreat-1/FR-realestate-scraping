"""ERA Immobilier family."""
from __future__ import annotations

from .base import Family, compile_patterns, get_registry

ERA = Family(
    name="era",
    host_patterns=compile_patterns(
        r"erafrance\.com$",
        r"\.erafrance\.com$",
        r"era[a-z0-9-]+\.(?:com|fr)$",
    ),
    html_markers=compile_patterns(
        r"era\s+immobilier",
        r"era[\s-]?france",
    ),
    listing_url_patterns=compile_patterns(
        r"/acheter/",
        r"/annonce[s]?/",
        r"-ref-?\d{4,}",
    ),
)

get_registry().register(ERA)
