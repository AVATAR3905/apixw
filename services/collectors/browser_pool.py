"""Browser pool for Playwright collection with crash recovery.

Long-lived scraping (carrier portals, OTA XHR interception) is expensive:
launching a Chromium instance per request wastes seconds and leaks memory.
This pool keeps a small number of isolated browser contexts on a single
background asyncio loop and hands them out to collectors.

Degrades gracefully: if Playwright is not installed or the browser cannot
launch, ``acquire()`` raises ``BrowserUnavailable`` and callers may fall back
to their non-browser path.
"""

import asyncio
import logging
import threading
from collections import deque
from typing import Any, Coroutine, Deque, Optional

from packages.shared.config import settings

logger = logging.getLogger(__name__)


class BrowserUnavailable(Exception):
    """Raised when Playwright or a browser context cannot be provisioned."""


class BrowserPool:
    """Manages a background asyncio loop and a bounded pool of browser contexts."""

    def __init__(
        self,
        max_contexts: int = settings.BROWSE_POOL_MAX_CONTEXTS,
        idle_seconds: float = settings.BROWSE_CONTEXT_IDLE_SECONDS,
    ):
        self.max_contexts = max_contexts
        self.idle_seconds = idle_seconds
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._started = False
        self._lock = threading.Lock()
        self._idle_ctxs: Deque[Any] = deque()
        self._in_use = 0
        self._created = 0
        self._pw: Any = None

    # -- lifecycle ----------------------------------------------------------

    def start(self) -> None:
        """Start the background loop thread; blocks until the loop is live."""
        with self._lock:
            if self._started:
                return
            self._started = True
        ready = threading.Event()

        def _run() -> None:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            with self._lock:
                self._loop = loop
            ready.set()
            loop.run_forever()

        self._thread = threading.Thread(target=_run, name="browser-pool-loop", daemon=True)
        self._thread.start()
        if not ready.wait(timeout=5.0):
            raise BrowserUnavailable("Browser pool thread failed to start.")

    def submit(self, coro: Coroutine) -> Any:
        """Run a coroutine on the pool's loop and block for its result."""
        self.start()
        with self._lock:
            loop = self._loop
        future = asyncio.run_coroutine_threadsafe(coro, loop)
        return future.result()

    def stop(self, wait: float = 2.0) -> None:
        with self._lock:
            if not self._started:
                return
            self._started = False
            loop = self._loop
            self._loop = None
            idle = list(self._idle_ctxs)
            self._idle_ctxs.clear()
        if loop and loop.is_running():

            async def _shutdown() -> None:
                self_task = asyncio.current_task()
                for ctx in idle:
                    try:
                        await ctx.close()
                    except Exception:  # noqa: BLE001 - best-effort teardown
                        pass
                if self._pw is not None:
                    try:
                        await self._pw.stop()
                    except Exception:  # noqa: BLE001 - driver may already be gone
                        pass
                for task in asyncio.all_tasks(loop):
                    if task is not self_task and not task.done():
                        task.cancel()

            future = asyncio.run_coroutine_threadsafe(_shutdown(), loop)
            try:
                future.result(timeout=max(wait, 0.5))
            except Exception:  # noqa: BLE001 - teardown is best-effort
                pass
            loop.call_soon_threadsafe(loop.stop)
        if self._thread:
            self._thread.join(timeout=wait)

    # -- context management -------------------------------------------------

    async def _provision_context(self) -> Any:
        try:
            from playwright.async_api import async_playwright

            self._pw = self._pw or (await async_playwright().start())
            browser = await self._pw.chromium.launch(
                headless=True,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                ],
            )
            context = await browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1280, "height": 800},
            )
            self._created += 1
            return context
        except ImportError as e:  # pragma: no cover - path exercised only without playwright
            raise BrowserUnavailable(f"Playwright not installed ({e})") from e
        except Exception as e:  # pragma: no cover - relies on real browser
            raise BrowserUnavailable(f"Could not launch browser context ({e})") from e

    async def acquire(self) -> Any:
        with self._lock:
            if not self._started:
                raise BrowserUnavailable("Pool not started")
            if self._idle_ctxs:
                return self._idle_ctxs.popleft()
            if self._in_use >= self.max_contexts:
                raise BrowserUnavailable("Context limit reached")
            self._in_use += 1
        try:
            ctx = await self._provision_context()
            return ctx
        except BrowserUnavailable:
            with self._lock:
                self._in_use = max(0, self._in_use - 1)
            raise

    async def release(self, context: Any) -> None:
        with self._lock:
            self._in_use = max(0, self._in_use - 1)
            self._idle_ctxs.append(context)

    async def discard(self, context: Any) -> None:
        with self._lock:
            self._in_use = max(0, self._in_use - 1)
        try:
            await context.close()
        except Exception:  # pragma: no cover
            pass

    def run_browser(self, coro: Coroutine) -> Any:
        """Acquire a context, run ``coro(context)``, release or discard on failure."""

        async def _runner():
            ctx = None
            try:
                ctx = await self.acquire()
                return await coro(ctx)
            except BrowserUnavailable:
                raise
            except Exception:
                if ctx is not None:
                    await self.discard(ctx)
                    ctx = None
                raise
            finally:
                if ctx is not None:
                    await self.release(ctx)

        return self.submit(_runner())

    def stats(self) -> dict:
        with self._lock:
            return {
                "started": self._started,
                "idle_contexts": len(self._idle_ctxs),
                "in_use": self._in_use,
                "created": self._created,
                "max_contexts": self.max_contexts,
            }


_default_pool: Optional[BrowserPool] = None


def get_browser_pool() -> BrowserPool:
    global _default_pool
    if _default_pool is None:
        _default_pool = BrowserPool()
    return _default_pool
