"""Lazy Playwright browser pool with reusable per-slot contexts.

We deliberately keep this module dependency-soft: importing it must not
fail when Playwright is missing. The pool exposes `is_available` so the
rest of the pipeline can fall back gracefully and emit
`dynamic_js_required` errors instead of crashing.

Design:
    * One Browser instance for the whole process.
    * A bounded pool of Contexts sized to `browser_concurrency`.
      Contexts are created lazily on first borrow and reused for the
      lifetime of the pool. This avoids the ~150-300 ms
      `browser.new_context(...)` cost on every page render.
    * Each `page()` borrow takes a Context from the pool, opens a
      fresh Page on it, applies per-target-host UA / client-hint
      headers via `set_extra_http_headers`, yields the Page, then
      closes the Page and returns the Context to the pool.
    * Route interception is registered once per Context at creation
      time, so resource blocking persists across borrows without
      paying the route-table cost on every page.
"""
from __future__ import annotations

import asyncio
import logging
from collections import deque
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Optional

from .config import Settings
from .headers import build_headers, profile_for_url

log = logging.getLogger(__name__)

_BLOCKED_RESOURCE_TYPES = {"image", "media", "font", "stylesheet"}
_BLOCKED_URL_FRAGMENTS = (
    "google-analytics", "googletagmanager", "doubleclick", "facebook.net",
    "hotjar", "clarity.ms", "matomo", "segment.io", "sentry.io",
    "youtube.com/embed",
)
_DEFAULT_ACCEPT = (
    "text/html,application/xhtml+xml,application/xml;q=0.9,"
    "image/avif,image/webp,*/*;q=0.8"
)


def _locale_from_accept_language(accept_language: str, fallback: str) -> str:
    """Return a Playwright-friendly BCP-47 locale string."""
    if not accept_language:
        return fallback
    primary = accept_language.split(",", 1)[0].strip()
    return primary or fallback


class BrowserPool:
    """Holds a Playwright browser and a small pool of reusable contexts."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._lock = asyncio.Lock()
        self._playwright: Any = None
        self._browser: Any = None
        self._semaphore = asyncio.Semaphore(settings.browser_concurrency)
        self._available: Optional[bool] = None
        # Pool of idle contexts. Acquisition is gated by `_semaphore`
        # so the deque is only ever accessed from one borrow at a time.
        self._idle_contexts: deque = deque()
        self._all_contexts: list[Any] = []

    @property
    def is_available(self) -> bool:
        """True if Playwright is importable and `enable_playwright` is set."""
        if not self._settings.enable_playwright:
            return False
        if self._available is not None:
            return self._available
        try:
            import playwright  # noqa: F401
        except Exception as exc:  # noqa: BLE001
            log.warning("playwright not importable: %s", exc)
            self._available = False
            return False
        self._available = True
        return True

    async def start(self) -> bool:
        if not self.is_available:
            return False
        async with self._lock:
            if self._browser is not None:
                return True
            try:
                from playwright.async_api import async_playwright
            except Exception as exc:  # noqa: BLE001
                log.warning("playwright import failed: %s", exc)
                self._available = False
                return False
            try:
                self._playwright = await async_playwright().start()
                self._browser = await self._playwright.chromium.launch(
                    headless=True,
                    args=["--no-sandbox", "--disable-dev-shm-usage"],
                )
            except Exception as exc:  # noqa: BLE001
                log.warning("chromium launch failed: %s", exc)
                self._available = False
                self._browser = None
                if self._playwright is not None:
                    try:
                        await self._playwright.stop()
                    except Exception:  # noqa: BLE001
                        pass
                self._playwright = None
                return False
        return True

    async def close(self) -> None:
        """Tear down the browser, capped at 10s wall-clock.

        Each step (context.close, browser.close, playwright.stop) talks
        to the chromium driver over a pipe that may already be closing
        - exactly what happens during Ctrl-C cancellation. Without a
        wall-clock cap the close hangs indefinitely waiting for
        replies that will never come, blocking process exit and
        producing the 'pipe closed by peer' loop the user sees. After
        10s we abandon the chromium subprocess; the OS reaps it on
        Python exit, equivalent to a kill.
        """
        try:
            await asyncio.wait_for(self._close_inner(), timeout=10.0)
        except asyncio.TimeoutError:
            log.warning(
                "browser pool close exceeded 10s, abandoning chromium",
            )
        except Exception as exc:  # noqa: BLE001
            log.debug("browser pool close error: %s", exc)

    async def _close_inner(self) -> None:
        async with self._lock:
            for context in self._all_contexts:
                try:
                    await asyncio.wait_for(context.close(), timeout=2.0)
                except BaseException as exc:  # noqa: BLE001
                    log.debug("context close: %s", exc)
            self._all_contexts.clear()
            self._idle_contexts.clear()
            if self._browser is not None:
                try:
                    await asyncio.wait_for(
                        self._browser.close(), timeout=3.0,
                    )
                except BaseException as exc:  # noqa: BLE001
                    log.debug("browser close: %s", exc)
                self._browser = None
            if self._playwright is not None:
                try:
                    await asyncio.wait_for(
                        self._playwright.stop(), timeout=3.0,
                    )
                except BaseException as exc:  # noqa: BLE001
                    log.debug("playwright stop: %s", exc)
                self._playwright = None

    async def _build_context(self) -> Any:
        """Create a fresh long-lived context. Caller holds `_semaphore`."""
        # We pick a default profile here; the per-borrow UA override is
        # applied on the page itself via `set_extra_http_headers`.
        default_profile = profile_for_url("")
        context = await self._browser.new_context(
            user_agent=default_profile.user_agent,
            ignore_https_errors=not self._settings.verify_tls,
            locale=_locale_from_accept_language(
                self._settings.accept_language, fallback="fr-FR"
            ),
        )
        # Resource interception lives on the context, so blocking is
        # active for every page opened on it without per-page setup.
        await context.route("**/*", _route_handler)
        self._all_contexts.append(context)
        return context

    async def _acquire_context(self) -> Any:
        """Take an idle context, building one on demand up to the cap."""
        if self._idle_contexts:
            return self._idle_contexts.popleft()
        if len(self._all_contexts) < self._settings.browser_concurrency:
            return await self._build_context()
        # Should never happen because `_semaphore` caps concurrent
        # borrows at the same `browser_concurrency`, but if it does we
        # build a context anyway rather than block forever.
        return await self._build_context()

    def _release_context(self, context: Any) -> None:
        self._idle_contexts.append(context)

    @asynccontextmanager
    async def page(self, *, target_url: str = "") -> AsyncIterator[Any]:
        """Yield a freshly-prepared Playwright page on a pooled context."""
        if not await self.start():
            raise RuntimeError("playwright not available")
        await self._semaphore.acquire()
        context = None
        page = None
        context_healthy = True
        try:
            context = await self._acquire_context()
            profile = (
                profile_for_url(target_url) if target_url else profile_for_url("")
            )
            extra_headers = build_headers(
                profile,
                accept=_DEFAULT_ACCEPT,
                accept_language=self._settings.accept_language,
            )
            extra_for_playwright = {
                key: value for key, value in extra_headers.items()
                if key.lower() != "user-agent"
            }
            try:
                await context.set_extra_http_headers(extra_for_playwright)
            except Exception as exc:  # noqa: BLE001
                log.debug("set_extra_http_headers failed: %s", exc)
            page = await context.new_page()
            page.set_default_navigation_timeout(
                int(self._settings.browser_nav_timeout * 1000)
            )
            page.set_default_timeout(
                int(self._settings.browser_nav_timeout * 1000)
            )
            yield page
        finally:
            # Page close with a hard 3s timeout. A broken Playwright
            # connection can hang page.close() indefinitely, which
            # blocks the semaphore release and permanently reduces
            # browser pool capacity.
            if page is not None:
                try:
                    await asyncio.wait_for(page.close(), timeout=3.0)
                except Exception:  # noqa: BLE001
                    # Page close failed or timed out. The context may
                    # have corrupted state; mark it unhealthy so we
                    # discard it instead of returning to the idle pool.
                    context_healthy = False
            if context is not None:
                if context_healthy:
                    self._release_context(context)
                else:
                    # Discard the corrupted context. A fresh one will
                    # be built on next borrow. Remove from tracking
                    # so close() doesn't double-close it.
                    try:
                        self._all_contexts.remove(context)
                    except ValueError:
                        pass
                    try:
                        await asyncio.wait_for(context.close(), timeout=3.0)
                    except Exception:  # noqa: BLE001
                        pass
            self._semaphore.release()


_ROUTE_ACTION_TIMEOUT: float = 1.0


async def _route_handler(route: Any) -> None:
    """Block heavy / tracking resources to keep dynamic runs fast.

    Each route action is wrapped in `wait_for` AND a broad except.
    During domain-level cancellation Playwright still fires this
    handler one last time per in-flight request; the underlying
    `route.continue_()` / `route.abort()` then waits for a reply on
    the closing driver pipe. Without the time cap, those calls hang
    until Playwright tears the connection down, and each hang
    surfaces as 'Route.continue_: Connection closed while reading
    from the driver' - hundreds per cancelled domain in the user's
    run log. We bound the wait at 1s and swallow every error: the
    page is being closed regardless, so whether the route was
    aborted, continued, or neither does not affect correctness.
    """
    try:
        request = route.request
        if request.resource_type in _BLOCKED_RESOURCE_TYPES:
            try:
                await asyncio.wait_for(
                    route.abort(), timeout=_ROUTE_ACTION_TIMEOUT,
                )
            except BaseException:  # noqa: BLE001
                pass
            return
        url = request.url.lower()
        if any(fragment in url for fragment in _BLOCKED_URL_FRAGMENTS):
            try:
                await asyncio.wait_for(
                    route.abort(), timeout=_ROUTE_ACTION_TIMEOUT,
                )
            except BaseException:  # noqa: BLE001
                pass
            return
        try:
            await asyncio.wait_for(
                route.continue_(), timeout=_ROUTE_ACTION_TIMEOUT,
            )
        except BaseException:  # noqa: BLE001
            pass
    except BaseException:  # noqa: BLE001
        # Driver pipe is gone. Nothing we can do. Suppress to prevent
        # the cascade observed in the user's run output.
        pass
