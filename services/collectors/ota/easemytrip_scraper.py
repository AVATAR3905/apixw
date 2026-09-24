"""EaseMyTrip (easemytrip.com) Flight Scraper & Data Adapter.

Real search: unlike the TLS-blocked sites, easemytrip.com loads and searches
normally. Its homepage defaults to DEL->BOM with no popup to dismiss, so the
form flow is the simplest of the OTAs done this round -- verified live:
real IndiGo/Air India Express flights and prices rendered straight into the
DOM after submitting a real date + clicking the real search input. Extraction
reuses `card_extraction.py` (DOM per card, OCR screenshot fallback), same as
Ixigo.
"""

import datetime
import logging
import re
from typing import Any, Dict, List

from services.collectors.ota.base_ota_scraper import BaseOTAScraper
from services.collectors.ota.card_extraction import (
    extract_cards_from_dom,
    extract_cards_from_screenshot,
)

logger = logging.getLogger(__name__)

# City names EaseMyTrip's "FROM"/"TO" autocomplete indexes on. Verified live
# for DEL/BOM (the page's own default); others follow the same
# type-then-click-first-suggestion pattern but weren't individually confirmed.
_EMT_CITY_NAMES = {
    "DEL": "Delhi", "BOM": "Mumbai", "BLR": "Bengaluru", "CCU": "Kolkata",
    "HYD": "Hyderabad", "MAA": "Chennai", "IXS": "Silchar", "DHM": "Dharamsala",
}

_CARRIER_CODES = {
    "spicejet": "SG", "indigo": "6E", "air india": "AI", "akasa": "QP",
    "air india express": "IX", "akasaair": "QP",
}


class EaseMyTripScraper(BaseOTAScraper):
    """Scrapes EaseMyTrip domestic flight quotes. Highlights Zero Convenience Fee baseline."""

    def __init__(self):
        super().__init__(
            source_id=9,
            source_name="EaseMyTrip",
            domain="easemytrip.com",
            standard_convenience_fee=0.0,  # EMT zero convenience fee promotion
        )

    def _execute_scrape(
        self,
        origin_airport: str,
        destination_airport: str,
        travel_date: datetime.date,
        advance_days: int,
    ) -> List[Dict[str, Any]]:
        try:
            quotes = self._scrape_emt_interactive(
                origin_airport, destination_airport, travel_date, advance_days
            )
            if quotes:
                return quotes
        except Exception as e:
            logger.warning("EaseMyTrip interactive scrape failed: %s", e)
        return []  # base class falls back to the calibrated baseline

    def _scrape_emt_interactive(
        self,
        origin_airport: str,
        destination_airport: str,
        travel_date: datetime.date,
        advance_days: int,
    ) -> List[Dict[str, Any]]:
        origin_name = _EMT_CITY_NAMES.get(origin_airport.upper())
        dest_name = _EMT_CITY_NAMES.get(destination_airport.upper())
        if not origin_name or not dest_name:
            return []

        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True, args=["--disable-blink-features=AutomationControlled"]
            )
            try:
                context = browser.new_context(
                    user_agent=(
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
                    ),
                    viewport={"width": 1280, "height": 1000},
                )
                page = context.new_page()
                page.goto(
                    "https://www.easemytrip.com/", wait_until="domcontentloaded", timeout=20000
                )
                page.wait_for_timeout(2500)

                if not self._fill_emt_city(
                    page, "#FromSector_show", "#frmcity", origin_airport, origin_name
                ):
                    return []
                if not self._fill_emt_city(
                    page, "#Editbox13_show", "#tocity", destination_airport, dest_name
                ):
                    return []

                page.locator("#ddate").click()
                page.wait_for_timeout(800)
                if not self._click_emt_calendar_date(page, travel_date):
                    return []
                page.wait_for_timeout(500)
                page.locator(".srchBtnSe").click()
                page.wait_for_timeout(13000)

                quotes = extract_cards_from_dom(
                    page, "div.nw_listing_bx", travel_date.isoformat()
                )
                extraction_method = "DOM_BROWSER"
                if not quotes:
                    import os
                    import tempfile

                    shot_path = os.path.join(
                        tempfile.gettempdir(), f"emt_{origin_airport}_{destination_airport}.png"
                    )
                    page.screenshot(path=shot_path, full_page=False)
                    quotes = extract_cards_from_screenshot(shot_path, travel_date.isoformat())
                    extraction_method = "OCR"

                return self._to_raw_quotes(
                    quotes, origin_airport, destination_airport, travel_date,
                    advance_days, extraction_method,
                )
            finally:
                browser.close()

    @staticmethod
    def _fill_emt_city(
        page, input_sel: str, display_sel: str, iata_code: str, city_name: str
    ) -> bool:
        """Skips (no-op success) if the field already shows the target
        airport, e.g. ``#frmcity`` reading "FROM\\n\\n[DEL] Indira Gandhi...".
        """
        try:
            display = page.locator(display_sel)
            if display.count() and f"[{iata_code.upper()}]" in (display.inner_text() or ""):
                return True

            field = page.locator(input_sel)
            try:
                field.click(timeout=5000)
            except Exception:
                # A sibling overlay (e.g. #a_Editbox13_show inside
                # #toautoFill_in) sometimes intercepts the standard
                # actionability-checked click on the "To" field specifically --
                # same class of overlap already worked around for Cleartrip's
                # modal and Air India Express's calendar cells. A raw
                # coordinate click bypasses Playwright's interception check.
                box = field.bounding_box()
                if not box:
                    raise
                page.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
            page.wait_for_timeout(600)
            page.keyboard.type(city_name, delay=30)
            page.wait_for_timeout(1200)
            suggestion = page.get_by_text(city_name, exact=False).first
            try:
                suggestion.click(timeout=5000)
            except Exception:
                # Same overlay-interception issue as the field-open click above,
                # now on the suggestion row itself.
                box = suggestion.bounding_box()
                if not box:
                    raise
                page.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
            return True
        except Exception as e:
            logger.warning("easemytrip: could not select %s=%s: %s", input_sel, city_name, e)
            return False

    @staticmethod
    def _click_emt_calendar_date(page, target_date: datetime.date) -> bool:
        """Two-month calendar, day cells combine day-number + price text
        (``"7\\n₹6090"``) -- match by first line, disambiguate by position
        relative to the target month's header (same pattern as Akasa/Ixigo)."""
        # Match case-insensitively: Playwright's text engine matches raw DOM
        # textContent ("Oct 2026"), not the CSS text-transform:uppercase
        # rendering ("OCT 2026") that .inner_text() reports.
        month_label = target_date.strftime("%b %Y").upper()
        for _ in range(6):
            headers = page.get_by_text(re.compile(r"^[A-Za-z]{3} \d{4}$")).all()
            texts = [h.inner_text() for h in headers]
            texts_upper = [t.upper() for t in texts]
            if month_label in texts_upper:
                header = headers[texts_upper.index(month_label)]
                hbox = header.bounding_box()
                target_day = str(target_date.day)
                for li in page.locator("li").all():
                    txt = li.inner_text().strip()
                    if txt.split("\n")[0] != target_day:
                        continue
                    cb = li.bounding_box()
                    if cb and hbox and cb["y"] > hbox["y"] and abs(cb["x"] - hbox["x"]) < 260:
                        li.click()
                        return True
                return False
            advanced = False
            for btn in page.locator("button, [role=button], a").all():
                try:
                    if (btn.inner_text() or "").strip() in (">", "›", "→"):
                        btn.click()
                        advanced = True
                        break
                except Exception:
                    continue
            if not advanced:
                return False
            page.wait_for_timeout(400)
        return False

    def _to_raw_quotes(
        self,
        parsed_cards: List[Dict[str, Any]],
        origin_airport: str,
        destination_airport: str,
        travel_date: datetime.date,
        advance_days: int,
        extraction_method: str,
    ) -> List[Dict[str, Any]]:
        quotes = []
        for card in parsed_cards:
            price = card.get("price")
            if price is None or not (1500.0 <= price <= 60000.0):
                continue
            carrier_code = card.get("airline") or _CARRIER_CODES.get(
                (card.get("airline_name") or "").lower(), "6E"
            )
            quotes.append(
                {
                    "source_id": self.source_id,
                    "source_name": self.source_name,
                    "source_domain": self.domain,
                    "carrier_code": carrier_code,
                    "flight_number": card.get("flight_number") or f"{carrier_code}-101",
                    "origin_airport": origin_airport,
                    "destination_airport": destination_airport,
                    "travel_date": travel_date.isoformat(),
                    "departure_time": card.get("departure_time", "00:00"),
                    "arrival_time": card.get("arrival_time"),
                    "advance_purchase_days": advance_days,
                    "stops": card.get("stops", 0),
                    "total_fare": float(price),
                    "cabin_class": "ECONOMY",
                    "fare_family": "BASIC",
                    "is_unconditional": True,
                    "is_sold_out": False,
                    "extraction_method": extraction_method,
                }
            )
        return quotes

    def _generate_calibrated_quotes(
        self,
        origin_airport: str,
        destination_airport: str,
        travel_date: datetime.date,
        advance_days: int,
    ) -> List[Dict[str, Any]]:
        corridor = f"{origin_airport}-{destination_airport}"
        base_tariffs = {
            "DEL-BOM": 3000.0,
            "DEL-BLR": 3500.0,
            "BOM-BLR": 2800.0,
            "DEL-CCU": 3400.0,
            "DEL-HYD": 3200.0,
            "BOM-MAA": 3100.0,
            "BLR-HYD": 2600.0,
            "DEL-MAA": 3600.0,
            "DEL-IXS": 5200.0,
            "DEL-DHM": 4800.0,
        }
        corridor_base = base_tariffs.get(corridor, 3200.0)
        h_mult = {1: 2.04, 7: 1.45, 14: 1.00, 30: 0.94, 45: 0.88}.get(advance_days, 1.0)
        route_price = corridor_base * h_mult

        flights_schedule = [
            {"carrier": "6E", "fno": "6E-205", "dep": "06:00", "arr": "08:15", "mod": 1.00},
            {"carrier": "6E", "fno": "6E-532", "dep": "09:30", "arr": "11:45", "mod": 1.05},
            {"carrier": "AI", "fno": "AI-806", "dep": "11:00", "arr": "13:10", "mod": 1.15},
            {"carrier": "QP", "fno": "QP-1102", "dep": "14:15", "arr": "16:30", "mod": 0.95},
            {"carrier": "SG", "fno": "SG-8169", "dep": "18:45", "arr": "21:00", "mod": 0.93},
        ]

        quotes = []
        for fl in flights_schedule:
            base = round(route_price * fl["mod"], 2)
            fuel = round(base * 0.18, 2)
            udf = 350.0
            gst = round(base * 0.05, 2)
            conv_fee = 0.0  # Zero convenience fee feature
            discount = 0.0
            total = round(base + fuel + udf + gst + conv_fee, 2)

            quotes.append(
                {
                    "source_id": self.source_id,
                    "source_name": self.source_name,
                    "source_domain": self.domain,
                    "carrier_code": fl["carrier"],
                    "flight_number": fl["fno"],
                    "origin_airport": origin_airport,
                    "destination_airport": destination_airport,
                    "travel_date": travel_date.isoformat(),
                    "departure_time": fl["dep"],
                    "arrival_time": fl["arr"],
                    "advance_purchase_days": advance_days,
                    "base_fare": base,
                    "fuel_surcharge": fuel,
                    "udf_adf": udf,
                    "gst_taxes": gst,
                    "convenience_fee": conv_fee,
                    "promotional_discount": discount,
                    "total_fare": total,
                    "cabin_class": "ECONOMY",
                    "fare_family": "BASIC",
                    "is_unconditional": True,
                    "is_sold_out": False,
                }
            )

        return quotes
