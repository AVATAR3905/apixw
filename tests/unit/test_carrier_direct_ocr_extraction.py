"""Regression tests for the carrier-direct OCR fallback's multi-flight extraction.

Before this fix, `_extract_via_ocr` called `AdaptiveExtractor.extract()` for a
single field-set and wrapped it in a one-element list, so a results page with
N real flights always collapsed to at most 1 observation whenever the primary
JSON/DOM parser failed and OCR took over. It now reuses the same multi-card
extraction (`card_extraction.extract_cards_from_screenshot`) the OTA scrapers
rely on, so N cards on the screenshot yield N observations.
"""

from unittest.mock import patch

from services.collectors.carrier_direct_scraper import CarrierDirectScraper


def _card(price, flight_number=None, **extra):
    card = {"price": price}
    if flight_number:
        card["flight_number"] = flight_number
    card.update(extra)
    return card


def test_ocr_fallback_returns_one_quote_per_card():
    scraper = CarrierDirectScraper()
    cards = [
        _card(4500, "SG-8161", departure_time="06:30"),
        _card(5200, "SG-8163", departure_time="09:30"),
        _card(6100, "SG-8165", departure_time="18:30"),
    ]
    with patch(
        "services.collectors.ota.card_extraction.extract_cards_from_screenshot",
        return_value=cards,
    ):
        quotes = scraper._extract_via_ocr(
            carrier_code="SG",
            origin="DEL",
            dest="BOM",
            date_str="2026-10-15",
            advance_days=15,
            screenshot_path="fake_screenshot.png",
        )

    assert len(quotes) == 3
    assert {q["total_fare"] for q in quotes} == {4500.0, 5200.0, 6100.0}
    assert {q["flight_number"] for q in quotes} == {"SG-8161", "SG-8163", "SG-8165"}
    assert all(q["feed_type"] == "CARRIER_DIRECT" for q in quotes)


def test_ocr_fallback_skips_cards_without_a_price():
    scraper = CarrierDirectScraper()
    cards = [_card(4500, "SG-8161"), {"flight_number": "SG-8163"}, _card(6100, "SG-8165")]
    with patch(
        "services.collectors.ota.card_extraction.extract_cards_from_screenshot",
        return_value=cards,
    ):
        quotes = scraper._extract_via_ocr(
            carrier_code="SG",
            origin="DEL",
            dest="BOM",
            date_str="2026-10-15",
            advance_days=15,
            screenshot_path="fake_screenshot.png",
        )

    assert len(quotes) == 2
    assert {q["flight_number"] for q in quotes} == {"SG-8161", "SG-8165"}


def test_ocr_fallback_returns_empty_list_when_no_screenshot():
    scraper = CarrierDirectScraper()
    quotes = scraper._extract_via_ocr(
        carrier_code="SG",
        origin="DEL",
        dest="BOM",
        date_str="2026-10-15",
        advance_days=15,
        screenshot_path=None,
    )
    assert quotes == []


def test_ocr_fallback_returns_empty_list_when_no_cards_found():
    scraper = CarrierDirectScraper()
    with patch(
        "services.collectors.ota.card_extraction.extract_cards_from_screenshot",
        return_value=[],
    ):
        quotes = scraper._extract_via_ocr(
            carrier_code="SG",
            origin="DEL",
            dest="BOM",
            date_str="2026-10-15",
            advance_days=15,
            screenshot_path="fake_screenshot.png",
        )
    assert quotes == []
