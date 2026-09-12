"""SpiceJet (SG) Direct Scraper."""

import datetime
import logging
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from services.collectors.carrier_direct.base_carrier_scraper import CarrierDirectScraper

logger = logging.getLogger(__name__)


class SpiceJetScraper(CarrierDirectScraper):
    """SpiceJet (SG) direct website scraper."""

    def __init__(self):
        super().__init__(
            carrier_code="SG",
            carrier_name="SpiceJet",
            domain="spicejet.com",
            ndc_endpoint=None,  # No NDC yet
        )
        self.standard_convenience_fee = 250.0

    def _scrape_via_ndc(self, *args, **kwargs) -> List[Dict[str, Any]]:
        return []

    def _scrape_via_browser(
        self,
        origin_airport: str,
        destination_airport: str,
        travel_date: datetime.date,
        advance_days: int,
        db: Optional[Session],
    ) -> List[Dict[str, Any]]:
        from services.collectors.browser_pool import get_browser_pool

        pool = get_browser_pool()
        try:
            async def _scrape(context):
                page = await context.new_page()
                url = f"https://www.spicejet.com/booking?origin={origin_airport}&destination={destination_airport}&departureDate={travel_date.isoformat()}&adults=1"
                await page.goto(url, wait_until="networkidle", timeout=30000)
                await page.wait_for_selector('.flight-card', timeout=15000)

                quotes = []
                flight_cards = await page.query_selector_all('.flight-card')
                for card in flight_cards[:10]:
                    try:
                        flight_data = await self._extract_flight_card(card)
                        if flight_data:
                            quotes.append(flight_data)
                    except Exception as e:
                        logger.warning(f"Failed to extract SpiceJet flight card: {e}")
                return quotes

            return pool.run_browser(_scrape)
        except Exception:
            logger.warning("Browser pool unavailable for SpiceJet")
            return []

    def _generate_calibrated_quotes(
        self,
        origin_airport: str,
        destination_airport: str,
        travel_date: datetime.date,
        advance_days: int,
    ) -> List[Dict[str, Any]]:
        base_tariffs = {
            "DEL-BOM": 2600.0,
            "DEL-BLR": 3000.0,
            "BOM-BLR": 2300.0,
            "DEL-CCU": 2900.0,
            "DEL-HYD": 2700.0,
            "BOM-MAA": 2600.0,
            "BLR-HYD": 2200.0,
            "DEL-MAA": 3100.0,
            "DEL-IXS": 4200.0,
            "DEL-DHM": 3900.0,
        }
        corridor_base = base_tariffs.get(f"{origin_airport}-{destination_airport}", 2800.0)

        h_mult = {1: 2.5, 7: 1.7, 14: 1.0, 30: 0.88, 45: 0.8}.get(advance_days, 1.0)
        route_price = corridor_base * h_mult

        flights_schedule = [
            {"carrier": "SG", "fno": "SG-8169", "dep": "06:30", "arr": "08:45", "mod": 1.00},
            {"carrier": "SG", "fno": "SG-173", "dep": "10:15", "arr": "12:30", "mod": 1.08},
            {"carrier": "SG", "fno": "SG-298", "dep": "14:45", "arr": "17:00", "mod": 1.05},
            {"carrier": "SG", "fno": "SG-412", "dep": "19:20", "arr": "21:35", "mod": 0.97},
        ]

        quotes = []
        for fl in flights_schedule:
            base = round(route_price * fl["mod"], 2)
            fuel = round(base * 0.18, 2)
            gst = round(base * 0.05, 2)
            total = round(base + fuel + 350.0 + gst + 250.0, 2)

            quotes.append({
                "source_id": 5,
                "source_name": "SpiceJet Direct",
                "source_domain": "spicejet.com",
                "carrier_code": "SG",
                "carrier_name": "SpiceJet",
                "flight_number": fl["fno"],
                "origin_airport": origin_airport,
                "destination_airport": destination_airport,
                "travel_date": travel_date.isoformat(),
                "departure_time": fl["dep"],
                "arrival_time": fl["arr"],
                "advance_purchase_days": advance_days,
                "base_fare": base,
                "fuel_surcharge": fuel,
                "udf_adf": 350.0,
                "gst_taxes": gst,
                "convenience_fee": 250.0,
                "promotional_discount": 0.0,
                "total_fare": total,
                "cabin_class": "ECONOMY",
                "fare_family": "BASIC",
                "is_unconditional": True,
                "is_sold_out": False,
                "extraction_method": "CALIBRATED_MODEL",
                "feed_type": "CALIBRATED_BASELINE",
            })

        return quotes
