"""Unit tests for OCR token geometry clustering (fare-card banding)."""

from services.extraction.layout_clusterer import LayoutClusterer, OCRToken


def _tokens():
    # Two fare cards stacked vertically: each card = a row of choice boxes.
    card_a = [
        OCRToken("06:00", bbox=[10, 10, 60, 30]),
        OCRToken("₹3,540", bbox=[70, 10, 140, 30]),
        OCRToken("6E-205", bbox=[150, 10, 215, 30]),
    ]
    card_b = [
        OCRToken("09:30", bbox=[10, 90, 60, 110]),
        OCRToken("₹3,717", bbox=[70, 90, 140, 110]),
        OCRToken("6E-532", bbox=[150, 90, 215, 110]),
    ]
    return card_a + card_b


def test_cluster_by_vertical_banding():
    clusters = LayoutClusterer.cluster(_tokens())
    assert len(clusters) == 2
    assert all(len(c) == 3 for c in clusters)


def test_cards_produce_readable_text_in_read_order():
    cards = LayoutClusterer.cards(_tokens())
    assert len(cards) == 2
    assert cards[0]["text"] == "06:00 ₹3,540 6E-205"
    assert cards[1]["text"] == "09:30 ₹3,717 6E-532"


def test_empty_tokens_return_empty_cards():
    assert LayoutClusterer.cards([]) == []
