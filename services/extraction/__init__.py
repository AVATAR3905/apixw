"""Provenance-aware extraction service layer (OCR / VLM / layout clustering).

Implements the OBSERVE -> UNDERSTAND -> EXTRACT chain:
1. DOM state (Playwright element boxes + text) is the cheapest, most accurate signal.
2. OCR (PP-OCRv5) recovers text from pixel-only surfaces via geometry clustering.
3. A small VLM backend (PaddleOCR-VL / OpenRouter) resolves ambiguity only where
   the first two stages fell short.

OCR/VLM dependencies are optional (lazy imports) so the collector runs without
them; each stage degrades gracefully to the next.
"""

from .adaptive_extractor import AdaptiveExtractor, ExtractionContext, ExtractionResult
from .layout_clusterer import LayoutClusterer, OCRToken
from .ocr_service import ExtractionNotAvailable, OCRService
from .vlm_service import VLMNotConfigured, VLMService

__all__ = [
    "AdaptiveExtractor",
    "ExtractionContext",
    "ExtractionResult",
    "LayoutClusterer",
    "OCRToken",
    "ExtractionNotAvailable",
    "OCRService",
    "VLMNotConfigured",
    "VLMService",
]
