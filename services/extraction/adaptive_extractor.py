"""Adaptive OBSERVE -> UNDERSTAND -> EXTRACT pipeline for fare cards.

Precedence is deterministic first, neural last:
1. DOM (element boxes + text from Playwright) — cheapest & most trusted.
2. OCR (PP-OCRv5) with geometry clustering for pixel-only surfaces.
3. VLM (PaddleOCR-VL / OpenRouter) only for fields neither stage resolved.

The reported ``extraction_method`` reflects the strongest stage actually used,
so downstream confidence scoring can discount weaker stages.

Every stage targets the same full field set so raw screenshots can be turned
into complete fare records: price, route, travel/return date, airline, flight
number, departure/arrival times, stops and duration.
"""

import datetime
import logging
import os
import re
from typing import Any, Dict, List, NamedTuple, Optional

from packages.statistics.confidence import METHOD_WEIGHTS
from services.extraction.layout_clusterer import LayoutClusterer, OCRToken
from services.extraction.ocr_service import ExtractionNotAvailable, OCRService
from services.extraction.vlm_service import VLMNotConfigured, VLMService

logger = logging.getLogger(__name__)

_PRICE_RE = re.compile(r"(?:INR|Rs\.?|₹|USD|\$)\s?([\d][\d,]*)")
_AIRPORTS_RE = re.compile(r"\b([A-Z]{3})\s*[-→>]{1,2}\s*([A-Z]{3})\b")
_FLIGHT_RE = re.compile(r"\b(?=[A-Z0-9]*[A-Z])([A-Z0-9]{2})-?\s*(\d{3,4})\b")
_TIME_RE = re.compile(r"\b([01]?\d|2[0-3]):([0-5]\d)\b")
_STOPS_RE = re.compile(r"\b(?:non-?stop|direct)\b|\b(\d)\s*[- ]?(?:stop|layover)[s]?\b", re.IGNORECASE)
_DURATION_RE = re.compile(
    r"\b(\d{1,2})\s*h\s*(?:(\d{1,2})\s*m)?\b|\b(\d{1,2})\s*(?:hr|hour)s?\b",
    re.IGNORECASE,
)

_MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}
_MONTH_RE = r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)"

# Date patterns tried in order; first match = travel date, second = return date.
_ISO_DATE_RE = re.compile(r"\b(20\d{2})[-/.](\d{1,2})[-/.](\d{1,2})\b")
_DD_MMM_YYYY_RE = re.compile(rf"\b(\d{{1,2}})\s+{_MONTH_RE}[a-z]*\.?[, ]\s*(20\d{{2}})\b", re.IGNORECASE)
_MMM_DD_YYYY_RE = re.compile(rf"\b{_MONTH_RE}[a-z]*\.?\s+(\d{{1,2}})[a-z]{{0,2}}[, ]\s*(20\d{{2}})\b", re.IGNORECASE)
_DD_MMM_RE = re.compile(rf"\b(\d{{1,2}})\s+{_MONTH_RE}[a-z]*\.?\b", re.IGNORECASE)
_MMM_DD_RE = re.compile(rf"\b{_MONTH_RE}[a-z]*\.?\s+(\d{{1,2}})[a-z]{{0,2}}\b", re.IGNORECASE)

_AIRLINE_NAMES = {
    "6E": "IndiGo",
    "AI": "Air India",
    "SG": "SpiceJet",
    "QP": "Akasa Air",
    "IX": "Air India Express",
    "UK": "Vistara",
    "I5": "Air India Express",
    "G8": "Go First",
}


class ExtractionContext(NamedTuple):
    dom_text: List[str] = []
    image_path: Optional[str] = None
    reference_date: Optional[str] = None  # queried travel date, "YYYY-MM-DD"


class ExtractionResult(NamedTuple):
    fields: Dict[str, Any]
    extraction_method: str
    confidence: float
    chain: List[str]


def _resolve_date(
    day: int, month: int, year: Optional[int], reference_date: Optional[datetime.date]
) -> str:
    """Normalize a parsed date to ISO; infer the year for year-less travel dates."""
    if year:
        try:
            return datetime.date(year, month, day).isoformat()
        except ValueError:
            return ""
    ref = reference_date or datetime.date.today()
    base = datetime.date(ref.year, month, day)
    if ref <= base <= ref + datetime.timedelta(days=60):
        return base.isoformat()
    base_ny = datetime.date(ref.year + 1, month, day)
    if ref <= base_ny <= ref + datetime.timedelta(days=60):
        return base_ny.isoformat()
    return base.isoformat()


def extract_date_fields(text: str, reference_date: Optional[str | datetime.date] = None) -> Dict[str, Any]:
    """Pull travel/return dates out of a fare-card text blob.

    Returns ``{"travel_date": "...", "return_date": "...", "travel_date_raw": "...",
    "return_date_raw": "..."}`` for every date the card actually shows.
    """
    ref: Optional[datetime.date] = None
    if reference_date:
        if isinstance(reference_date, datetime.date):
            ref = reference_date
        else:
            try:
                ref = datetime.date.fromisoformat(str(reference_date))
            except ValueError:
                ref = None

    matches: List[tuple] = []
    raw_hits: List[tuple] = []  # (start, raw, parsed)
    for pattern, explicit in (
        (_ISO_DATE_RE, True),
        (_DD_MMM_YYYY_RE, True),
        (_MMM_DD_YYYY_RE, True),
        (_DD_MMM_RE, False),
        (_MMM_DD_RE, False),
    ):
        for m in pattern.finditer(text):
            if pattern is _ISO_DATE_RE:
                y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
                raw_hits.append((m.start(), m.group(0), (d, mo, y)))
            elif pattern is _DD_MMM_YYYY_RE or pattern is _DD_MMM_RE:
                d, mo, y = int(m.group(1)), _MONTHS[m.group(2).lower()], None
                if explicit:
                    y = int(m.group(3))
                raw_hits.append((m.start(), m.group(0), (d, mo, y)))
            else:  # MMM d, yyyy | MMM d
                mo = _MONTHS[m.group(1).lower()]
                d = int(m.group(2))
                y = int(m.group(3)) if explicit else None
                raw_hits.append((m.start(), m.group(0), (d, mo, y)))

    raw_hits.sort(key=lambda t: t[0])
    for _, raw, (d, mo, y) in raw_hits:
        iso = _resolve_date(d, mo, y, ref)
        if iso:
            matches.append((raw, iso))

    fields: Dict[str, Any] = {}
    if len(matches) >= 1:
        fields["travel_date"] = matches[0][1]
        fields["travel_date_raw"] = matches[0][0]
    if len(matches) >= 2:
        fields["return_date"] = matches[1][1]
        fields["return_date_raw"] = matches[1][0]
    return fields


def _env_flag(name: str, default: bool) -> bool:
    """Read a live env override (set at runtime) ahead of the settings singleton."""
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


class AdaptiveExtractor:
    """Runs the extraction chain and reports the strongest method used."""

    def __init__(
        self,
        ocr: Optional[OCRService] = None,
        vlm: Optional[VLMService] = None,
        layout: Optional[LayoutClusterer] = None,
        allow_vlm: Optional[bool] = None,
        allow_ocr: Optional[bool] = None,
    ):
        from packages.shared.config import settings

        if allow_vlm is None:
            allow_vlm = _env_flag("EXTRACTION_ALLOW_VLM", settings.EXTRACTION_ALLOW_VLM)
        if allow_ocr is None:
            allow_ocr = _env_flag("EXTRACTION_ALLOW_OCR", settings.EXTRACTION_ALLOW_OCR)

        self.ocr = ocr or OCRService()
        self.vlm = vlm or VLMService()
        self.layout = layout or LayoutClusterer()
        self.allow_vlm = allow_vlm
        self.allow_ocr = allow_ocr

    @staticmethod
    def _parse_price(text: str) -> Optional[float]:
        match = _PRICE_RE.search(text)
        if not match:
            return None
        try:
            return float(match.group(1).replace(",", ""))
        except ValueError:
            return None

    @classmethod
    def fields_from_dom(cls, texts: List[str], reference_date: Optional[str] = None) -> Dict[str, Any]:
        """Deterministic full-record extraction from DOM text."""
        joined = " ".join(texts)

        fields: Dict[str, Any] = {}
        prices = [cls._parse_price(t) for t in texts]
        prices = [p for p in prices if p is not None]
        if prices:
            fields["price"] = min(prices)

        airports = _AIRPORTS_RE.search(joined)
        if airports:
            fields["origin"], fields["destination"] = airports.groups()

        flight = _FLIGHT_RE.search(joined)
        if flight:
            code = flight.group(1).upper()
            fields["flight_number"] = f"{code}-{flight.group(2)}"
            if code in _AIRLINE_NAMES:
                fields["airline"] = code
                fields["airline_name"] = _AIRLINE_NAMES[code]

        times = _TIME_RE.findall(joined)
        if len(times) >= 1:
            fields["departure_time"] = f"{times[0][0]}:{times[0][1]}"
        if len(times) >= 2:
            fields["arrival_time"] = f"{times[1][0]}:{times[1][1]}"

        stops = _STOPS_RE.search(joined)
        if stops:
            if stops.group(1):
                fields["stops"] = int(stops.group(1))
            else:
                fields["stops"] = 0

        duration = _DURATION_RE.search(joined)
        if duration:
            if duration.group(1):
                fields["duration_minutes"] = int(duration.group(1)) * 60 + int(duration.group(2) or 0)
            elif duration.group(3):
                fields["duration_minutes"] = int(duration.group(3)) * 60

        fields.update(extract_date_fields(joined, reference_date))
        return fields

    @classmethod
    def fields_from_tokens(cls, tokens: List[OCRToken], reference_date: Optional[str] = None) -> Dict[str, Any]:
        texts = [t.text for t in tokens]
        return cls.fields_from_dom(texts, reference_date)

    def extract(self, context: ExtractionContext) -> ExtractionResult:
        chain: List[str] = []
        ref = context.reference_date

        # 1. DOM state
        dom_fields = self.fields_from_dom(context.dom_text or [], ref)
        if dom_fields.get("price") is not None:
            return ExtractionResult(dom_fields, "DOM_BROWSER", 0.95, ["DOM"])

        # 2. OCR geometry
        ocr_fields: Dict[str, Any] = {}
        if context.image_path and self.allow_ocr:
            chain.append("OCR")
            try:
                tokens = self.ocr.extract(context.image_path)
                ocr_fields = self.fields_from_tokens(tokens, ref)
            except ExtractionNotAvailable:
                chain.append("OCR_SKIPPED")
        elif not self.allow_ocr:
            chain.append("OCR_SKIPPED")

        # 3. VLM fallback for missing fields
        vlm_used = False
        if (
            self.allow_vlm
            and context.image_path
            and (not ocr_fields.get("price") or not ocr_fields.get("origin"))
        ):
            chain.append("VLM")
            try:
                schema = {
                    "origin": "IATA",
                    "destination": "IATA",
                    "price": "INR",
                    "travel_date": "ISO date (YYYY-MM-DD)",
                    "return_date": "ISO date (YYYY-MM-DD)",
                    "airline": "IATA code",
                    "flight_number": "e.g. 6E-101",
                    "departure_time": "HH:MM",
                    "arrival_time": "HH:MM",
                    "stops": "integer",
                    "duration_minutes": "integer",
                }
                vlm_fields = self.vlm.extract_fields(
                    context.image_path,
                    "Extract the cheapest fare's origin, destination, total price, travel date,"
                    " return date, airline, flight number, departure/arrival times, stops and duration.",
                    schema,
                )
                ocr_fields.update(vlm_fields)
                vlm_used = True
            except VLMNotConfigured:
                chain.append("VLM_SKIPPED")

        fields = {**dom_fields, **ocr_fields}
        if not fields:
            return ExtractionResult({}, "NONE", 0.0, chain)
        method = "OCR" if context.image_path else "DOM_BROWSER"
        if vlm_used and not fields.get("origin"):
            method = "VLM"
        confidence = METHOD_WEIGHTS.get(method.upper(), 0.5)
        return ExtractionResult(fields, method, confidence, chain)
