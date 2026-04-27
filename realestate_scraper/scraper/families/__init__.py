"""CMS / agency-network family rules.

A family encodes the listing-URL conventions and selector hints that are
shared by *many* agency websites running the same template (e.g. all
Nestenn or Stéphane Plaza branches). One file per family keeps things
linear and reviewable.
"""
from __future__ import annotations

from .base import Family, FamilyRegistry, get_registry

__all__ = ["Family", "FamilyRegistry", "get_registry"]
