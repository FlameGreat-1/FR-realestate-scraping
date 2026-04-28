"""Domain models used across the scraper.

The `Listing` field set is the contract mandated by the test brief and
must be preserved exactly: any change here ripples through CSV headers,
resolvers, and tests.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Optional

from .error_codes import ErrorReason


# Exact column order required for the listings CSV output.
LISTING_FIELDS: tuple[str, ...] = (
    "reference_id",
    "price",
    "property_type",
    "location",
    "surface_area",
    "rooms",
    "bedrooms",
    "agency_name",
    "agent_name",
    "phone_number",
    "email",
    "coordinates",
    "dpe_rating",
    "source_url",
    "source_domain",
)

ERROR_FIELDS: tuple[str, ...] = ("domain", "status", "reason")

DOMAIN_SUMMARY_FIELDS: tuple[str, ...] = (
    "domain",
    "status",
    "listing_count",
    "reason",
    "strategy",
    "duration_seconds",
)


class DomainStatus(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


class Strategy(str, Enum):
    STATIC = "static"
    DYNAMIC = "dynamic"
    HYBRID = "hybrid"
    NONE = "none"


@dataclass(slots=True)
class DomainJob:
    """One unit of work: a single deduplicated agency website."""

    domain: str
    url: str
    agency_name: str = ""
    agent_name: str = ""
    phone: str = ""
    city: str = ""
    postalcode: str = ""
    rows_merged: int = 1


@dataclass(slots=True)
class Listing:
    """A single property listing - exact field set from the brief."""

    reference_id: str = ""
    price: str = ""
    property_type: str = ""
    location: str = ""
    surface_area: str = ""
    rooms: str = ""
    bedrooms: str = ""
    agency_name: str = ""
    agent_name: str = ""
    phone_number: str = ""
    email: str = ""
    coordinates: str = ""
    dpe_rating: str = ""
    source_url: str = ""
    source_domain: str = ""

    def to_row(self) -> dict[str, Any]:
        return asdict(self)

    def is_publishable(self) -> bool:
        """A listing qualifies when it carries enough listing-shaped signal.

        All three conditions must hold:
            1. At least two of the six informative fields are filled.
            2. EITHER price or reference_id is filled (the two strong
               anchors that hub / template pages cannot fake), OR
               surface_area AND at least one of
               {rooms, location, property_type} are filled.
            3. Trivially-empty informative fields are not counted in
               the filled tally (whitespace-only values are treated
               as absent).

        Informative fields are the six the brief uses to describe a
        property:

            price, location, surface_area, rooms, reference_id, property_type

        Agency/agent metadata is intentionally excluded because it
        propagates from the input CSV and would otherwise let any
        parsed page through.

        Why surface_area alone is not enough: agency listing-index /
        pagination templates render the most recent listing's surface
        on the index page itself. A page that only produces
        surface_area is therefore likely an index ghost, not a real
        detail page. Requiring a companion descriptive field rejects
        the ghost while preserving every real detail page (real
        listings always set surface + at least one of rooms /
        location / property_type).
        """
        def _set(value: str) -> bool:
            return bool((value or "").strip())

        informative = (
            self.price, self.location, self.surface_area,
            self.rooms, self.reference_id, self.property_type,
        )
        if sum(1 for v in informative if _set(v)) < 2:
            return False

        # Strong anchors: price or reference_id alone is sufficient.
        if _set(self.price) or _set(self.reference_id):
            return True

        # Surface-as-anchor only when paired with another descriptor.
        if _set(self.surface_area) and any(
            _set(v) for v in (self.rooms, self.location, self.property_type)
        ):
            return True

        return False


@dataclass(slots=True)
class ErrorRecord:
    domain: str
    status: str
    reason: ErrorReason

    def to_row(self) -> dict[str, str]:
        return {
            "domain": self.domain,
            "status": self.status,
            "reason": self.reason.value,
        }


@dataclass(slots=True)
class DomainResult:
    """Outcome of processing one domain - feeds the summary CSV."""

    domain: str
    status: DomainStatus
    listing_count: int = 0
    reason: Optional[ErrorReason] = None
    strategy: Strategy = Strategy.NONE
    duration_seconds: float = 0.0

    def to_row(self) -> dict[str, Any]:
        return {
            "domain": self.domain,
            "status": self.status.value,
            "listing_count": self.listing_count,
            "reason": self.reason.value if self.reason else "",
            "strategy": self.strategy.value,
            "duration_seconds": f"{self.duration_seconds:.2f}",
        }


@dataclass(slots=True)
class ResolverResult:
    """Output of a single field resolver: value + confidence (0..1)."""

    value: str = ""
    confidence: float = 0.0
    source: str = ""

    @property
    def has_value(self) -> bool:
        return bool((self.value or "").strip())


@dataclass(slots=True)
class PageContext:
    """Everything a resolver needs about a single fetched page."""

    url: str
    html: str
    text: str = ""
    title: str = ""
    h1: str = ""
    json_ld: dict[str, Any] = field(default_factory=dict)
    domain_job: Optional[DomainJob] = None
