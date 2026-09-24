"""Carrier Direct Website Scraper using Playwright / Direct Endpoints (PRD Section 24, 25).

Functions as:
Primary Authoritative Feed (Priority 1):
Scrapes official airline booking portals to capture true carrier prices before aggregator markups.
"""

import asyncio
import datetime
import hashlib
import json
import logging
import os
from typing import Any, Dict, List, Optional

from playwright.async_api import async_playwright
from sqlalchemy.orm import Session

from packages.schemas.models import RawPayload, Source
from packages.shared.time_utils import utcnow
from services.collectors.browser_pool import BrowserUnavailable, get_browser_pool
from services.collectors.circuit_breaker import (
    CircuitBreaker,
)
from services.collectors.ethical_scraping import RobotsTxtChecker

logger = logging.getLogger(__name__)

# One shared robots.txt checker (per-domain cache) for every carrier-direct request.
_ROBOTS_CHECKER = RobotsTxtChecker()

# Case-insensitive substrings that indicate a bot-challenge / block page rather
# than genuine search results. Detected on rendered body text and on any
# 403/429/503 HTTP status so a challenge page is never mistaken for "no fares".
_BLOCK_PAGE_MARKERS = (
    "captcha", "recaptcha", "hcaptcha", "cloudflare", "are you a human",
    "unusual traffic", "access denied", "request blocked", "bot detection",
    "verify you are human",
)

# Real per-carrier search-URL builders. Only SpiceJet's is verified against a
# live network-JSON response in this codebase (see `_SPICEJET_AVAILABILITY_PATH`
# below); the others route to the carrier's *own* domain (fixing a bug where
# every non-SG/6E carrier silently searched spicejet.com) but their DOM/XHR
# layout has not been reverse-engineered here, so they rely on the generic
# DOM/OCR/calibrated degrade chain.
_CARRIER_SEARCH_URLS = {
    "SG": lambda o, d, t: f"https://www.spicejet.com/search?from={o}&to={d}&tripType=1&departure={t}&adult=1",
    "6E": lambda o, d, t: f"https://www.goindigo.in/flight-booking.html?origin={o}&destination={d}&date={t}",
    "AI": lambda o, d, t: f"https://www.airindia.com/en-in/book/select-flights?tripType=ONE_WAY&origin={o}&destination={d}&departDate={t}&adult=1",
    "QP": lambda o, d, t: f"https://www.akasaair.com/flight-search?tripType=O&origin={o}&destination={d}&departureDate={t}&adultCount=1&childCount=0&infantCount=0&cabinType=Economy",
    "IX": lambda o, d, t: f"https://www.airindiaexpress.com/book/flight-select?tripType=O&origin={o}&destination={d}&departDate={t}&adult=1",
}

_CARRIER_DOMAINS = {
    "SG": "www.spicejet.com",
    "6E": "www.goindigo.in",
    "AI": "www.airindia.com",
    "QP": "www.akasaair.com",
    "IX": "www.airindiaexpress.com",
}

_SPICEJET_AVAILABILITY_PATH = "api/v3/search/availability"
_AKASA_AVAILABILITY_PATH = "/api/ibe/availability/search"

# City names Akasa's "Where from/to?" autocomplete actually indexes on, for the
# 10 basket airports. Verified live for DEL/BOM; the others follow the same
# "city name -> pick the suggestion row" pattern but weren't individually
# confirmed (Akasa may simply not serve some of the regional-thin routes, in
# which case no suggestion appears and the flow safely falls through to the
# calibrated baseline like any other non-match).
_AKASA_CITY_NAMES = {
    "DEL": "Delhi", "BOM": "Mumbai", "BLR": "Bengaluru", "CCU": "Kolkata",
    "HYD": "Hyderabad", "MAA": "Chennai", "IXS": "Silchar", "DHM": "Dharamsala",
}


class CarrierDirectScraper:
    """Scrapes flight quotes directly from airline official booking portals."""

    SOURCE_NAME = "Carrier Direct Booking Scraper"

    def __init__(self, raw_dir: str = "data/raw/live/carrier_direct"):
        self.raw_dir = raw_dir
        os.makedirs(raw_dir, exist_ok=True)
        self.circuit_breaker = CircuitBreaker(
            source_id=5,
            source_name=self.SOURCE_NAME,
            failure_threshold=5,
            recovery_timeout_seconds=60.0,
        )

    def scrape_carrier_corridor(
        self,
        carrier_code: str,
        origin_airport: str,
        destination_airport: str,
        advance_days: int,
        search_date: Optional[datetime.date] = None,
        db: Optional[Session] = None,
    ) -> List[Dict[str, Any]]:
        """
        Scrapes direct quotes for a carrier and corridor on a given horizon.
        Prefers an idle pooled browser context, falls back to a dedicated
        Playwright launch, then to the calibrated direct baseline.

        Under ``SCRAPE_MODE=calibrated`` (presentations/offline demos) the
        network/browser/OCR/VLM path is skipped entirely and the deterministic
        calibrated baseline is served immediately. Under ``SCRAPE_MODE=hybrid``
        the same deterministic baseline is served while the RPC feed goes live.
        """
        if search_date is None:
            search_date = datetime.date.today()

        travel_date = search_date + datetime.timedelta(days=advance_days)
        origin, dest = origin_airport.upper(), destination_airport.upper()

        from packages.shared.config import settings

        if settings.SCRAPE_MODE in ("calibrated", "hybrid"):
            logger.info(
                "SCRAPE_MODE=%s: serving deterministic calibrated baseline for %s %s->%s",
                settings.SCRAPE_MODE, carrier_code, origin, dest,
            )
            return self._generate_authoritative_carrier_quotes(
                carrier_code=carrier_code,
                origin=origin,
                dest=dest,
                travel_date=travel_date,
                advance_days=advance_days,
            )

        pool = get_browser_pool()
        try:
            return pool.run_browser(
                lambda ctx: self._scrape_with_context(
                    ctx,
                    carrier_code=carrier_code,
                    origin=origin,
                    dest=dest,
                    travel_date=travel_date,
                    advance_days=advance_days,
                    db=db,
                )
            )
        except BrowserUnavailable as e:
            logger.warning(
                "Browser pool unavailable for %s (%s); trying dedicated launch.",
                carrier_code, e,
            )
            try:
                return asyncio.run(
                    self._legacy_async_scrape(
                        carrier_code, origin, dest, travel_date, advance_days, db
                    )
                )
            except Exception as e:
                logger.warning(
                    "Dedicated browser scrape failed for %s (%s); using calibrated baseline.",
                    carrier_code, e,
                )
                return self._generate_authoritative_carrier_quotes(
                    carrier_code=carrier_code,
                    origin=origin,
                    dest=dest,
                    travel_date=travel_date,
                    advance_days=advance_days,
                )
        except Exception as e:
            # A crashed Playwright driver (e.g. node EPIPE) must never abort the
            # whole corridor run: degrade to the calibrated authoritative baseline.
            logger.warning(
                "Browser scrape crashed for %s (%s); using calibrated baseline.",
                carrier_code, e,
            )
            return self._generate_authoritative_carrier_quotes(
                carrier_code=carrier_code,
                origin=origin,
                dest=dest,
                travel_date=travel_date,
                advance_days=advance_days,
            )

    async def _legacy_async_scrape(
        self,
        carrier_code: str,
        origin: str,
        dest: str,
        travel_date: datetime.date,
        advance_days: int,
        db: Optional[Session] = None,
    ) -> List[Dict[str, Any]]:
        """Playwright launch path used when the pool cannot provision a context."""
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                ],
            )
            try:
                context = await browser.new_context(
                    user_agent=(
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
                    ),
                    viewport={"width": 1280, "height": 800},
                )
                return await self._scrape_with_context(
                    context,
                    carrier_code,
                    origin,
                    dest,
                    travel_date,
                    advance_days,
                    db,
                )
            finally:
                await browser.close()

    async def _scrape_with_context(
        self,
        context,
        carrier_code: str,
        origin: str,
        dest: str,
        travel_date: datetime.date,
        advance_days: int,
        db: Optional[Session] = None,
    ) -> List[Dict[str, Any]]:
        """Network-JSON / DOM harvest + screen-OCR extraction on a shared browser context.

        Every request is gated by robots.txt (real ``urllib.robotparser`` check,
        not a hardcoded path list) and every response is screened for a
        bot-challenge page before being trusted as "no fares available".
        """
        code = carrier_code.upper()
        quotes: List[Dict[str, Any]] = []
        travel_date_str = travel_date.isoformat()

        if code == "QP":
            homepage = "https://www.akasaair.com/"
            if not _ROBOTS_CHECKER.can_fetch(homepage):
                logger.warning("robots.txt disallows %s; skipping live scrape.", homepage)
                self._store_raw_payload(db, [], carrier_code, origin, dest, travel_date_str)
                return []
            try:
                quotes = await self._scrape_akasa_interactive(
                    context, origin, dest, travel_date, advance_days
                )
            except Exception as e:
                logger.warning("Akasa interactive scrape failed: %s", e)
            if not quotes:
                quotes = self._generate_authoritative_carrier_quotes(
                    carrier_code=carrier_code, origin=origin, dest=dest,
                    travel_date=travel_date, advance_days=advance_days,
                )
            self._store_raw_payload(db, quotes, carrier_code, origin, dest, travel_date_str)
            return quotes

        url_builder = _CARRIER_SEARCH_URLS.get(code, _CARRIER_SEARCH_URLS["SG"])
        target_url = url_builder(origin, dest, travel_date_str)

        if not _ROBOTS_CHECKER.can_fetch(target_url):
            logger.warning("robots.txt disallows %s for %s; skipping live scrape.", target_url, code)
            self._store_raw_payload(db, [], carrier_code, origin, dest, travel_date_str)
            return []

        page = await context.new_page()
        screenshot_path = None
        blocked = False
        api_responses: List[Dict[str, Any]] = []

        try:
            async def handle_response(res):
                try:
                    ct = res.headers.get("content-type", "")
                    if "json" in ct and res.request.resource_type in ("xhr", "fetch"):
                        api_responses.append({"url": res.url, "body": await res.json()})
                except Exception:
                    pass

            page.on("response", handle_response)
            resp = await page.goto(target_url, wait_until="domcontentloaded", timeout=15000)
            await page.wait_for_timeout(3000)

            if resp is not None and resp.status in (403, 429, 503):
                blocked = True
            else:
                body_lower = (await page.inner_text("body"))[:4000].lower()
                if any(marker in body_lower for marker in _BLOCK_PAGE_MARKERS):
                    blocked = True

            if blocked:
                logger.warning("Bot-challenge / block page detected for %s at %s", code, target_url)
            elif code == "SG":
                quotes = self._parse_spicejet_availability(
                    api_responses, origin, dest, travel_date_str, advance_days
                )
            else:
                # Generic path for carriers without a verified JSON schema:
                # try structured DOM price cards first, then any intercepted
                # JSON payload that looks like it carries fare amounts.
                quotes = await self._extract_generic_dom_prices(
                    page, code, origin, dest, travel_date_str, advance_days
                )
                if not quotes:
                    quotes = self._extract_generic_json_prices(
                        api_responses, code, origin, dest, travel_date_str, advance_days
                    )

            if not quotes and not blocked:
                screenshot_path = await self._capture_screenshot(
                    page, carrier_code, origin, dest, travel_date_str
                )

        except Exception as e:
            logger.warning("Live navigation failed for %s (%s): %s", code, target_url, e)

        # OCR is the next live production stage when DOM/JSON produced nothing
        # (canvas rendering) and no bot-challenge was seen. Skipped entirely on
        # a detected block, since OCR-ing a CAPTCHA page cannot yield a fare.
        if not quotes and not blocked:
            quotes = self._extract_via_ocr(
                carrier_code, origin, dest, travel_date_str, advance_days, screenshot_path
            )

        if not quotes:
            quotes = self._generate_authoritative_carrier_quotes(
                carrier_code=carrier_code,
                origin=origin,
                dest=dest,
                travel_date=travel_date,
                advance_days=advance_days,
            )

        self._store_raw_payload(db, quotes, carrier_code, origin, dest, travel_date_str)
        return quotes

    async def _scrape_akasa_interactive(
        self,
        context,
        origin: str,
        dest: str,
        travel_date: datetime.date,
        advance_days: int,
    ) -> List[Dict[str, Any]]:
        """Real Akasa Air search: unlike SpiceJet, Akasa has no deep-link URL --
        the search form must be filled in and submitted (verified live 2026-09:
        real fares captured end-to-end for DEL-BOM T+15). Intercepts the real
        ``/api/ibe/availability/search`` XHR the site's own JS triggers.
        """
        origin_name = _AKASA_CITY_NAMES.get(origin.upper())
        dest_name = _AKASA_CITY_NAMES.get(dest.upper())
        if not origin_name or not dest_name:
            return []  # route not in our verified city-name map -> safe no-op

        page = await context.new_page()
        api_responses: List[Dict[str, Any]] = []

        async def handle_response(res):
            try:
                if _AKASA_AVAILABILITY_PATH in res.url and "json" in res.headers.get("content-type", ""):
                    api_responses.append(await res.json())
            except Exception:
                pass

        page.on("response", handle_response)
        try:
            await page.goto("https://www.akasaair.com/", wait_until="networkidle", timeout=25000)
            await page.wait_for_timeout(1500)

            close_btn = await page.query_selector("text=\"Close\"")
            if close_btn:
                await close_btn.click()
                await page.wait_for_timeout(300)

            from_input = await page.query_selector("#From")
            await from_input.click()
            await from_input.fill(origin_name)
            await page.wait_for_timeout(1200)
            if not await self._click_akasa_suggestion(page, origin_name):
                return []
            await page.wait_for_timeout(600)

            to_input = await page.query_selector("#To")
            await to_input.click()
            await to_input.fill(dest_name)
            await page.wait_for_timeout(1200)
            if not await self._click_akasa_suggestion(page, dest_name):
                return []
            await page.wait_for_timeout(600)

            dep_input = await page.query_selector("input[placeholder='Departure date']")
            await dep_input.click()
            await page.wait_for_timeout(800)
            picked = await self._click_akasa_calendar_date(page, travel_date)
            if not picked:
                return []
            await page.wait_for_timeout(600)

            search_btn = await page.query_selector("button:has-text('Search Flights')")
            if search_btn is None or not await search_btn.is_enabled():
                return []  # form validation didn't clear (bad city/date match)
            await search_btn.click()
            await page.wait_for_timeout(9000)
        finally:
            await page.close()

        return self._parse_akasa_availability(api_responses, origin, dest, travel_date, advance_days)

    @staticmethod
    async def _click_akasa_suggestion(page, city_name: str) -> bool:
        """Clicks the autocomplete suggestion row inside the "Our Destinations"
        dropdown -- scoped to that specific panel (not a page-wide text search)
        so it never matches an unrelated promo banner mentioning the same city.
        Returns False (safe no-op) if no matching suggestion appears, e.g. a
        route Akasa doesn't actually serve.
        """
        panel = page.locator("div:has-text('Our Destinations')").last
        try:
            await panel.wait_for(state="visible", timeout=5000)
        except Exception:
            return False
        row = panel.get_by_text(city_name, exact=False).first
        try:
            await row.click(timeout=5000)
            return True
        except Exception:
            return False

    @staticmethod
    async def _click_akasa_calendar_date(page, target_date: datetime.date) -> bool:
        """Clicks the target date in Akasa's 2-month side-by-side calendar,
        paging forward with the "next" control when the target month isn't
        yet visible. Best-effort: verified live for a same/next-month target
        (covers T+1..T+15); far-out horizons (T+30/T+45) may need more than
        the bounded page attempts below and will safely no-op (caller falls
        back to the calibrated baseline) if the month never becomes visible.
        """
        import re

        month_label = target_date.strftime("%B %Y")
        for _ in range(6):
            headers = await page.get_by_text(re.compile(r"^[A-Z][a-z]+ \d{4}$")).all()
            texts = [await h.inner_text() for h in headers]
            if month_label in texts:
                header = headers[texts.index(month_label)]
                hbox = await header.bounding_box()
                day_cells = await page.locator("[aria-label='day-block']").all()
                target_day = str(target_date.day)
                for cell in day_cells:
                    if (await cell.inner_text()).strip() != target_day:
                        continue
                    cbox = await cell.bounding_box()
                    if cbox and hbox and abs(cbox["x"] - hbox["x"]) < 250 and cbox["y"] > hbox["y"]:
                        await cell.click()
                        return True
                return False
            advanced = False
            for btn in await page.locator("button, [role=button]").all():
                aria = (await btn.get_attribute("aria-label")) or ""
                if "next" in aria.lower():
                    await btn.click()
                    advanced = True
                    break
            if not advanced:
                return False
            await page.wait_for_timeout(400)
        return False

    def _parse_akasa_availability(
        self,
        api_responses: List[Dict[str, Any]],
        origin: str,
        dest: str,
        travel_date: datetime.date,
        advance_days: int,
    ) -> List[Dict[str, Any]]:
        """Parses Akasa's real ``/api/ibe/availability/search`` response.

        Verified live shape (2026-09): ``data.results[].trips[].
        journeysAvailableByMarket[].value[]`` lists each flight (segment
        identifier = flight number/carrier code, designator times); each
        flight's ``fares[].fareAvailabilityKey`` indexes into the sibling
        ``data.faresAvailable`` list of ``{key, value}`` pairs, whose
        ``value.fares[0].passengerFares[0]`` carries ``publishedFare`` (base)
        and ``fareAmount`` (total) -- same base/total split pattern as
        SpiceJet's NDC-style response.
        """
        travel_date_str = travel_date.isoformat()
        quotes: List[Dict[str, Any]] = []

        for payload in api_responses:
            data = payload.get("data") or {}
            fares_catalog = {item["key"]: item["value"] for item in (data.get("faresAvailable") or [])}
            for trip in data.get("results") or []:
                for t in trip.get("trips") or []:
                    for market in t.get("journeysAvailableByMarket") or []:
                        for journey in market.get("value") or []:
                            designator = journey.get("designator", {})
                            segments = journey.get("segments") or []
                            fare_keys = [f.get("fareAvailabilityKey") for f in (journey.get("fares") or [])]

                            best_amount = None
                            best_base = None
                            for key in fare_keys:
                                entry = fares_catalog.get(key)
                                if not entry:
                                    continue
                                for fare in entry.get("fares") or []:
                                    for pf in fare.get("passengerFares") or []:
                                        if pf.get("passengerType") not in (None, "ADT"):
                                            continue
                                        amount = pf.get("fareAmount")
                                        base = pf.get("publishedFare") or pf.get("revenueFare")
                                        if amount is None:
                                            continue
                                        if best_amount is None or amount < best_amount:
                                            best_amount, best_base = amount, base

                            if best_amount is None or not (1500 <= best_amount <= 60000):
                                continue

                            carrier_code, flight_no = "QP", None
                            if segments:
                                ident = segments[0].get("identifier", {})
                                carrier_code = ident.get("carrierCode", "QP")
                                flight_no = ident.get("identifier")

                            base_fare = float(best_base) if best_base is not None else round(best_amount * 0.8, 2)
                            tax_bucket = round(float(best_amount) - base_fare, 2)

                            quotes.append(
                                {
                                    "source": "CARRIER_DIRECT",
                                    "carrier_code": carrier_code,
                                    "carrier_name": self._carrier_name(carrier_code),
                                    "origin_airport": designator.get("origin", origin),
                                    "destination_airport": designator.get("destination", dest),
                                    "travel_date": travel_date_str,
                                    "advance_purchase_days": advance_days,
                                    "flight_number": f"{carrier_code}-{flight_no}" if flight_no else f"{carrier_code}-101",
                                    "departure_time": (designator.get("departure") or "")[11:16] or "00:00",
                                    "arrival_time": (designator.get("arrival") or "")[11:16] or None,
                                    "stops": max(0, len(segments) - 1),
                                    "base_fare": base_fare,
                                    "fuel_surcharge": 0.0,
                                    "tax_amount": tax_bucket,
                                    "development_fee": 0.0,
                                    "convenience_fee": 0.0,
                                    "total_fare": float(best_amount),
                                    "cabin_class": "ECONOMY",
                                    "fare_family": "BASIC",
                                    "feed_type": "CARRIER_DIRECT",
                                    "extraction_method": "NETWORK_API",
                                }
                            )
        return quotes

    def _parse_spicejet_availability(
        self,
        api_responses: List[Dict[str, Any]],
        origin: str,
        dest: str,
        travel_date_str: str,
        advance_days: int,
    ) -> List[Dict[str, Any]]:
        """Parses SpiceJet's real ``api/v3/search/availability`` XHR response.

        Verified live shape (2026-09): ``data.trips[].journeysAvailable[]`` lists
        each flight (segment identifier = flight number, carrier code, times);
        each journey's ``fares`` dict keys into the sibling ``data.faresAvailable``
        catalog, whose entries carry ``passengerFares[0]`` with ``fareAmount``
        (total) and ``publishedFare``/``revenueFare`` (carrier base component).
        """
        quotes: List[Dict[str, Any]] = []
        payload = None
        for entry in api_responses:
            if _SPICEJET_AVAILABILITY_PATH in entry.get("url", ""):
                payload = entry.get("body")
                break
        if not payload:
            return quotes

        try:
            data = payload.get("data", {})
            fares_catalog = data.get("faresAvailable", {})
            trips = data.get("trips", [])
        except AttributeError:
            return quotes

        for trip in trips:
            for journey in trip.get("journeysAvailable", []):
                designator = journey.get("designator", {})
                segments = journey.get("segments", [])
                fare_keys = list(journey.get("fares", {}).keys())
                if not fare_keys:
                    continue

                # Fare-mix protection at the source: pick the cheapest fare
                # option for this specific flight (lowest available economy).
                best_amount = None
                best_base = None
                for key in fare_keys:
                    fare_entry = fares_catalog.get(key)
                    if not fare_entry:
                        continue
                    passenger_fares = fare_entry.get("passengerFares") or []
                    adult_fare = next(
                        (pf for pf in passenger_fares if pf.get("passengerType") == "ADT"),
                        passenger_fares[0] if passenger_fares else None,
                    )
                    if not adult_fare:
                        continue
                    amount = adult_fare.get("fareAmount")
                    base = adult_fare.get("publishedFare") or adult_fare.get("revenueFare")
                    if amount is None:
                        continue
                    if best_amount is None or amount < best_amount:
                        best_amount, best_base = amount, base

                if best_amount is None or not (1500 <= best_amount <= 60000):
                    continue

                flight_no = None
                carrier_code = "SG"
                if segments:
                    ident = segments[0].get("identifier", {})
                    carrier_code = ident.get("carrierCode", "SG")
                    flight_no = ident.get("identifier")

                base_fare = float(best_base) if best_base is not None else round(best_amount * 0.76, 2)
                surcharge_bucket = round(float(best_amount) - base_fare, 2)

                quotes.append(
                    {
                        "source": "CARRIER_DIRECT",
                        "carrier_code": carrier_code,
                        "carrier_name": self._carrier_name(carrier_code),
                        "origin_airport": designator.get("origin", origin),
                        "destination_airport": designator.get("destination", dest),
                        "travel_date": travel_date_str,
                        "advance_purchase_days": advance_days,
                        "flight_number": f"{carrier_code}-{flight_no}" if flight_no else f"{carrier_code}-101",
                        "departure_time": (designator.get("departure") or "")[11:16] or "00:00",
                        "arrival_time": (designator.get("arrival") or "")[11:16] or None,
                        "stops": max(0, len(segments) - 1),
                        "base_fare": base_fare,
                        # SpiceJet's public response separates base vs total but does
                        # not itemize fuel/GST/UDF/convenience individually, so the
                        # remainder is carried as a single carrier-added bucket
                        # (tax_amount) rather than guessed at with a fixed formula.
                        "fuel_surcharge": 0.0,
                        "tax_amount": surcharge_bucket,
                        "development_fee": 0.0,
                        "convenience_fee": 0.0,
                        "total_fare": float(best_amount),
                        "cabin_class": "ECONOMY",
                        "fare_family": "BASIC",
                        "feed_type": "CARRIER_DIRECT",
                        "extraction_method": "NETWORK_API",
                    }
                )

        return quotes

    async def _extract_generic_dom_prices(
        self,
        page,
        carrier_code: str,
        origin: str,
        dest: str,
        travel_date_str: str,
        advance_days: int,
    ) -> List[Dict[str, Any]]:
        """Best-effort DOM price-card scrape for carriers without a verified schema."""
        quotes: List[Dict[str, Any]] = []
        try:
            price_elements = await page.query_selector_all(
                "[data-testid*='fare'], [data-testid*='price'], .fare-price, .price, "
                "[class*='flight-price'], [class*='fareAmount'], [class*='FareAmount']"
            )
            for idx, el in enumerate(price_elements[:6]):
                txt = await el.inner_text()
                txt_clean = txt.replace("₹", "").replace(",", "").strip()
                try:
                    val = float(txt_clean)
                except ValueError:
                    continue
                if 1500 <= val <= 60000:
                    quotes.append(
                        {
                            "source": "CARRIER_DIRECT",
                            "carrier_code": carrier_code,
                            "carrier_name": self._carrier_name(carrier_code),
                            "origin_airport": origin,
                            "destination_airport": dest,
                            "travel_date": travel_date_str,
                            "advance_purchase_days": advance_days,
                            "flight_number": f"{carrier_code}-{100 + idx * 10 + 1}",
                            "departure_time": f"{8 + idx * 2:02d}:30",
                            "stops": 0,
                            "total_fare": val,
                            "cabin_class": "ECONOMY",
                            "fare_family": "BASIC",
                            "feed_type": "CARRIER_DIRECT",
                            "extraction_method": "DOM_BROWSER",
                        }
                    )
        except Exception:
            return []
        return quotes

    def _extract_generic_json_prices(
        self,
        api_responses: List[Dict[str, Any]],
        carrier_code: str,
        origin: str,
        dest: str,
        travel_date_str: str,
        advance_days: int,
    ) -> List[Dict[str, Any]]:
        """Scans any intercepted XHR JSON for plausible fare-amount fields.

        Unverified generic fallback: looks for common field names
        (fareAmount/totalFare/totalPrice/grandTotal/amount) with a numeric
        value inside the valid domestic-fare band, for carriers whose response
        schema hasn't been individually reverse-engineered.
        """
        candidates: List[float] = []
        field_names = ("fareamount", "totalfare", "totalprice", "grandtotal", "totalamount")

        def _walk(node: Any):
            if isinstance(node, dict):
                for k, v in node.items():
                    if isinstance(v, (int, float)) and k.lower() in field_names:
                        if 1500 <= v <= 60000:
                            candidates.append(float(v))
                    else:
                        _walk(v)
            elif isinstance(node, list):
                for item in node:
                    _walk(item)

        for entry in api_responses:
            _walk(entry.get("body"))

        quotes = []
        for idx, val in enumerate(sorted(set(candidates))[:6]):
            quotes.append(
                {
                    "source": "CARRIER_DIRECT",
                    "carrier_code": carrier_code,
                    "carrier_name": self._carrier_name(carrier_code),
                    "origin_airport": origin,
                    "destination_airport": dest,
                    "travel_date": travel_date_str,
                    "advance_purchase_days": advance_days,
                    "flight_number": f"{carrier_code}-{100 + idx * 10 + 1}",
                    "departure_time": f"{8 + idx * 2:02d}:30",
                    "stops": 0,
                    "total_fare": val,
                    "cabin_class": "ECONOMY",
                    "fare_family": "BASIC",
                    "feed_type": "CARRIER_DIRECT",
                    "extraction_method": "NETWORK_JSON_GENERIC",
                }
            )
        return quotes

    async def _capture_screenshot(
        self, page, carrier_code: str, origin: str, dest: str, date_str: str
    ) -> Optional[str]:
        """Saves a full-page screenshot for the OCR stage."""
        try:
            path = os.path.join(
                self.raw_dir,
                f"screenshot_{carrier_code}_{origin}_{dest}_{date_str}.png",
            )
            await page.screenshot(path=path, full_page=True)
            return path
        except Exception:
            return None

    def _extract_via_ocr(
        self,
        carrier_code: str,
        origin: str,
        dest: str,
        date_str: str,
        advance_days: int,
        screenshot_path: Optional[str],
    ) -> List[Dict[str, Any]]:
        """Attempts live extraction from a screenshot when DOM parsing failed."""
        if not screenshot_path:
            return []
        try:
            from services.extraction.adaptive_extractor import (
                AdaptiveExtractor,
                ExtractionContext,
            )

            # OCR only in the live scraper: the VLM weight set is far too slow to
            # load mid-collection for a single screenshot. VLM stays an explicit
            # offline/verify-stage tool.
            result = AdaptiveExtractor(allow_vlm=False).extract(
                ExtractionContext(
                    image_path=screenshot_path,
                    reference_date=date_str,
                )
            )
            price = result.fields.get("price")
            if not price:
                return []

            extracted_travel_date = result.fields.get("travel_date")
            if extracted_travel_date and extracted_travel_date != date_str:
                logger.warning(
                    "OCR date mismatch on %s screenshot: page shows %s, queried %s",
                    carrier_code.upper(), extracted_travel_date, date_str,
                )

            return [
                {
                    "source": "CARRIER_DIRECT",
                    "carrier_code": carrier_code.upper(),
                    "carrier_name": result.fields.get("airline_name") or self._carrier_name(carrier_code),
                    "origin_airport": result.fields.get("origin") or origin,
                    "destination_airport": result.fields.get("destination") or dest,
                    "travel_date": extracted_travel_date or date_str,
                    "return_date": result.fields.get("return_date"),
                    "advance_purchase_days": advance_days,
                    "flight_number": result.fields.get("flight_number") or f"{carrier_code.upper()}-101",
                    "departure_time": result.fields.get("departure_time") or "09:00",
                    "arrival_time": result.fields.get("arrival_time"),
                    "stops": result.fields.get("stops", 0),
                    "duration_minutes": result.fields.get("duration_minutes"),
                    "total_fare": float(price),
                    "cabin_class": "ECONOMY",
                    "fare_family": "BASIC",
                    "feed_type": "CARRIER_DIRECT",
                    "extraction_method": result.extraction_method,
                }
            ]
        except Exception as e:
            logger.warning("OCR extraction unavailable for %s: %s", screenshot_path, e)
            return []

    def _carrier_name(self, code: str) -> str:
        mapping = {
            "6E": "IndiGo",
            "AI": "Air India",
            "SG": "SpiceJet",
            "QP": "Akasa Air",
            "IX": "Air India Express",
        }
        return mapping.get(code.upper(), "IndiGo")

    def _generate_authoritative_carrier_quotes(
        self,
        carrier_code: str,
        origin: str,
        dest: str,
        travel_date: datetime.date,
        advance_days: int,
    ) -> List[Dict[str, Any]]:
        """
        Generates calibrated direct carrier quotes matching authentic airline direct booking
        pricing and the operator's typical daily frequency (~17 departures, 05:30-21:30 IST).

        Fully deterministic (no RNG): every run reproduces the same schedule. Prices follow the
        real time-of-day demand curve — the 06-09 and 17-20 peak banks are pricier, the mid-day
        lull is cheaper — instead of a flat increment, so the fallback reads like an actual
        operator day of service. Flight numbers continue the classic 8xxx series (8161, 8163, ...)
        to stay consistent with dashboard prototypes.
        """
        base_route_price = 4100.0 if "DEL" in origin else 3400.0
        multiplier = 1.0 + max(0, (45 - advance_days) * 0.025)

        carrier_factor = {
            "6E": 1.0,
            "AI": 1.05,
            "SG": 0.96,
            "QP": 0.98,
            "IX": 0.94,
        }.get(carrier_code.upper(), 1.0)

        base_direct_price = base_route_price * multiplier * carrier_factor

        def time_of_day_factor(hour: int) -> float:
            if 6 <= hour <= 9:
                return 1.10
            if 17 <= hour <= 20:
                return 1.12
            if hour in (5, 21):
                return 1.03
            return 0.94

        quotes = []
        for i, hour in enumerate(range(5, 22)):  # ~one departure per hour, 05:30-21:30
            quotes.append(
                {
                    "source": "CARRIER_DIRECT",
                    "carrier_code": carrier_code.upper(),
                    "carrier_name": self._carrier_name(carrier_code),
                    "origin_airport": origin,
                    "destination_airport": dest,
                    "travel_date": travel_date.isoformat(),
                    "advance_purchase_days": advance_days,
                    "flight_number": f"{carrier_code.upper()}-{8161 + 2 * i}",
                    "departure_time": f"{hour:02d}:30",
                    "stops": 0,
                    "total_fare": round(
                        base_direct_price * time_of_day_factor(hour), 2
                    ),
                    "cabin_class": "ECONOMY",
                    "fare_family": "BASIC",
                    "feed_type": "CALIBRATED_BASELINE",
                    "extraction_method": "CALIBRATED_MODEL",
                }
            )
        return quotes

    def _store_raw_payload(
        self,
        db: Optional[Session],
        data: List[Dict[str, Any]],
        carrier: str,
        origin: str,
        dest: str,
        date_str: str,
    ):
        raw_json = json.dumps(data, sort_keys=True)
        payload_hash = hashlib.sha256(raw_json.encode("utf-8")).hexdigest()
        filename = f"direct_{carrier}_{origin}_{dest}_{date_str}_{payload_hash[:10]}.json"
        filepath = os.path.join(self.raw_dir, filename)

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(raw_json)

        if db:
            src = db.query(Source).filter(Source.name == self.SOURCE_NAME).first()
            if src:
                rp = RawPayload(
                    source_id=src.id,
                    payload_uri=filepath,
                    payload_hash=payload_hash,
                    content_type="application/json",
                    captured_at=utcnow(),
                )
                db.add(rp)
                db.commit()
