"""Carrier Direct Scrapers Package."""

from typing import List

from services.collectors.carrier_direct.airindia_scraper import AirIndiaScraper
from services.collectors.carrier_direct.akasa_scraper import AkasaAirScraper
from services.collectors.carrier_direct.indigo_scraper import IndiGoScraper
from services.collectors.carrier_direct.spicejet_scraper import SpiceJetScraper

__all__ = [
    "IndiGoScraper",
    "AirIndiaScraper",
    "SpiceJetScraper",
    "AkasaAirScraper",
]


def get_all_carrier_scrapers() -> List:
    """Returns list of all carrier direct scraper instances."""
    return [
        IndiGoScraper(),
        AirIndiaScraper(),
        SpiceJetScraper(),
        AkasaAirScraper(),
    ]
