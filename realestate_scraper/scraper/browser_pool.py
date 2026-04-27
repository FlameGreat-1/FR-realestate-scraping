"""Lazy Playwright browser pool with request interception.

We deliberately keep this module dependency-soft: importing it must not
fail when Playwright is missing. The pool exposes `is_available` so the
rest of the pipeline can fall back gracefully and emit
`dynamic_js_required` errors instead of crashing.
"""
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Optional

from .config import Settings

log = logging.getLogger(__name__)

_BLOCKED_RESOURCE_TYPES = {"image", "media", "font", "stylesheet"}
_BLOCKED_URL_FRAGMENTS = (
    "google-analytics", "googletagmanager", "doubleclick", "facebook.net",
    "hotjar", "clarity.ms", "matomo", "segment.io", "sentry.io",
    "youtube.com/embed",
)


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
    async def page(self) -> AsyncIterator[Any]:
        """Yield a freshly-prepared Playwright page with interception on."""
        if not await self.start():
            raise RuntimeError("playwright not available")
        await self._semaphore.acquire()
        context = None
        page = None
        try:
            context = await self._browser.new_context(
                user_agent=self._settings.user_agent,
                ignore_https_errors=not self._settings.verify_tls,
                locale="fr-FR",
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
