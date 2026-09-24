"""Shared multi-card fare extraction: DOM text first, OCR/VLM screenshot fallback.

OTA results pages render N fare cards per screenshot/page (unlike the
single-card crops the carrier-direct OCR fallback works on), so this reuses
the same field-parsing regexes as `AdaptiveExtractor` (`fields_from_dom`) but
applies them per-card instead of to one blob of text -- "the same method",
just fed multiple times. DOM text is tried first (cheapest, most trusted,
per the adaptive extractor's own precedence); a full-page screenshot run
through `OCRService` + `LayoutClusterer.cards()` is the genuine OCR/VLM
fallback when a site's markup doesn't yield clean per-card DOM text.
"""

import logging
from typing import Any, Dict, List, Optional

from services.extraction.adaptive_extractor import AdaptiveExtractor

logger = logging.getLogger(__name__)


def extract_cards_from_dom(
    page,
    card_selector: str,
    reference_date: Optional[str] = None,
    max_cards: int = 15,
) -> List[Dict[str, Any]]:
    """Locates each fare-card element and runs the shared field parser on its
    own text -- the DOM-first tier of the extraction chain.
    """
    cards: List[Dict[str, Any]] = []
    try:
        elements = page.locator(card_selector).all()
    except Exception as e:
        logger.warning("Card selector %r failed: %s", card_selector, e)
        return []

    for el in elements[:max_cards]:
        try:
            text = el.inner_text()
        except Exception:
            continue
        if not text:
            continue
        fields = AdaptiveExtractor.fields_from_dom([text], reference_date)
        if fields.get("price"):
            fields["_extraction_method"] = "DOM_BROWSER"
            cards.append(fields)
    return cards


def extract_cards_from_screenshot(
    image_path: str,
    reference_date: Optional[str] = None,
    allow_vlm: bool = False,
) -> List[Dict[str, Any]]:
    """OCR (+ optional VLM) fallback: clusters a full-page/results screenshot
    into per-card token groups and parses each cluster the same way.

    ``allow_vlm`` defaults off here: VLM is a per-image, single-card-shaped
    call (~100s local / ~2s cloud per invocation, see docs/PIPELINE_BENCHMARK.md
    §3b), so escalating it per fare-card on a 15-card results page would be
    far too slow for a live collection cycle. OCR alone (~1s for the whole
    page, per the same benchmark) is the right cost/accuracy tradeoff for
    a *list* of cards; VLM stays reserved for the single-card carrier-direct
    fallback it was designed for.
    """
    from services.extraction.layout_clusterer import LayoutClusterer
    from services.extraction.ocr_service import ExtractionNotAvailable, OCRService

    cards: List[Dict[str, Any]] = []
    try:
        tokens = OCRService().extract(image_path)
    except ExtractionNotAvailable as e:
        logger.warning("OCR unavailable for %s: %s", image_path, e)
        return []
    except Exception as e:
        logger.warning("OCR failed on %s: %s", image_path, e)
        return []

    for card in LayoutClusterer.cards(tokens):
        fields = AdaptiveExtractor.fields_from_dom([card["text"]], reference_date)
        if fields.get("price"):
            fields["_extraction_method"] = "OCR"
            cards.append(fields)

    if not cards and allow_vlm:
        # Whole-page VLM is intentionally not attempted here (cost, see
        # docstring above); a caller that truly wants it can pass a
        # pre-cropped single-card image through AdaptiveExtractor directly.
        logger.info("OCR found no cards on %s; VLM escalation skipped for list pages.", image_path)

    return cards
