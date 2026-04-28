"""Resolver orchestration: HTML/URL -> Listing.

The orchestrator owns the resolver instances (stateless, so a single
instance per process is fine) and applies them in the order required to
fill a `Listing`. Each resolver runs independently; a failure to resolve
one field never prevents the others (see `_safe_resolve`).
"""
from __future__ import annotations

import logging

from selectolax.parser import HTMLParser

from ..models import DomainJob, Listing, PageContext
from ..resolvers.agent_name import AgentNameResolver
from ..resolvers.bedrooms import BedroomsResolver
from ..resolvers.coordinates import CoordinatesResolver
from ..resolvers.dpe import DpeResolver
from ..resolvers.email import EmailResolver
from ..resolvers.location import LocationResolver
from ..resolvers.phone import PhoneResolver
from ..resolvers.price import PriceResolver
from ..resolvers.property_type import PropertyTypeResolver
from ..resolvers.reference import ReferenceResolver
from ..resolvers.rooms import RoomsResolver
from ..resolvers.surface import SurfaceResolver
from ..utils.json_ld import extract_json_ld
from ..utils.text import collapse_whitespace
from ..utils.url import canonicalize, parse_registrable_domain

log = logging.getLogger(__name__)


_PRICE = PriceResolver()
_REFERENCE = ReferenceResolver()
_PROPERTY_TYPE = PropertyTypeResolver()
_SURFACE = SurfaceResolver()
_ROOMS = RoomsResolver()
_BEDROOMS = BedroomsResolver()
_DPE = DpeResolver()
_LOCATION = LocationResolver()
_COORDS = CoordinatesResolver()
_PHONE = PhoneResolver()
_EMAIL = EmailResolver()
_AGENT = AgentNameResolver()


def parse_page(
    url: str,
    html: str,
    domain_job: DomainJob | None = None,
) -> PageContext:
    """Build a `PageContext` from raw HTML."""
    if not html:
        return PageContext(
            url=url,
            html="",
            text="",
            title="",
            h1="",
            json_ld={},
            domain_job=domain_job,
        )
    try:
        parser = HTMLParser(html)
    except Exception:
        parser = None

    title = ""
    h1 = ""
    if parser is not None:
        title_node = parser.css_first("title")
        if title_node:
            title = collapse_whitespace(
                title_node.text(deep=True, separator=" ", strip=True)
            )
        h1_node = parser.css_first("h1")
        if h1_node:
            h1 = collapse_whitespace(
                h1_node.text(deep=True, separator=" ", strip=True)
            )
        text = collapse_whitespace(
            parser.body.text(deep=True, separator=" ", strip=True)
            if parser.body else ""
        )
    else:
        text = ""

    return PageContext(
        url=url,
        html=html,
        text=text,
        title=title,
        h1=h1,
        json_ld=extract_json_ld(html),
        domain_job=domain_job,
    )


def _safe_resolve(resolver, ctx: PageContext) -> str:
    """Run `resolver.resolve(ctx)` and return its value, or empty on crash.

    Resolvers are pure-CPU Python code, but real-world HTML can drive
    any of them into pathological behaviour (regex backtracking,
    selectolax tree walks on malformed DOM, KeyError on missing
    JSON-LD shapes, ...). A resolver crash MUST NOT take down the
    entire listing - the other 11 fields are independent and useful
    on their own.

    Catches `Exception` (not BaseException) so KeyboardInterrupt /
    SystemExit / asyncio.CancelledError still propagate normally.
    """
    try:
        return resolver.resolve(ctx).value
    except Exception as exc:  # noqa: BLE001
        log.debug(
            "resolver %s crashed on %s: %s",
            getattr(resolver, "name", resolver.__class__.__name__),
            ctx.url, exc,
        )
        return ""


def build_listing(ctx: PageContext) -> Listing:
    """Run every resolver on `ctx` and assemble a `Listing`.

    Each resolver runs through `_safe_resolve` so that a crash in one
    field never aborts assembly of the others. The publishability
    rule on the result still decides whether the listing is emitted.
    """
    job = ctx.domain_job
    listing = Listing(
        source_url=canonicalize(ctx.url) or ctx.url,
        source_domain=parse_registrable_domain(ctx.url) or (job.domain if job else ""),
        agency_name=(job.agency_name if job else ""),
    )

    listing.price = _safe_resolve(_PRICE, ctx)
    listing.reference_id = _safe_resolve(_REFERENCE, ctx)
    listing.property_type = _safe_resolve(_PROPERTY_TYPE, ctx)
    listing.surface_area = _safe_resolve(_SURFACE, ctx)
    listing.rooms = _safe_resolve(_ROOMS, ctx)
    listing.bedrooms = _safe_resolve(_BEDROOMS, ctx)
    listing.dpe_rating = _safe_resolve(_DPE, ctx)
    listing.location = _safe_resolve(_LOCATION, ctx)
    listing.coordinates = _safe_resolve(_COORDS, ctx)
    listing.phone_number = _safe_resolve(_PHONE, ctx)
    listing.email = _safe_resolve(_EMAIL, ctx)
    listing.agent_name = _safe_resolve(_AGENT, ctx)

    return listing
