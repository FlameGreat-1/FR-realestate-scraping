"""Lazy Playwright browser pool with request interception.

We deliberately keep this module dependency-soft: importing it must not
fail when Playwright is missing. The pool exposes `is_available` so the
rest of the pipeline can fall back gracefully and emit
`dynamic_js_required` errors instead of crashing.

The per-page context reuses the same UA + client-hint profile that the
static fetcher would have sent, so a domain whose static request was
rotated to a Firefox/Linux profile presents that same fingerprint when
we later render it in headless Chromium.
"""
from __future__ import annotations

import asyncio
import logging
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
    """Holds a single Playwright browser and a per-context semaphore."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._lock = asyncio.Lock()
        self._playwright: Any = None
        self._browser: Any = None
        self._semaphore = asyncio.Semaphore(settings.browser_concurrency)
        self._available: Optional[bool] = None

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
        async with self._lock:
            if self._browser is not None:
                try:
                    await self._browser.close()
                except Exception as exc:  # noqa: BLE001
                    log.debug("browser close: %s", exc)
                self._browser = None
            if self._playwright is not None:
                try:
                    await self._playwright.stop()
                except Exception as exc:  # noqa: BLE001
                    log.debug("playwright stop: %s", exc)
                self._playwright = None

    @asynccontextmanager
    async def page(self, *, target_url: str = "") -> AsyncIterator[Any]:
        """Yield a freshly-prepared Playwright page with interception on.

        `target_url` lets the caller align the headless context's
        fingerprint with the static fetcher's choice for the same host.
        When omitted, the first profile in the pool is used.
        """
        if not await self.start():
            raise RuntimeError("playwright not available")
        await self._semaphore.acquire()
        context = None
        page = None
        try:
            profile = profile_for_url(target_url) if target_url else profile_for_url("")
            extra_headers = build_headers(
                profile,
                accept=_DEFAULT_ACCEPT,
                accept_language=self._settings.accept_language,
            )
            # The User-Agent is set on the context constructor (Playwright
            # honours it across all requests); the rest go in extra_http_headers.
            extra_for_playwright = {
                key: value for key, value in extra_headers.items()
                if key.lower() != "user-agent"
            }
            context = await self._browser.new_context(
                user_agent=profile.user_agent,
                ignore_https_errors=not self._settings.verify_tls,
                locale=_locale_from_accept_language(
                    self._settings.accept_language, fallback="fr-FR"
                ),
                extra_http_headers=extra_for_playwright,
            )
            await context.route("**/*", _route_handler)
            page = await context.new_page()
            page.set_default_navigation_timeout(
                int(self._settings.browser_nav_timeout * 1000)
            )
            page.set_default_timeout(
                int(self._settings.browser_nav_timeout * 1000)
            )
            yield page
        finally:
            try:
                if page is not None:
                    await page.close()
            except Exception:  # noqa: BLE001
                pass
            try:
                if context is not None:
                    await context.close()
            except Exception:  # noqa: BLE001
                pass
            self._semaphore.release()


async def _route_handler(route: Any) -> None:
    """Block heavy / tracking resources to keep dynamic runs fast."""
    request = route.request
    if request.resource_type in _BLOCKED_RESOURCE_TYPES:
        try:
            await route.abort()
        except Exception:  # noqa: BLE001
            await route.continue_()
        return
    url = request.url.lower()
    if any(fragment in url for fragment in _BLOCKED_URL_FRAGMENTS):
        try:
            await route.abort()
        except Exception:  # noqa: BLE001
            await route.continue_()
        return
    await route.continue_()
