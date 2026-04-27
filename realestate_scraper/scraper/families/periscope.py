"""Périscope / Hektor / Périclès style CMSes.

These CMSes (Hektor by LaBoiteImmo, Périclès, Périscope) commonly use
lot/bien-style URLs with embedded numeric reference identifiers.
"""
from __future__ import annotations

from .base import Family, compile_patterns, get_registry

PERISCOPE = Family(
    name="hektor_pericles",
    host_patterns=(),
    html_markers=compile_patterns(
        r"hektor",
        r"laboiteimmo",
        r"pericles",
        r"periscope",
    ),
    listing_url_patterns=compile_patterns(
        r"/(?:lot|bien|annonce)s?/\d{3,}",
        r",[A-Z]{1,3}\d{3,}(?:[/?]|$)",
        r"-vp\d+",
        r"-vm\d+",
    ),
)

get_registry().register(PERISCOPE)
