"""Unit tests for the adaptive extraction chain (DOM first, OCR, VLM last)."""

import datetime

from services.extraction.adaptive_extractor import (
    AdaptiveExtractor,
    ExtractionContext,
    extract_date_fields,
)
from services.extraction.layout_clusterer import OCRToken
from services.extraction.ocr_service import ExtractionNotAvailable
from services.extraction.vlm_service import VLMNotConfigured


class _NoOPOCR:
    def extract(self, image_path):
        raise ExtractionNotAvailable("not installed")


class _FakeOCR:
    def __init__(self, tokens):
        self._tokens = tokens
        self.called = False

    def extract(self, image_path):
        self.called = True
        return self._tokens


class _FakeVLM:
    def __init__(self, fields=None, raises=False):
        self.fields = fields or {}
        self.raises = raises

    def extract_fields(self, image_path, prompt, schema):
        if self.raises:
            raise VLMNotConfigured("no backend")
        return self.fields


def test_dom_price_short_circuits_before_ocr_and_vlm():
    ocr = _FakeOCR([])
    vlm = _FakeVLM()
    extractor = AdaptiveExtractor(ocr=ocr, vlm=vlm)
    result = extractor.extract(ExtractionContext(dom_text=["06:00", "₹4,500", "6E-205"]))
    assert result.extraction_method == "DOM_BROWSER"
    assert result.fields["price"] == 4500.0
    assert result.chain == ["DOM"]
    assert ocr.called is False


def test_ocr_path_resolves_price_from_pixel_tokens():
    tokens = [OCRToken("₹3,540", bbox=[0, 0, 100, 30])]
    ocr = _FakeOCR(tokens)
    extractor = AdaptiveExtractor(ocr=ocr, vlm=_FakeVLM(raises=True))
    result = extractor.extract(ExtractionContext(image_path="screenshot.png"))
    assert result.fields["price"] == 3540.0
    assert result.extraction_method == "OCR"
    assert "OCR" in result.chain
    assert ocr.called is True


def test_vlm_resolves_missing_origin_when_ocr_has_price():
    tokens = [OCRToken("₹3,540", bbox=[0, 0, 100, 30])]
    ocr = _FakeOCR(tokens)
    vlm = _FakeVLM(fields={"origin": "DEL", "destination": "BOM"})
    extractor = AdaptiveExtractor(ocr=ocr, vlm=vlm)
    result = extractor.extract(ExtractionContext(image_path="screenshot.png"))
    assert result.fields["origin"] == "DEL"
    assert "VLM" in result.chain


def test_ocr_route_and_price_skips_vlm_backend():
    tokens = [
        OCRToken("DEL -> BOM", bbox=[0, 0, 200, 30]),
        OCRToken("INR 3,540", bbox=[0, 40, 180, 70]),
    ]
    ocr = _FakeOCR(tokens)
    vlm = _FakeVLM(raises=True)
    extractor = AdaptiveExtractor(ocr=ocr, vlm=vlm)
    result = extractor.extract(ExtractionContext(image_path="screenshot.png"))
    assert result.fields["origin"] == "DEL"
    assert result.fields["destination"] == "BOM"
    assert result.extraction_method == "OCR"
    assert "VLM" not in result.chain
    assert "VLM_SKIPPED" not in result.chain


def test_no_fields_resolves_to_none():
    extractor = AdaptiveExtractor(ocr=_NoOPOCR(), vlm=_FakeVLM(raises=True))
    result = extractor.extract(ExtractionContext(image_path="blank.png"))
    assert result.fields == {}
    assert result.extraction_method == "NONE"
    assert result.confidence == 0.0
    assert "OCR_SKIPPED" in result.chain
    assert "VLM_SKIPPED" in result.chain


def test_iso_travel_and_return_dates():
    fields = extract_date_fields("Depart 2026-09-15 Return 2026-09-22")
    assert fields.get("travel_date") == "2026-09-15"
    assert fields.get("return_date") == "2026-09-22"


def test_day_month_year_date():
    fields = extract_date_fields("15 Sep 2026")
    assert fields.get("travel_date") == "2026-09-15"


def test_month_day_year_date():
    fields = extract_date_fields("Sep 15, 2026")
    assert fields.get("travel_date") == "2026-09-15"


def test_yearless_date_resolves_within_forward_window():
    # Reference date 2026-09-10: "12 Sep" falls inside the +60d window -> 2026.
    fields = extract_date_fields("12 Sep", reference_date="2026-09-10")
    assert fields.get("travel_date") == "2026-09-12"


def test_yearless_date_past_window_resolves_to_next_year():
    # Reference 2026-12-05: "10 Jan" is before it in 2026 -> resolved to the
    # forward window in 2027 (the _resolve_date next-year branch).
    fields = extract_date_fields("10 Jan", reference_date="2026-12-05")
    assert fields.get("travel_date") == "2027-01-10"


def test_full_record_from_dom_text():
    texts = [
        "DEL -> BOM",
        "6E 205",
        "09:30",
        "11:45",
        "Nonstop",
        "2h 15m",
        "₹3,540",
        "15 Sep 2026",
    ]
    fields = AdaptiveExtractor.fields_from_dom(texts, reference_date="2026-09-10")
    assert fields["price"] == 3540.0
    assert fields["origin"] == "DEL"
    assert fields["destination"] == "BOM"
    assert fields["airline"] == "6E"
    assert fields["airline_name"] == "IndiGo"
    assert fields["flight_number"] == "6E-205"
    assert fields["departure_time"] == "09:30"
    assert fields["arrival_time"] == "11:45"
    assert fields["stops"] == 0
    assert fields["duration_minutes"] == 135
    assert fields["travel_date"] == "2026-09-15"


def test_ocr_tokens_carry_full_record():
    tokens = [
        OCRToken("DEL -> BOM", bbox=[0, 0, 100, 30]),
        OCRToken("6E 205", bbox=[0, 35, 80, 65]),
        OCRToken("₹3,540", bbox=[0, 70, 100, 100]),
        OCRToken("12 Sep", bbox=[0, 105, 90, 135]),
    ]
    fields = AdaptiveExtractor.fields_from_tokens(tokens, reference_date="2026-09-10")
    assert fields["price"] == 3540.0
    assert fields["travel_date"] == "2026-09-12"


def test_reference_date_as_date_object():
    fields = extract_date_fields("12 Sep", reference_date=datetime.date(2026, 9, 10))
    assert fields.get("travel_date") == "2026-09-12"
