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


@pytest.fixture
def carrier_direct_live_fake(monkeypatch):
    """Simulates a genuinely successful live carrier-direct extraction.

    Unlike ``carrier_baseline`` (which routes to the calibrated fallback and is
    correctly downgraded to ``is_synthetic=True`` / ``feed_type`` preserved as
    ``CALIBRATED_BASELINE``), this fixture stands in for a real DOM/JSON scrape
    that actually returned fares -- ``feed_type="CARRIER_DIRECT"`` -- so tests
    that verify the *genuine* real-data persistence path stay hermetic without
    depending on live network access.
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
        travel_date = search_date or datetime.date.today()
        base = self._generate_authoritative_carrier_quotes(
            carrier_code=carrier_code,
            origin=origin_airport,
            dest=destination_airport,
            travel_date=travel_date,
            advance_days=advance_days,
        )
        for q in base:
            q["feed_type"] = "CARRIER_DIRECT"
            q["extraction_method"] = "DOM_BROWSER"
        return base

    monkeypatch.setattr(cds_mod.CarrierDirectScraper, "scrape_carrier_corridor", fake)
    return cds_mod
