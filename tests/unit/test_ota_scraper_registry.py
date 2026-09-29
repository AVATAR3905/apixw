"""Unit tests for the OTA scraper registry (services/collectors/ota/registry.py).

This is the mechanism that lets a new, permitted OTA be onboarded by writing
a scraper class + approving its `sources` row, without editing
CollectionScheduler or MultiSourceFlightOrchestrator (PRD US-014).
"""

import pytest

from database.session import SessionLocal
from packages.schemas.models import Source
from services.collectors.ota.base_ota_scraper import BaseOTAScraper
from services.collectors.ota.registry import (
    _OTA_SCRAPER_REGISTRY,
    get_approved_ota_scrapers,
    get_registered_ota_scrapers,
    register_ota_scraper,
)

_FAKE_SOURCE_NAME = "Totally Fake OTA (test-only)"


class _FakeScraper(BaseOTAScraper):
    def __init__(self):
        super().__init__(source_id=999999, source_name=_FAKE_SOURCE_NAME, domain="fake-ota.test")

    def _execute_scrape(self, **kwargs):
        return []

    def _generate_calibrated_quotes(self, **kwargs):
        return []


@pytest.fixture
def isolated_registry(monkeypatch):
    """Registering a scraper mutates module-level state; keep tests isolated
    from each other and from whatever real scrapers are registered by import
    side effects elsewhere in the suite.
    """
    fake_registry = dict(_OTA_SCRAPER_REGISTRY)
    monkeypatch.setattr("services.collectors.ota.registry._OTA_SCRAPER_REGISTRY", fake_registry)
    return fake_registry


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        # Clean up only the exact test row this file creates -- never a broad
        # filter that could match real seeded sources (see CONTRIBUTING.md).
        session.query(Source).filter(Source.name == _FAKE_SOURCE_NAME).delete()
        session.commit()
        session.close()


def test_register_ota_scraper_adds_to_registry(isolated_registry):
    register_ota_scraper(_FAKE_SOURCE_NAME)(_FakeScraper)

    registered = get_registered_ota_scrapers()
    assert registered[_FAKE_SOURCE_NAME] is _FakeScraper


def test_get_approved_ota_scrapers_skips_missing_source_row(isolated_registry, db):
    register_ota_scraper(_FAKE_SOURCE_NAME)(_FakeScraper)

    # No matching `sources` row exists -> skipped silently, not an error.
    scrapers = get_approved_ota_scrapers(db)
    assert all(not isinstance(s, _FakeScraper) for s in scrapers)


def test_get_approved_ota_scrapers_skips_disabled_source(isolated_registry, db):
    register_ota_scraper(_FAKE_SOURCE_NAME)(_FakeScraper)

    db.add(
        Source(
            name=_FAKE_SOURCE_NAME,
            type="OTA",
            access_method="PLAYWRIGHT",
            permission_status="REVIEW_REQUIRED",
            enabled=False,
            access_mode="PUBLIC",
        )
    )
    db.commit()

    scrapers = get_approved_ota_scrapers(db)
    assert all(not isinstance(s, _FakeScraper) for s in scrapers)


def test_get_approved_ota_scrapers_includes_approved_enabled_source(isolated_registry, db):
    register_ota_scraper(_FAKE_SOURCE_NAME)(_FakeScraper)

    db.add(
        Source(
            name=_FAKE_SOURCE_NAME,
            type="OTA",
            access_method="PLAYWRIGHT",
            permission_status="APPROVED",
            enabled=True,
            access_mode="PUBLIC",
        )
    )
    db.commit()

    scrapers = get_approved_ota_scrapers(db)
    assert any(isinstance(s, _FakeScraper) for s in scrapers)
