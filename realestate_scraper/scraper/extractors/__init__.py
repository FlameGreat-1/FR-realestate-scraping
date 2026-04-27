"""Extractors translate fetched HTML into `Listing` objects.

* `pipeline_extract` runs all field resolvers on a single page.
* `static_extractor` performs HTTPX-driven multi-page extraction.
* `dynamic_extractor` performs Playwright-driven extraction.
"""
from __future__ import annotations

from .pipeline_extract import build_listing, parse_page
from .static_extractor import StaticExtractor

__all__ = ["StaticExtractor", "build_listing", "parse_page"]
