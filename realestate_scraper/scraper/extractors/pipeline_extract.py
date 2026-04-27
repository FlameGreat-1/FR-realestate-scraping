"""Resolver orchestration: HTML/URL -> Listing.

The orchestrator owns the resolver instances (stateless, so a single
instance per process is fine) and applies them in the order required to
fill a `Listing`. Each resolver runs independently; a failure to resolve
one field never prevents the others.
"""
from __future__ import annotations

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


def build_listing(ctx: PageContext) -> Listing:
    """Run every resolver on `ctx` and assemble a `Listing`."""
    job = ctx.domain_job
    listing = Listing(
        source_url=canonicalize(ctx.url) or ctx.url,
        source_domain=parse_registrable_domain(ctx.url) or (job.domain if job else ""),
        agency_name=(job.agency_name if job else ""),
    )

    listing.price = _PRICE.resolve(ctx).value
    listing.reference_id = _REFERENCE.resolve(ctx).value
    listing.property_type = _PROPERTY_TYPE.resolve(ctx).value
    listing.surface_area = _SURFACE.resolve(ctx).value
    listing.rooms = _ROOMS.resolve(ctx).value
    listing.bedrooms = _BEDROOMS.resolve(ctx).value
    listing.dpe_rating = _DPE.resolve(ctx).value
    listing.location = _LOCATION.resolve(ctx).value
    listing.coordinates = _COORDS.resolve(ctx).value
    listing.phone_number = _PHONE.resolve(ctx).value
    listing.email = _EMAIL.resolve(ctx).value
    listing.agent_name = _AGENT.resolve(ctx).value

    return listing
