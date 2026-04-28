"""Resolver orchestration: HTML/URL -> Listing.

The orchestrator owns the resolver instances (stateless, so a single
instance per process is fine) and applies them in the order required to
fill a `Listing`. Each resolver runs independently; a failure to resolve
one field never prevents the others (see `_safe_resolve`).
"""
from __future__ import annotations

import logging
import signal
import threading
from contextlib import contextmanager
from typing import Iterator, Optional

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


class _ParseTimeout(Exception):
    """Raised by the SIGALRM handler when synchronous parse work
    exceeds its wall-clock budget.

    Caught inside `parse_and_build_listing` and translated into a
    `None` return value, which the extractors already treat as a
    dropped listing. Never propagates to the caller.
    """


@contextmanager
def _parse_time_guard(budget: Optional[float]) -> Iterator[None]:
    """Bound synchronous parse work to `budget` seconds when possible.

    SIGALRM is the only mechanism that can interrupt CPython code
    mid-execution (regex backtracking, selectolax C extension work),
    but Python only delivers signals on the main thread. When this
    runs in a parse-pool worker (the hot path) the guard is a no-op,
    and we rely on the regex shape fixes plus the per-listing
    asyncio.wait_for in the extractors.

    When called from the main thread (tests, ad-hoc scripts) the
    guard is armed: a SIGALRM after `budget` seconds raises
    `_ParseTimeout`, which `parse_and_build_listing` catches and
    converts into a dropped listing.

    Always yields - never blocks the caller. The handler and any
    pending alarm are cleared in a finally block, so a guard armed
    on one call cannot leak into the next.
    """
    if (
        budget is None
        or budget <= 0
        or threading.current_thread() is not threading.main_thread()
        or not hasattr(signal, "SIGALRM")
    ):
        yield
        return

    def _handler(signum, frame):  # type: ignore[no-untyped-def]
        raise _ParseTimeout("parse budget exceeded")

    # signal.setitimer accepts sub-second resolution; signal.alarm only
    # accepts whole seconds. Prefer setitimer when available so a 1.5s
    # budget is honoured precisely.
    previous = signal.signal(signal.SIGALRM, _handler)
    use_itimer = hasattr(signal, "setitimer")
    try:
        if use_itimer:
            signal.setitimer(signal.ITIMER_REAL, budget)
        else:
            # Round up so we never under-cap the budget.
            signal.alarm(max(1, int(budget + 0.999)))
        yield
    finally:
        if use_itimer:
            signal.setitimer(signal.ITIMER_REAL, 0)
        else:
            signal.alarm(0)
        signal.signal(signal.SIGALRM, previous)


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


def parse_and_build_listing(
    url: str,
    html: str,
    domain_job: DomainJob | None = None,
    *,
    time_budget: Optional[float] = None,
) -> Listing | None:
    """Synchronous combined entry point for parse + build_listing.

    Returns the Listing when publishable, None otherwise. Designed to
    be invoked through `asyncio.to_thread` / `run_in_executor` so the
    synchronous selectolax / regex / resolver work runs OFF the event
    loop. Running this work on the loop directly is the architectural
    defect that froze the pipeline up through Round 8 - the selectolax
    C extension and regex engine do not yield to asyncio, so per-
    listing wall-clock guards (asyncio.wait_for) cannot interrupt them.

    `time_budget`: optional wall-clock cap, in seconds, for the
    synchronous work. When the call runs on the main thread and
    SIGALRM is available (POSIX), exceeding the budget raises
    `_ParseTimeout` internally and the function returns None. On
    parse-pool worker threads the guard is a no-op (signals are
    main-thread only); the regex-shape fixes are the primary defence
    on that path, with the asyncio.wait_for in the extractors as the
    structural cancellation boundary.

    Why a combined helper rather than two to_thread calls:
        * Each to_thread round-trip costs an executor handoff.
        * Crashes inside parse_page (selectolax raising on malformed
          HTML) are contained the same way resolver crashes are.
    """
    try:
        with _parse_time_guard(time_budget):
            ctx = parse_page(url, html, domain_job=domain_job)
            listing = build_listing(ctx)
    except _ParseTimeout:
        log.debug("parse_and_build_listing time budget exceeded for %s", url)
        return None
    except Exception as exc:  # noqa: BLE001
        log.debug("parse_and_build_listing failed for %s: %s", url, exc)
        return None
    if not listing.is_publishable():
        return None
    return listing
