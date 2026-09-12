"""Shared pytest fixtures for the APIX test suite."""

import datetime

import pytest

from services.collectors import carrier_direct_scraper as cds_mod


@pytest.fixture
def carrier_baseline(monkeypatch):
    """Route carrier direct scraping to the calibrated baseline.

    Keeps carrier/OTA/collection tests hermetic: no real airline sites, browser,
    or model inference even when Chromium is installed (which would otherwise
    make tests drive live scraping for minutes).
    """

    def fake(
        self,
        carrier_code,
        origin_airport,
        destination_airport,
        advance_days,
        search_date=None,
        db=None,
    ):
        return self._generate_authoritative_carrier_quotes(
            carrier_code=carrier_code,
            origin=origin_airport,
            dest=destination_airport,
            travel_date=search_date or datetime.date.today(),
            advance_days=advance_days,
        )

    monkeypatch.setattr(cds_mod.CarrierDirectScraper, "scrape_carrier_corridor", fake)
    return cds_mod
