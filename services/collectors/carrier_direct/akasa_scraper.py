"""Akasa Air (QP) Direct Scraper."""

import datetime
import logging
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from services.collectors.carrier_direct.base_carrier_scraper import CarrierDirectScraper

logger = logging.getLogger(__name__)


class AkasaAirScraper(CarrierDirectScraper):
    """Akasa Air (QP) direct website scraper."""

    def __init__(self):
        super().__init__(
            carrier_code="QP",
            carrier_name="Akasa Air",
            domain="akasaair.com",
            ndc_endpoint=None,
        )
        self.standard_convenience_fee = 0.0

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
                url = f"https://www.akasaair.com/booking?origin={origin_airport}&destination={destination_airport}&departureDate={travel_date.isoformat()}&adults=1"
                await page.goto(url, wait_until="networkidle", timeout=30000)
                await page.wait_for_selector('[data-testid="flight-card"]', timeout=15000)

                quotes = []
                flight_cards = await page.query_selector_all('[data-testid="flight-card"]')
                for card in flight_cards[:10]:
                    try:
                        flight_data = await self._extract_flight_card(card)
                        if flight_data:
                            quotes.append(flight_data)
                    except Exception as e:
                        logger.warning(f"Failed to extract Akasa flight card: {e}")
                return quotes

            return pool.run_browser(_scrape)
        except Exception:
            logger.warning("Browser pool unavailable for Akasa Air")
            return []

    def _generate_calibrated_quotes(
        self,
        origin_airport: str,
        destination_airport: str,
        travel_date: datetime.date,
        advance_days: int,
    ) -> List[Dict[str, Any]]:
        base_tariffs = {
            "DEL-BOM": 2900.0,
            "DEL-BLR": 3300.0,
            "BOM-BLR": 2600.0,
            "DEL-CCU": 3100.0,
            "DEL-HYD": 3000.0,
            "BOM-MAA": 2800.0,
            "BLR-HYD": 2400.0,
            "DEL-MAA": 3400.0,
            "DEL-IXS": 4600.0,
            "DEL-DHM": 4300.0,
        }
        corridor_base = base_tariffs.get(f"{origin_airport}-{destination_airport}", 3000.0)

        h_mult = {1: 2.2, 7: 1.55, 14: 1.0, 30: 0.91, 45: 0.84}.get(advance_days, 1.0)
        route_price = corridor_base * h_mult

        flights_schedule = [
            {"carrier": "QP", "fno": "QP-1102", "dep": "07:00", "arr": "09:15", "mod": 1.00},
            {"carrier": "QP", "fno": "QP-1305", "dep": "11:30", "arr": "13:45", "mod": 1.05},
            {"carrier": "QP", "fno": "QP-1567", "dep": "16:00", "arr": "18:15", "mod": 1.02},
            {"carrier": "QP", "fno": "QP-1890", "dep": "20:30", "arr": "22:45", "mod": 0.96},
        ]

        quotes = []
        for fl in flights_schedule:
            base = round(route_price * fl["mod"], 2)
            fuel = round(base * 0.17, 2)
            gst = round(base * 0.05, 2)
            total = round(base + fuel + 350.0 + gst, 2)

            quotes.append({
                "source_id": 5,
                "source_name": "Akasa Air Direct",
                "source_domain": "akasaair.com",
                "carrier_code": "QP",
                "carrier_name": "Akasa Air",
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
                "convenience_fee": 0.0,
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
