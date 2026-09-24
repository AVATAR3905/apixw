"""Smoke-test the real Playwright Chromium browser through the collector pool.

Loads a page (network first, local HTML fallback so it works offline), executes
JS, extracts text, and saves a screenshot proof.

Usage:
    python scripts/verify_browser_pool.py
"""

import json
import os
import sys
import tempfile
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.collectors.browser_pool import BrowserUnavailable, get_browser_pool

OUT_DIR = os.environ.get("EXTRACT_VERIFY_DIR") or os.path.join(tempfile.gettempdir(), "opencode")
os.makedirs(OUT_DIR, exist_ok=True)
SHOT = os.path.join(OUT_DIR, "browser_pool_smoke.png")
HTML = (
    "<html><body><h1 id='t'>India Airfare Test</h1>"
    "<span class='fare'>INR 4,999</span></body></html>"
)


async def _exercise(context) -> dict:
    page = context.pages[0] if context.pages else await context.new_page()
    origin = "local-html"
    try:
        await page.goto("https://example.com", timeout=12000, wait_until="domcontentloaded")
        origin = "network:example.com"
    except Exception as exc:  # offline / blocked networks must not fail the test
        print(f"  (network load skipped: {exc})")

    await page.set_content(HTML, wait_until="load")
    title = await page.locator("#t").inner_text()
    fares = await page.locator(".fare").all_inner_texts()
    viewport = await page.evaluate("({w: innerWidth, h: innerHeight})")
    await page.screenshot(path=SHOT, full_page=False)
    return {
        "origin": origin,
        "title": title,
        "fares": fares,
        "viewport": viewport,
        "screenshot": SHOT,
    }


if __name__ == "__main__":
    pool = get_browser_pool()
    print("pool stats before:", pool.stats())
    t0 = time.time()
    try:
        result = pool.run_browser(_exercise)
    except BrowserUnavailable as e:
        print(f"BROWSER UNAVAILABLE: {e}")
        sys.exit(1)
    print(f"browser round-trip in {time.time() - t0:.1f}s")
    print(json.dumps(result, indent=2))
    print("pool stats after: ", pool.stats())
    print("screenshot: ", SHOT)
    pool.stop()
    sys.exit(0)
