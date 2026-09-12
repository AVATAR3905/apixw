"""Unified Multi-Source Orchestrator: Flight Carriers & Top 6 OTAs.

Executes concurrent collection across:
1. Flight Carrier Official Portals: IndiGo (6E), Air India (AI), SpiceJet (SG), Akasa Air (QP)
2. Top 6 Indian OTAs: MakeMyTrip, Ixigo, EaseMyTrip, Yatra, Cleartrip, Skyscanner India
"""

import datetime
import logging
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from services.collectors.carrier_direct_scraper import CarrierDirectScraper
from services.collectors.ota.cleartrip_scraper import CleartripScraper
from services.collectors.ota.easemytrip_scraper import EaseMyTripScraper
from services.collectors.ota.ixigo_scraper import IxigoScraper
from services.collectors.ota.makemytrip_scraper import MakeMyTripScraper
from services.collectors.ota.skyscanner_scraper import SkyscannerScraper
from services.collectors.ota.yatra_scraper import YatraScraper

logger = logging.getLogger(__name__)


class MultiSourceFlightOrchestrator:
    """Orchestrates comprehensive scraping across airlines and OTAs."""

    def __init__(self):
        self.carrier_scraper = CarrierDirectScraper()
        self.ota_scrapers = [
            MakeMyTripScraper(),
            IxigoScraper(),
            EaseMyTripScraper(),
            YatraScraper(),
            CleartripScraper(),
            SkyscannerScraper(),
        ]

    def collect_corridor_all_sources(
        self,
        route_code: str = "DEL-BOM",
        advance_days: int = 14,
        search_date: Optional[datetime.date] = None,
        db: Optional[Session] = None,
    ) -> Dict[str, Any]:
        """
        Executes end-to-end collection across all carriers and OTAs for a corridor and horizon.
        """
        if search_date is None:
            search_date = datetime.date.today()

        travel_date = search_date + datetime.timedelta(days=advance_days)
        parts = route_code.upper().split("-")
        origin, dest = parts[0], parts[1]

        all_quotes: List[Dict[str, Any]] = []
        carrier_quotes: List[Dict[str, Any]] = []
        ota_quotes_by_source: Dict[str, List[Dict[str, Any]]] = {}

        # 1. Scrape Direct Carriers (IndiGo, Air India, SpiceJet, Akasa Air)
        logger.info(f"Collecting direct carrier quotes for {route_code} (T+{advance_days})...")
        for carrier_code in ["6E", "AI", "SG", "QP"]:
            try:
                c_res = self.carrier_scraper.scrape_carrier_corridor(
                    carrier_code=carrier_code,
                    origin_airport=origin,
                    destination_airport=dest,
                    advance_days=advance_days,
                    search_date=search_date,
                    db=db,
                )
                # Attach source metadata only; never fabricate fares or schedules here.
                for q in c_res:
                    c_name = q.get("carrier_name", carrier_code)
                    q["source_id"] = 5
                    q["source_name"] = q.get("source_name", f"Carrier Direct ({c_name})")
                    q["source_domain"] = q.get(
                        "source_domain", f"{carrier_code.lower()}.airline.direct"
                    )
                    q["extraction_method"] = q.get(
                        "extraction_method",
                        "CALIBRATED_MODEL"
                        if q.get("feed_type") == "CALIBRATED_BASELINE"
                        else "DOM_BROWSER",
                    )

                carrier_quotes.extend(c_res)
                all_quotes.extend(c_res)
            except Exception as e:
                logger.error(f"Carrier scrape failed for {carrier_code}: {e}")

        # NOTE: No common-schedule or fare-decomposition fabrication is injected here.
        # Cross-flight comparability relies on real flight-number overlap across platforms.

        # 2. Scrape All 6 OTAs
        for ota in self.ota_scrapers:
            logger.info(f"Collecting from {ota.source_name} for {route_code}...")
            try:
                o_res = ota.scrape_corridor(
                    origin_airport=origin,
                    destination_airport=dest,
                    travel_date=travel_date,
                    advance_days=advance_days,
                    db=db,
                )
                ota_quotes_by_source[ota.source_name] = o_res
                all_quotes.extend(o_res)
            except Exception as e:
                logger.error(f"OTA scrape failed for {ota.source_name}: {e}")
                ota_quotes_by_source[ota.source_name] = []

        return {
            "route_code": route_code,
            "origin": origin,
            "destination": dest,
            "search_date": search_date.isoformat(),
            "travel_date": travel_date.isoformat(),
            "advance_days": advance_days,
            "total_quotes_collected": len(all_quotes),
            "carrier_quotes_count": len(carrier_quotes),
            "carrier_quotes": carrier_quotes,
            "ota_quotes_by_source": ota_quotes_by_source,
            "all_quotes": all_quotes,
        }
